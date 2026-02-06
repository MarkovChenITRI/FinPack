"""
股票數據快取模組 - 系統核心數據來源

================================================================================
                                 架構概覽
================================================================================

【數據流】
    yfinance API → raw_data (OHLCV) → pickle 快取
                          ↓
    _align_data_with_bfill() → aligned_data (日期對齊)
                          ↓
    _calculate_all_indicators() → sharpe_matrix, slope_matrix

【關鍵屬性】
    raw_data       原始 OHLCV (dict[ticker] → DataFrame)
    aligned_data   日期對齊後的 OHLCV (dict[ticker] → DataFrame)
    sharpe_matrix  Sharpe Ratio 矩陣 (DataFrame: 日期 × 股票)
    slope_matrix   排名變化矩陣 (DataFrame: 日期 × 股票)

【元件數據對應表】⚠️ 所有元件必須使用相同數據來源
    ┌───────────────────┬─────────────────────────────────────┐
    │ 元件              │ 數據來源                            │
    ├───────────────────┼─────────────────────────────────────┤
    │ K 線圖            │ aligned_data                        │
    │ Sharpe 柱狀圖     │ sharpe_matrix                       │
    │ 增長率柱狀圖      │ slope_matrix                        │
    │ 交易模擬器        │ aligned_data                        │
    │ 回測引擎-價格     │ aligned_data                        │
    │ 回測引擎-排名     │ sharpe_matrix / slope_matrix        │
    └───────────────────┴─────────────────────────────────────┘

================================================================================
                                 設計原則
================================================================================

【快取原則】
    ✅ 快取：raw_data, watchlist, stock_info, last_update
    ❌ 不快取：sharpe_matrix, slope_matrix（每次載入重算）

【日期對齊】
    不同市場交易日不同 → _align_data_with_bfill() 統一日期
    1. 過濾有效交易日（≥50 支股票有資料）
    2. 每支股票 reindex 到統一日期
    3. bfill().ffill() 填補缺失值

【Inf/NaN 處理】
    _calculate_sharpe(): rolling_std=0 → Inf → NaN
    sharpe_matrix: Inf/-Inf → NaN → bfill/ffill
    slope_matrix: 第一行 NaN → 0
    API clean_nan(): NaN/Inf → JSON null

【修改注意】
    - 新增指標：修改 _calculate_all_indicators()
    - 禁止在 _save_to_cache() 存衍生指標
    - 禁止在 _fetch_stock_history() 計算指標

================================================================================
                                 公式說明
================================================================================

【Sharpe Ratio】
    Sharpe = (滾動平均超額報酬 / 滾動標準差) × √252
    - 超額報酬 = 日報酬率 - 日無風險利率(4%/252)
    - 滾動視窗 = 252 天
    - 解讀：>1 優良，>2 優秀，<0 虧損

【Ranking Change（排名變化）】
    Ranking Change = Sharpe排名(yesterday) - Sharpe排名(today)
    - +10 = 排名上升 10 位
    - -5 = 排名下降 5 位
    - 前端顯示為「增長率 Top 15」

================================================================================
"""
import pickle
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta
from pathlib import Path


# 快取目錄
CACHE_DIR = Path(__file__).parent.parent / "cache"
CACHE_FILE = CACHE_DIR / "stock_data.pkl"


class StockDataCache:
    """股票數據快取器"""
    
    # TradingView 設定
    WATCHLIST_ID = "118349730"
    SESSION_ID = "b379eetq1pojcel6olyymmpo1rd41nng"
    
    # 計算參數
    SHARPE_WINDOW = 252   # Sharpe 計算視窗
    RISK_FREE_RATE = 0.04
    
    def __init__(self, auto_load: bool = True):
        # ====================================================================
        # 原始資料（會被快取到 pickle）
        # 注意：只有這些資料會被存入快取！
        # ====================================================================
        self.raw_data = {}    # {ticker: DataFrame with OHLCV only}
        self.watchlist = {}   # {industry: {provider: [codes]}}
        self.stock_info = {}  # {ticker: {country, industry, provider}}
        self.last_update = None
        
        # ====================================================================
        # 衍生資料（動態計算，禁止快取！）
        # 這些資料在每次載入後由 _calculate_all_indicators() 計算
        # ====================================================================
        self.aligned_data = {}      # 對齊日期後的資料（用 bfill 填補）
        self.unified_dates = None   # 統一日期索引
        self.sharpe_matrix = None   # 由 aligned_data 計算得出
        self.slope_matrix = None    # Sharpe 排名變化（昨天排名 - 今天排名）
        self.initialized = False
        
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        
        if auto_load:
            self.load_or_fetch()
    
    def load_or_fetch(self, force_refresh: bool = False):
        """載入快取或重新抓取資料"""
        if not force_refresh and self._load_from_cache():
            print(f"✅ 從快取載入原始資料 (最後更新: {self.last_update})")
            print(f"  📦 raw_data: {len(self.raw_data)} 檔股票")
        else:
            print("📥 開始抓取股票資料...")
            self._fetch_all_data()
            self._save_to_cache()
            print(f"✅ 股票資料抓取完成 ({len(self.raw_data)} 檔股票)")
        
        # 統一對齊所有股票的日期（用 bfill 填補）
        print("📅 對齊股票日期（bfill）...")
        self._align_data_with_bfill()
        print(f"✅ 日期對齊完成")
        print(f"  📅 unified_dates: {len(self.unified_dates) if self.unified_dates is not None else 0} 個交易日")
        print(f"  📦 aligned_data: {len(self.aligned_data)} 檔股票")
        
        # 載入後計算衍生指標（基於對齊後的資料）
        print("📊 計算衍生指標...")
        self._calculate_all_indicators()
        self.initialized = True
        print(f"✅ 指標計算完成")
        print(f"  📊 sharpe_matrix: {self.sharpe_matrix.shape if self.sharpe_matrix is not None and not self.sharpe_matrix.empty else 'None/Empty'}")
        print(f"  📊 slope_matrix: {self.slope_matrix.shape if self.slope_matrix is not None and not self.slope_matrix.empty else 'None/Empty'}")
    
    # ===== 快取管理 =====
    
    def _load_from_cache(self) -> bool:
        """從快取載入原始資料"""
        if not CACHE_FILE.exists():
            return False
        
        try:
            with open(CACHE_FILE, 'rb') as f:
                cache = pickle.load(f)
            
            cache_time = cache.get('last_update')
            if cache_time:
                cache_age = datetime.now() - cache_time
                if cache_age > timedelta(days=1):
                    print("⚠️ 快取已過期，將重新抓取")
                    return False
            
            self.raw_data = cache.get('raw_data', {})
            self.watchlist = cache.get('watchlist', {})
            self.stock_info = cache.get('stock_info', {})
            self.last_update = cache.get('last_update')
            
            return len(self.raw_data) > 0
            
        except Exception as e:
            print(f"⚠️ 載入快取失敗: {e}")
            return False
    
    def _save_to_cache(self):
        """
        儲存原始資料到快取
        
        ⚠️ 重要：禁止在此加入任何衍生指標！
        - ❌ 不要加入 sharpe_matrix
        - ❌ 不要加入 slope_matrix
        - ❌ 不要加入任何計算出來的資料
        """
        try:
            # 只存原始資料，不存衍生指標
            cache = {
                'raw_data': self.raw_data,      # 只有 OHLCV
                'watchlist': self.watchlist,    # 產業分類
                'stock_info': self.stock_info,  # 股票基本資訊
                'last_update': self.last_update # 更新時間
                # ❌ 禁止加入 sharpe_matrix, slope_matrix 等衍生資料
            }
            with open(CACHE_FILE, 'wb') as f:
                pickle.dump(cache, f)
            print(f"💾 已儲存快取至 {CACHE_FILE}")
        except Exception as e:
            print(f"⚠️ 儲存快取失敗: {e}")
    
    # ===== 資料抓取 =====
    
    def _fetch_watchlist(self) -> dict:
        """從 TradingView 取得投資組合清單"""
        import requests
        
        url = f'https://in.tradingview.com/api/v1/symbols_list/custom/{self.WATCHLIST_ID}'
        headers = {
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'cookie': f'sessionid={self.SESSION_ID}',
            'x-requested-with': 'XMLHttpRequest',
        }
        
        try:
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            symbols = response.json()["symbols"]
        except Exception as e:
            print(f"⚠️ TradingView 無回應: {e}")
            return {}
        
        result = {}
        current_key = None
        
        for item in symbols:
            if "###" in item:
                current_key = item.strip("###\u2064")
                result[current_key] = {}
            elif current_key:
                provider, code = item.split(":", 1)
                if provider not in result[current_key]:
                    result[current_key][provider] = []
                
                # 轉換為 yfinance 格式
                if provider in ['NASDAQ', 'NYSE']:
                    yf_code = code
                    country = 'US'
                elif provider == 'TWSE':
                    yf_code = f"{code}.TW"
                    country = 'TW'
                else:
                    continue
                
                result[current_key][provider].append(yf_code)
                
                self.stock_info[yf_code] = {
                    'country': country,
                    'industry': current_key,
                    'provider': provider,
                    'original_code': code
                }
        
        return result
    
    def _fetch_stock_history(self, ticker: str, period: str = "6y") -> pd.DataFrame:
        """
        下載單一股票歷史數據
        
        ⚠️ 重要：此函數只回傳原始 OHLCV 資料！
        - ❌ 不要在這裡計算 Sharpe
        - ❌ 不要在這裡計算 Returns
        - ❌ 不要在這裡加入任何衍生欄位
        
        Returns:
            DataFrame with columns: Open, High, Low, Close, Volume (僅此五欄)
        """
        try:
            df = yf.Ticker(ticker).history(period=period, interval="1d")
            if df.empty:
                return pd.DataFrame()
            
            df = df.tz_localize(None)
            df = df.sort_index()
            # ⚠️ 只保留原始欄位，禁止加入衍生欄位！
            return df[['Open', 'High', 'Low', 'Close', 'Volume']]
        except Exception as e:
            print(f"  ⚠️ {ticker}: {e}")
            return pd.DataFrame()
    
    def _fetch_all_data(self):
        """抓取所有股票的原始資料（含市場指數）"""
        self.watchlist = self._fetch_watchlist()
        
        if not self.watchlist:
            print("⚠️ 無法取得 watchlist")
            return
        
        # 先抓取市場指數（優先，確保 K 線圖有資料）
        market_indices = [
            ('^IXIC', 'NASDAQ', 'US'),      # NASDAQ 指數
            ('^TWII', 'TWSE', 'TW'),        # 台灣加權指數
            ('GC=F', 'CME', 'US'),          # 黃金期貨
            ('BTC-USD', 'CRYPTO', 'US'),    # 比特幣
            ('TLT', 'NYSE', 'US'),          # 美國20年期公債 ETF
        ]
        
        # ⚠️ 重要：所有資料統一使用 6y，確保指標計算後仍有 5 年可用
        # 不要修改這個值！如需調整請同時修改檔案開頭的說明文件
        DATA_PERIOD = "6y"
        
        print(f"📈 抓取市場指數（{DATA_PERIOD}）...")
        for ticker, provider, country in market_indices:
            print(f"  抓取 {ticker}...", end=" ")
            df = self._fetch_stock_history(ticker, period=DATA_PERIOD)
            
            if df.empty:
                print("❌ 無資料")
                continue
            
            self.raw_data[ticker] = df
            self.stock_info[ticker] = {
                'country': country,
                'industry': 'Market Index',
                'provider': provider,
                'original_code': ticker
            }
            print(f"✅ {len(df)} 筆")
        
        all_tickers = list(self.stock_info.keys())
        # 過濾掉已經抓取的市場指數
        stock_tickers = [t for t in all_tickers if t not in [m[0] for m in market_indices]]
        print(f"📊 共 {len(stock_tickers)} 檔股票待抓取")
        
        for i, ticker in enumerate(stock_tickers):
            print(f"  [{i+1}/{len(stock_tickers)}] 抓取 {ticker}...", end=" ")
            
            # ⚠️ 使用統一的 DATA_PERIOD，不要硬編碼！
            df = self._fetch_stock_history(ticker, period=DATA_PERIOD)
            
            if df.empty:
                print("❌ 無資料")
                continue
            
            self.raw_data[ticker] = df
            print(f"✅ {len(df)} 筆")
        
        self.last_update = datetime.now()
    
    # =========================================================================
    # 日期對齊
    # =========================================================================
    
    def _align_data_with_bfill(self):
        """
        對齊所有股票的日期，並用 bfill 填補空缺
        
        不同市場有不同的交易日（如週末只有 BTC-USD 有資料），
        這會導致計算 slope/ranking 時出現大量 NaN。
        
        解決方案：
        1. 建立統一日期索引（所有股票日期的聯集）
        2. 過濾出「有效交易日」（≥50 支股票有資料的日子）
        3. 每支股票 reindex 到統一日期
        4. 使用 bfill (backward fill) 填補缺失值
        
        這確保所有指標計算都基於相同的日期基準。
        """
        if not self.raw_data:
            self.aligned_data = {}
            self.unified_dates = pd.DatetimeIndex([])
            return
        
        # Step 1: 收集所有日期，並統計每個日期有多少股票有資料
        date_stock_count = {}
        for ticker, df in self.raw_data.items():
            if df.empty:
                continue
            for date in df.index:
                date_stock_count[date] = date_stock_count.get(date, 0) + 1
        
        # Step 2: 過濾出有效交易日（≥50 支股票有資料）
        # 這會排除週末（只有加密貨幣交易）和其他非主要交易日
        MIN_STOCKS_FOR_VALID_DAY = 50
        valid_dates = [
            date for date, count in date_stock_count.items()
            if count >= MIN_STOCKS_FOR_VALID_DAY
        ]
        
        if not valid_dates:
            # 如果沒有有效日期（股票太少），使用所有日期
            valid_dates = list(date_stock_count.keys())
        
        self.unified_dates = pd.DatetimeIndex(sorted(valid_dates))
        
        # Step 3: 對齊每支股票的資料
        self.aligned_data = {}
        for ticker, df in self.raw_data.items():
            if df.empty:
                continue
            
            # Reindex 到統一日期，然後 bfill
            # bfill: 用「下一個有效值」填補空缺
            # 這對股票合理：假日用前一個交易日的收盤價
            aligned_df = df.reindex(self.unified_dates).bfill()
            
            # 對於開頭的 NaN（沒有後續值可 bfill），用 ffill 補
            aligned_df = aligned_df.ffill()
            
            self.aligned_data[ticker] = aligned_df
        
        # 記錄過濾掉的日期數量（debug 用）
        total_dates = len(date_stock_count)
        filtered_dates = total_dates - len(self.unified_dates)
        if filtered_dates > 0:
            print(f"  📅 過濾掉 {filtered_dates} 個非主要交易日（如週末）")

    # =========================================================================
    # 衍生指標計算區
    # =========================================================================
    # 所有衍生指標的計算邏輯都放在這裡
    # 新增指標時：
    #   1. 新增計算函數（如 _calculate_xxx）
    #   2. 在 _calculate_all_indicators() 中調用
    #   3. 在 class 中新增對應的 matrix 屬性（設為 None）
    # =========================================================================
    
    def _calculate_sharpe(self, close_series: pd.Series) -> pd.Series:
        """計算滾動 Sharpe 比率"""
        if close_series.empty:
            return pd.Series(dtype=float)
        
        returns = close_series.pct_change()
        daily_rf = self.RISK_FREE_RATE / self.SHARPE_WINDOW
        excess_returns = returns - daily_rf
        
        rolling_mean = excess_returns.rolling(self.SHARPE_WINDOW).mean()
        rolling_std = excess_returns.rolling(self.SHARPE_WINDOW).std()
        
        # 避免除以零產生 Inf
        rolling_std = rolling_std.replace(0, np.nan)
        
        sharpe = rolling_mean / rolling_std * np.sqrt(self.SHARPE_WINDOW)
        
        # 將 Inf/-Inf 替換為 NaN，然後用 bfill 填補
        sharpe = sharpe.replace([np.inf, -np.inf], np.nan)
        sharpe = sharpe.bfill().ffill()
        
        return sharpe
    
    def _calculate_ranking_change(self, sharpe_matrix: pd.DataFrame) -> pd.DataFrame:
        """
        計算 Sharpe 排名變化（前一交易日排名 - 今天排名）
        
        正值表示排名上升（例：從 #20 升到 #10 = +10）
        負值表示排名下降
        
        用於前端「增長率 Top 15」顯示，找出排名快速上升的股票
        這比單日數值變化更有意義，能真正反映「誰在崛起」
        
        注意：因為 aligned_data 已經過濾掉週末等非主要交易日，
        這裡直接 shift(1) 就是正確的前一交易日。
        """
        if sharpe_matrix.empty:
            return pd.DataFrame()
        
        # 計算每日排名（1 = 最高 Sharpe，數字越小越好）
        # ascending=False: Sharpe 越高排名越前
        # method='min': 相同值給相同排名
        ranking_matrix = sharpe_matrix.rank(axis=1, ascending=False, method='min')
        
        # 計算排名變化：前一交易日排名 - 今天排名
        # 正值 = 排名上升（從 20 升到 10 = 20-10 = +10）
        # 負值 = 排名下降（從 10 降到 20 = 10-20 = -10）
        ranking_change = ranking_matrix.shift(1) - ranking_matrix
        
        return ranking_change
    
    def _calculate_all_indicators(self):
        """
        計算所有衍生指標（每次載入快取後執行）
        
        這是衍生指標的唯一計算入口點！
        新增指標時，在這裡添加計算邏輯。
        
        重要：使用 aligned_data（對齊後的資料）計算，確保所有日期一致。
        
        目前計算的指標：
        - sharpe_matrix: 滾動 Sharpe Ratio（252天視窗）
        - slope_matrix: Sharpe 排名變化（昨天排名 - 今天排名），找出排名快速上升的股票
                        正值 = 排名上升（例：+10 表示從第 20 名升到第 10 名）
                        負值 = 排名下降
        """
        sharpe_data = {}
        
        print(f"  📊 aligned_data 有 {len(self.aligned_data)} 檔股票")
        
        # 使用對齊後的資料計算（確保所有股票日期一致）
        for ticker, df in self.aligned_data.items():
            if 'Close' not in df.columns:
                print(f"    ⚠️ {ticker} 沒有 Close 欄位，跳過")
                continue
            
            # 計算 Sharpe
            sharpe = self._calculate_sharpe(df['Close'])
            sharpe_data[ticker] = sharpe
        
        # 建立 Sharpe 矩陣
        if sharpe_data:
            self.sharpe_matrix = pd.DataFrame(sharpe_data).sort_index()
            
            # 將任何剩餘的 Inf 替換為 NaN，然後用 bfill/ffill 填補
            self.sharpe_matrix = self.sharpe_matrix.replace([np.inf, -np.inf], np.nan)
            self.sharpe_matrix = self.sharpe_matrix.bfill().ffill()
            
            # 計算排名變化（基於完整的 sharpe_matrix）
            # 因為日期已經對齊，不會有週末等非主要交易日的問題
            self.slope_matrix = self._calculate_ranking_change(self.sharpe_matrix)
            
            # slope_matrix 第一行會是 NaN（沒有前一天），用 0 填補
            self.slope_matrix = self.slope_matrix.fillna(0)
        else:
            self.sharpe_matrix = pd.DataFrame()
            self.slope_matrix = pd.DataFrame()
    
    # ===== 查詢方法 =====
    # 注意：所有查詢方法都使用 aligned_data（對齊後的資料）
    
    def get_stock_info(self, ticker: str) -> dict:
        """取得股票資訊"""
        return self.stock_info.get(ticker, {})
    
    def get_all_tickers(self) -> list:
        """取得所有股票代碼"""
        return list(self.aligned_data.keys())
    
    def get_tickers_by_country(self, country: str) -> list:
        """依國家篩選股票"""
        return [
            ticker for ticker, info in self.stock_info.items()
            if info.get('country') == country and ticker in self.aligned_data
        ]
    
    def get_tickers_by_industry(self, industry: str) -> list:
        """依產業篩選股票"""
        return [
            ticker for ticker, info in self.stock_info.items()
            if info.get('industry') == industry and ticker in self.aligned_data
        ]
    
    def get_industries(self) -> list:
        """取得所有產業名稱"""
        return list(self.watchlist.keys())
    
    def get_stock_sharpe(self, ticker: str) -> pd.Series:
        """
        取得單一股票的 Sharpe 時間序列
        
        Args:
            ticker: 股票代碼
            
        Returns:
            Series with date index and sharpe values
        """
        if self.sharpe_matrix is None or ticker not in self.sharpe_matrix.columns:
            return pd.Series(dtype=float)
        
        return self.sharpe_matrix[ticker]
    
    def get_sharpe_matrix(self, start_date: str = None, end_date: str = None) -> pd.DataFrame:
        """
        取得 Sharpe 矩陣（可選日期範圍）
        
        Args:
            start_date: 開始日期 (YYYY-MM-DD)
            end_date: 結束日期 (YYYY-MM-DD)
            
        Returns:
            DataFrame with date index and ticker columns
        """
        if self.sharpe_matrix is None:
            return pd.DataFrame()
        
        df = self.sharpe_matrix.copy()
        
        if start_date:
            df = df[df.index >= start_date]
        if end_date:
            df = df[df.index <= end_date]
        
        return df
    
    def get_daily_sharpe_summary(self, date: str = None) -> dict:
        """
        取得特定日期的 Sharpe 摘要（按國家分組）
        
        Args:
            date: 日期 (YYYY-MM-DD)，None 則使用最新日期
            
        Returns:
            {
                'date': '2026-02-05',
                'US': {'count': 30, 'mean': 1.2, 'max': 2.5, 'top3': [...]},
                'TW': {'count': 20, 'mean': 0.8, 'max': 1.8, 'top3': [...]}
            }
        """
        if self.sharpe_matrix is None or self.sharpe_matrix.empty:
            return {'date': None, 'US': {}, 'TW': {}}
        
        # 找到目標日期的資料
        if date:
            target_str = str(date)[:10]
            matched_dates = [d for d in self.sharpe_matrix.index if str(d)[:10] == target_str]
            if not matched_dates:
                return {'date': date, 'US': {}, 'TW': {}}
            actual_date = matched_dates[0]
        else:
            actual_date = self.sharpe_matrix.index[-1]
        
        row = self.sharpe_matrix.loc[actual_date]
        
        us_tickers = set(self.get_tickers_by_country('US'))
        tw_tickers = set(self.get_tickers_by_country('TW'))
        
        def summarize(tickers_set):
            values = row[row.index.isin(tickers_set)].dropna()
            if values.empty:
                return {'count': 0, 'mean': 0, 'max': 0, 'top3': []}
            
            top3 = values.nlargest(3)
            return {
                'count': len(values),
                'mean': round(values.mean(), 3),
                'max': round(values.max(), 3),
                'top3': [
                    {'ticker': t, 'sharpe': round(v, 3)}
                    for t, v in top3.items()
                ]
            }
        
        return {
            'date': str(actual_date)[:10],
            'US': summarize(us_tickers),
            'TW': summarize(tw_tickers)
        }

    def get_stock_price(self, ticker: str, date: str) -> dict:
        """
        取得股票在特定日期的價格資訊
        
        Args:
            ticker: 股票代碼
            date: 日期 (YYYY-MM-DD)
            
        Returns:
            {
                'ticker': 'AAPL',
                'date': '2026-02-04',
                'open': 100.0,
                'high': 105.0,
                'low': 98.0,
                'close': 103.0,
                'country': 'US'
            }
        """
        if ticker not in self.aligned_data:
            return {'error': f'股票 {ticker} 不存在'}
        
        df = self.aligned_data[ticker]
        
        # 嘗試找到指定日期
        try:
            # 將日期轉換為可比較格式
            target_date = pd.to_datetime(date).strftime('%Y-%m-%d')
            
            # 尋找日期
            matched = df[df.index.astype(str).str[:10] == target_date]
            
            if matched.empty:
                return {'error': f'找不到 {ticker} 在 {date} 的資料'}
            
            row = matched.iloc[0]
            info = self.stock_info.get(ticker, {})
            
            return {
                'ticker': ticker,
                'date': target_date,
                'open': float(row['Open']),
                'high': float(row['High']),
                'low': float(row['Low']),
                'close': float(row['Close']),
                'country': info.get('country', ''),
                'industry': info.get('industry', '')
            }
        except Exception as e:
            return {'error': str(e)}
    
    def get_stock_ohlcv(self, ticker: str) -> pd.DataFrame:
        """
        取得股票的完整 OHLCV 資料（使用對齊後的資料）
        
        Args:
            ticker: 股票代碼
            
        Returns:
            DataFrame with OHLCV columns, or None if not found
        """
        if ticker not in self.aligned_data:
            return None
        
        df = self.aligned_data[ticker].copy()
        # 確保 index 是字串格式的日期
        df.index = df.index.astype(str).str[:10]
        return df


# ===== 單例模式 =====

_stock_cache = None


def get_stock_cache() -> StockDataCache:
    """取得股票資料快取（單例）"""
    global _stock_cache
    if _stock_cache is None:
        _stock_cache = StockDataCache(auto_load=True)
    return _stock_cache


def refresh_stock_cache() -> StockDataCache:
    """強制重新抓取股票資料"""
    global _stock_cache
    _stock_cache = StockDataCache(auto_load=False)
    _stock_cache.load_or_fetch(force_refresh=True)
    return _stock_cache


# ===== 分析函數 =====

def get_industry_top_analysis(cache: StockDataCache, country: str = None, top_n: int = 15, date: str = None) -> dict:
    """分析 Sharpe Top N 的產業分布"""
    return _get_top_analysis(cache, cache.sharpe_matrix, country, top_n, 'sharpe', date)


def get_slope_top_analysis(cache: StockDataCache, country: str = None, top_n: int = 15, date: str = None) -> dict:
    """
    分析 Sharpe Slope Top N 的產業分布
    
    限制條件：只統計 Sharpe Top 15 產業內的股票
    1. 先找出 Sharpe Top 15 的產業
    2. 篩選屬於這些產業的所有股票
    3. 計算這些股票的 Slope 排名
    """
    return _get_slope_analysis_with_sharpe_filter(cache, country, top_n, date)


def _get_slope_analysis_with_sharpe_filter(cache: StockDataCache, country: str, top_n: int, target_date: str = None) -> dict:
    """
    帶有 Sharpe 產業過濾的 Slope 分析
    """
    sharpe_matrix = cache.sharpe_matrix
    slope_matrix = cache.slope_matrix
    
    if sharpe_matrix is None or sharpe_matrix.empty or slope_matrix is None or slope_matrix.empty:
        return {'date': None, 'industries': [], 'top_stocks': [], 'sharpe_top_industries': []}
    
    us_tickers = set(cache.get_tickers_by_country('US'))
    tw_tickers = set(cache.get_tickers_by_country('TW'))
    
    # 找到目標日期
    actual_date = None
    sharpe_row = None
    slope_row = None
    
    if target_date:
        target_date_str = str(target_date)[:10]
        for date in sharpe_matrix.index:
            if str(date)[:10] == target_date_str:
                actual_date = date
                sharpe_row = sharpe_matrix.loc[date]
                slope_row = slope_matrix.loc[date] if date in slope_matrix.index else None
                break
    else:
        # 找最新有效日期
        for date in reversed(sharpe_matrix.index):
            sharpe_current = sharpe_matrix.loc[date]
            slope_current = slope_matrix.loc[date] if date in slope_matrix.index else None
            
            if country == 'US':
                valid_sharpe = sharpe_current[sharpe_current.index.isin(us_tickers)].dropna()
            elif country == 'TW':
                valid_sharpe = sharpe_current[sharpe_current.index.isin(tw_tickers)].dropna()
            else:
                us_valid = sharpe_current[sharpe_current.index.isin(us_tickers)].dropna()
                tw_valid = sharpe_current[sharpe_current.index.isin(tw_tickers)].dropna()
                if len(us_valid) > 0 and len(tw_valid) > 0:
                    valid_sharpe = pd.concat([us_valid, tw_valid])
                else:
                    continue
            
            if len(valid_sharpe) >= min(top_n, 5) and slope_current is not None:
                actual_date = date
                sharpe_row = sharpe_current
                slope_row = slope_current
                break
    
    if actual_date is None or sharpe_row is None or slope_row is None:
        return {'date': target_date if target_date else None, 'industries': [], 'top_stocks': [], 'sharpe_top_industries': []}
    
    # Step 1: 篩選 Sharpe 資料
    if country == 'US':
        valid_sharpe = sharpe_row[sharpe_row.index.isin(us_tickers)].dropna()
        valid_slope = slope_row[slope_row.index.isin(us_tickers)].dropna()
    elif country == 'TW':
        valid_sharpe = sharpe_row[sharpe_row.index.isin(tw_tickers)].dropna()
        valid_slope = slope_row[slope_row.index.isin(tw_tickers)].dropna()
    else:
        us_sharpe = sharpe_row[sharpe_row.index.isin(us_tickers)].dropna()
        tw_sharpe = sharpe_row[sharpe_row.index.isin(tw_tickers)].dropna()
        valid_sharpe = pd.concat([us_sharpe, tw_sharpe])
        
        us_slope = slope_row[slope_row.index.isin(us_tickers)].dropna()
        tw_slope = slope_row[slope_row.index.isin(tw_tickers)].dropna()
        valid_slope = pd.concat([us_slope, tw_slope])
    
    if valid_sharpe.empty or valid_slope.empty:
        return {'date': str(actual_date)[:10], 'industries': [], 'top_stocks': [], 'sharpe_top_industries': []}
    
    # Step 2: 找出 Sharpe Top 15 的產業
    sharpe_top_stocks = valid_sharpe.nlargest(top_n)
    sharpe_top_industries = set()
    
    for ticker in sharpe_top_stocks.index:
        info = cache.get_stock_info(ticker)
        industry = info.get('industry', '未分類')
        sharpe_top_industries.add(industry)
    
    # Step 3: 篩選屬於這些產業的所有股票（不限於 Top 15）
    industry_tickers = set()
    for ticker in valid_slope.index:
        info = cache.get_stock_info(ticker)
        industry = info.get('industry', '未分類')
        if industry in sharpe_top_industries:
            industry_tickers.add(ticker)
    
    # Step 4: 從這些股票中取 Slope Top N
    filtered_slope = valid_slope[valid_slope.index.isin(industry_tickers)]
    
    if filtered_slope.empty:
        return {
            'date': str(actual_date)[:10], 
            'industries': [], 
            'top_stocks': [],
            'sharpe_top_industries': list(sharpe_top_industries)
        }
    
    slope_top_stocks = filtered_slope.nlargest(top_n)
    
    # Step 5: 建立結果
    industry_stats = {}
    top_stock_list = []
    
    for ticker, value in slope_top_stocks.items():
        info = cache.get_stock_info(ticker)
        industry = info.get('industry', '未分類')
        stock_country = info.get('country', '')
        
        top_stock_list.append({
            'ticker': ticker,
            'slope': round(value, 6),
            'country': stock_country,
            'industry': industry
        })
        
        if industry not in industry_stats:
            industry_stats[industry] = {
                'total': 0, 'US': 0, 'TW': 0, 
                'stocks': [],
                'US_stocks': [],
                'TW_stocks': []
            }
        
        industry_stats[industry]['total'] += 1
        industry_stats[industry]['stocks'].append(ticker)
        
        if stock_country == 'US':
            industry_stats[industry]['US'] += 1
            industry_stats[industry]['US_stocks'].append(ticker)
        elif stock_country == 'TW':
            industry_stats[industry]['TW'] += 1
            industry_stats[industry]['TW_stocks'].append(ticker)
    
    industries = [
        {'name': name, **stats}
        for name, stats in industry_stats.items()
    ]
    industries.sort(key=lambda x: x['total'], reverse=True)
    
    return {
        'date': str(actual_date)[:10],
        'industries': industries,
        'top_stocks': top_stock_list,
        'sharpe_top_industries': list(sharpe_top_industries)  # 額外返回 Sharpe Top 產業列表
    }


def _get_top_analysis(cache: StockDataCache, matrix: pd.DataFrame, 
                      country: str, top_n: int, value_name: str, target_date: str = None) -> dict:
    """
    通用的 Top 分析邏輯
    
    Args:
        cache: 股票快取
        matrix: Sharpe 或 Slope 矩陣
        country: 篩選國家 (US/TW/None)
        top_n: 取前 N 名
        value_name: 值的名稱 ('sharpe' 或 'slope')
        target_date: 指定日期 (YYYY-MM-DD)，None 則使用最新日期
    """
    if matrix is None or matrix.empty:
        return {'date': None, 'industries': [], 'top_stocks': []}
    
    us_tickers = set(cache.get_tickers_by_country('US'))
    tw_tickers = set(cache.get_tickers_by_country('TW'))
    
    # 如果指定日期，直接使用該日期
    if target_date:
        # 轉換字串為可比對的格式
        target_date_str = str(target_date)[:10]
        
        # 在 matrix 中尋找該日期
        for date in matrix.index:
            if str(date)[:10] == target_date_str:
                current_row = matrix.loc[date]
                
                if country == 'US':
                    row = current_row[current_row.index.isin(us_tickers)].dropna()
                elif country == 'TW':
                    row = current_row[current_row.index.isin(tw_tickers)].dropna()
                else:
                    us_valid = current_row[current_row.index.isin(us_tickers)].dropna()
                    tw_valid = current_row[current_row.index.isin(tw_tickers)].dropna()
                    row = pd.concat([us_valid, tw_valid])
                
                if not row.empty:
                    return _build_analysis_result(cache, row, date, top_n, value_name)
        
        # 指定日期沒有資料，返回空結果
        return {'date': target_date_str, 'industries': [], 'top_stocks': []}
    
    # 沒有指定日期，尋找最新有效日期
    latest_date = None
    row = None
    
    for date in reversed(matrix.index):
        current_row = matrix.loc[date]
        
        if country == 'US':
            valid_data = current_row[current_row.index.isin(us_tickers)].dropna()
            if len(valid_data) >= min(top_n, len(us_tickers)):
                latest_date = date
                row = valid_data
                break
        elif country == 'TW':
            valid_data = current_row[current_row.index.isin(tw_tickers)].dropna()
            if len(valid_data) >= min(top_n, len(tw_tickers)):
                latest_date = date
                row = valid_data
                break
        else:
            us_valid = current_row[current_row.index.isin(us_tickers)].dropna()
            tw_valid = current_row[current_row.index.isin(tw_tickers)].dropna()
            if len(us_valid) > 0 and len(tw_valid) > 0:
                all_valid = pd.concat([us_valid, tw_valid])
                latest_date = date
                row = all_valid
                break
    
    if latest_date is None or row is None or row.empty:
        return {'date': None, 'industries': [], 'top_stocks': []}
    
    return _build_analysis_result(cache, row, latest_date, top_n, value_name)


def _build_analysis_result(cache: StockDataCache, row: pd.Series, 
                           date, top_n: int, value_name: str) -> dict:
    """建立分析結果"""
    # 取 Top N
    top_stocks = row.nlargest(top_n)
    
    # 分析產業分布
    industry_stats = {}
    top_stock_list = []
    
    for ticker, value in top_stocks.items():
        info = cache.get_stock_info(ticker)
        industry = info.get('industry', '未分類')
        stock_country = info.get('country', '')
        
        top_stock_list.append({
            'ticker': ticker,
            value_name: round(value, 6) if value_name == 'slope' else round(value, 3),
            'country': stock_country,
            'industry': industry
        })
        
        if industry not in industry_stats:
            industry_stats[industry] = {
                'total': 0, 'US': 0, 'TW': 0, 
                'stocks': [],        # 所有股票（向下兼容）
                'US_stocks': [],     # 美股列表
                'TW_stocks': []      # 台股列表
            }
        
        industry_stats[industry]['total'] += 1
        industry_stats[industry]['stocks'].append(ticker)
        
        if stock_country == 'US':
            industry_stats[industry]['US'] += 1
            industry_stats[industry]['US_stocks'].append(ticker)
        elif stock_country == 'TW':
            industry_stats[industry]['TW'] += 1
            industry_stats[industry]['TW_stocks'].append(ticker)
    
    industries = [
        {'name': name, **stats}
        for name, stats in industry_stats.items()
    ]
    industries.sort(key=lambda x: x['total'], reverse=True)
    
    return {
        'date': str(date)[:10],
        'industries': industries,
        'top_stocks': top_stock_list
    }
