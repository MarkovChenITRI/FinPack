"""
資料抓取模組 - yfinance API

負責從 TradingView 和 yfinance 抓取股票資料與市場指數
"""
import pickle
import requests
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
from pathlib import Path

from .config import (
    CACHE_DIR, STOCK_CACHE_FILE, MARKET_CACHE_FILE,
    TRADINGVIEW_WATCHLIST_ID, TRADINGVIEW_SESSION_ID,
    DATA_PERIOD, MARKET_CACHE_MAX_AGE_HOURS, NON_TRADABLE_INDUSTRIES
)


def fetch_watchlist() -> tuple[dict, dict]:
    """
    從 TradingView 取得投資組合清單
    
    Returns:
        (watchlist, stock_info)
        watchlist: {industry: {provider: [codes]}}
        stock_info: {ticker: {country, industry, provider, original_code}}
    """
    url = f'https://in.tradingview.com/api/v1/symbols_list/custom/{TRADINGVIEW_WATCHLIST_ID}'
    headers = {
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'cookie': f'sessionid={TRADINGVIEW_SESSION_ID}',
        'x-requested-with': 'XMLHttpRequest',
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        symbols = response.json()["symbols"]
    except Exception as e:
        print(f"⚠️ TradingView 無回應: {e}")
        return {}, {}
    
    watchlist = {}
    stock_info = {}
    current_key = None
    
    for item in symbols:
        if "###" in item:
            current_key = item.strip("###\u2064")
            watchlist[current_key] = {}
        elif current_key:
            provider, code = item.split(":", 1)
            if provider not in watchlist[current_key]:
                watchlist[current_key][provider] = []
            
            # 轉換為 yfinance 格式
            if provider in ['NASDAQ', 'NYSE']:
                yf_code = code
                country = 'US'
            elif provider == 'TWSE':
                yf_code = f"{code}.TW"
                country = 'TW'
            else:
                continue
            
            watchlist[current_key][provider].append(yf_code)
            
            stock_info[yf_code] = {
                'country': country,
                'industry': current_key,
                'provider': provider,
                'original_code': code
            }
    
    return watchlist, stock_info


def fetch_stock_history(ticker: str, period: str = DATA_PERIOD) -> pd.DataFrame:
    """
    下載單一股票歷史數據
    
    只回傳原始 OHLCV 資料
    
    Returns:
        DataFrame with columns: Open, High, Low, Close, Volume
    """
    try:
        df = yf.Ticker(ticker).history(period=period, interval="1d")
        if df.empty:
            return pd.DataFrame()
        
        df = df.tz_localize(None)
        df = df.sort_index()
        return df[['Open', 'High', 'Low', 'Close', 'Volume']]
    except Exception as e:
        print(f"  ⚠️ {ticker}: {e}")
        return pd.DataFrame()


def fetch_all_stock_data() -> tuple[dict, dict, dict]:
    """
    抓取所有股票資料
    
    根據 TradingView 分類決定哪些是可交易標的，哪些是市場指數
    
    Returns:
        (raw_data, watchlist, stock_info)
    """
    watchlist, stock_info = fetch_watchlist()
    
    if not watchlist:
        print("⚠️ 無法取得 watchlist")
        return {}, {}, {}
    
    raw_data = {}
    
    # 抓取所有股票（包含 TradingView 分類為 Market Index 的）
    all_tickers = list(stock_info.keys())
    print(f"📊 共 {len(all_tickers)} 檔股票待抓取（{DATA_PERIOD}）")
    
    for i, ticker in enumerate(all_tickers):
        industry = stock_info[ticker].get('industry', 'Unknown')
        is_index = industry in NON_TRADABLE_INDUSTRIES
        prefix = "📈" if is_index else "  "
        
        print(f"{prefix} [{i+1}/{len(all_tickers)}] 抓取 {ticker} ({industry})...", end=" ")
        df = fetch_stock_history(ticker)
        
        if df.empty:
            print("❌ 無資料")
            continue
        
        raw_data[ticker] = df
        print(f"✅ {len(df)} 筆")
    
    return raw_data, watchlist, stock_info


def load_stock_cache() -> tuple[dict, dict, dict, datetime | None]:
    """
    從快取載入資料
    
    Returns:
        (raw_data, watchlist, stock_info, last_update)
    """
    print(f"📂 Stock Cache 檔案: {STOCK_CACHE_FILE}")
    print(f"   存在: {STOCK_CACHE_FILE.exists()}")
    
    if not STOCK_CACHE_FILE.exists():
        print("⚠️ Stock 快取檔案不存在，將重新抓取")
        return {}, {}, {}, None
    
    try:
        print(f"📥 正在讀取 Stock 快取檔案...")
        with open(STOCK_CACHE_FILE, 'rb') as f:
            cache = pickle.load(f)
        
        cache_time = cache.get('last_update')
        raw_data = cache.get('raw_data', {})
        watchlist = cache.get('watchlist', {})
        stock_info = cache.get('stock_info', {})
        
        print(f"✅ 載入 Stock 快取成功")
        print(f"   - 快取時間: {cache_time}")
        print(f"   - 共 {len(raw_data)} 檔股票資料")
        print(f"   - 共 {len(watchlist)} 個產業分類")
        print(f"   - 共 {len(stock_info)} 筆股票資訊")
        
        if cache_time:
            cache_age = datetime.now() - cache_time
            print(f"   - 快取年齡: {cache_age}")
            if cache_age > timedelta(days=1):
                print("⚠️ 快取已超過 1 天，將重新抓取")
                return {}, {}, {}, None
            else:
                print("✅ 快取仍有效，使用快取資料")
        
        return (raw_data, watchlist, stock_info, cache_time)
    except Exception as e:
        print(f"⚠️ 載入快取失敗: {e}")
        print(f"   提示: 可能是 numpy 版本不相容，需重新產生 cache")
        return {}, {}, {}, None


def save_stock_cache(raw_data: dict, watchlist: dict, stock_info: dict):
    """儲存資料到快取"""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    
    try:
        cache = {
            'raw_data': raw_data,
            'watchlist': watchlist,
            'stock_info': stock_info,
            'last_update': datetime.now()
        }
        with open(STOCK_CACHE_FILE, 'wb') as f:
            pickle.dump(cache, f)
        print(f"💾 已儲存 Stock 快取至 {STOCK_CACHE_FILE}")
        print(f"   - 共 {len(raw_data)} 檔股票資料")
    except Exception as e:
        print(f"⚠️ 儲存 Stock 快取失敗: {e}")


# ===== 市場資料加載 =====

class MarketDataLoader:
    """
    市場數據加載器
    
    設計原則：
    - 初始化時載入所有市場資料（max 範圍）
    - 伺服器運行期間只從快取讀取，不再從 yfinance 抓取
    - 不同 period 從已載入的資料中切片
    """
    
    # 預載的市場指數（包含匯率 TWD=X）
    MARKET_SYMBOLS = ['^IXIC', '^TWII', 'GC=F', 'BTC-USD', 'TLT', '^GSPC', 'TWD=X']
    
    def __init__(self):
        self.cache = {}           # 原始資料快取 {symbol: DataFrame}
        self.cache_time = {}      # 快取時間
        self.exchange_rate = 32.0 # 匯率
        self.initialized = False  # 初始化完成標記
        
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        print(f"📂 Cache 目錄: {CACHE_DIR}")
        print(f"📄 Market Cache 檔案: {MARKET_CACHE_FILE}")
        print(f"   存在: {MARKET_CACHE_FILE.exists()}")
        self._load_cache_from_disk()
    
    def _load_cache_from_disk(self):
        """從磁碟載入快取"""
        if MARKET_CACHE_FILE.exists():
            try:
                print(f"📥 正在讀取市場快取檔案...")
                with open(MARKET_CACHE_FILE, 'rb') as f:
                    saved = pickle.load(f)
                    self.cache = saved.get('data', {})
                    self.cache_time = saved.get('time', {})
                    self.exchange_rate = saved.get('exchange_rate', 32.0)
                    print(f"✅ 載入市場資料快取成功")
                    print(f"   - 共 {len(self.cache)} 個 symbol")
                    for sym, df in self.cache.items():
                        if isinstance(df, pd.DataFrame):
                            print(f"   - {sym}: {len(df)} 筆資料")
            except Exception as e:
                print(f"⚠️ 載入市場快取失敗: {e}")
                print(f"   提示: 可能是 numpy 版本不相容，需重新產生 cache")
        else:
            print(f"⚠️ 市場快取檔案不存在: {MARKET_CACHE_FILE}")
    
    def _save_cache_to_disk(self):
        """將快取存入磁碟"""
        try:
            with open(MARKET_CACHE_FILE, 'wb') as f:
                pickle.dump({
                    'data': self.cache,
                    'time': self.cache_time,
                    'exchange_rate': self.exchange_rate
                }, f)
            print(f"   ✅ 已儲存至 {MARKET_CACHE_FILE}")
        except Exception as e:
            print(f"   ❌ 儲存市場快取失敗: {e}")
    
    def _has_cache(self, symbol: str) -> bool:
        """檢查是否有該 symbol 的快取"""
        return symbol in self.cache and not self.cache[symbol].empty
    
    def _filter_by_period(self, df: pd.DataFrame, period: str) -> pd.DataFrame:
        """根據 period 過濾 DataFrame"""
        if df.empty:
            return df
        
        period_days = {
            '1mo': 30, '3mo': 90, '6mo': 180,
            '1y': 365, '2y': 730, '5y': 1825, '6y': 2190
        }
        
        if period in period_days:
            cutoff = datetime.now() - timedelta(days=period_days[period])
            return df[df.index >= cutoff].copy()
        
        # max 或未知 period，返回全部
        return df.copy()
    
    def preload_all(self, aligned_data: dict = None):
        """
        預載所有市場資料（只在初始化時呼叫）
        
        優先順序：
        1. 已有快取且足夠新（< 4小時）→ 跳過
        2. aligned_data 有資料 → 使用
        3. yfinance 抓取 → 最後手段
        """
        print(f"\n🔄 開始預載市場資料...")
        print(f"   快取有效時間: {MARKET_CACHE_MAX_AGE_HOURS} 小時")
        
        cache_max_age = timedelta(hours=MARKET_CACHE_MAX_AGE_HOURS)
        now = datetime.now()
        
        for symbol in self.MARKET_SYMBOLS:
            print(f"\n   📊 處理 {symbol}...")
            
            # 檢查快取是否足夠新
            if symbol in self.cache and symbol in self.cache_time:
                age = now - self.cache_time[symbol]
                has_data = not self.cache[symbol].empty if isinstance(self.cache[symbol], pd.DataFrame) else False
                print(f"      - 快取存在: True, 資料筆數: {len(self.cache[symbol]) if has_data else 0}")
                print(f"      - 快取年齡: {age}")
                
                if age < cache_max_age and has_data:
                    print(f"      ✅ 快取有效，跳過抓取")
                    continue  # 快取有效，跳過
                else:
                    print(f"      ⚠️ 快取過期或無資料，需重新抓取")
            else:
                print(f"      - 快取存在: False")
            
            # 嘗試從 aligned_data 讀取
            if aligned_data and symbol in aligned_data:
                df = aligned_data[symbol].copy()
                if not df.empty:
                    print(f"      ✅ 從 aligned_data 載入 ({len(df)} 筆)")
                    self.cache[symbol] = df
                    self.cache_time[symbol] = now
                    continue
            
            # 從 yfinance 抓取（max 範圍）
            try:
                print(f"      📥 從 yfinance 抓取 (period=max)...")
                ticker = yf.Ticker(symbol)
                df = ticker.history(period="max", interval="1d")
                df = df.tz_localize(None)
                df = df.sort_index()
                
                if not df.empty:
                    print(f"      ✅ 抓取成功 ({len(df)} 筆)")
                    self.cache[symbol] = df
                    self.cache_time[symbol] = now
                else:
                    print(f"      ❌ 無資料")
            except Exception as e:
                print(f"      ❌ 抓取失敗: {e}")
        
        # 從 TWD=X 歷史數據設定最新匯率
        print(f"\n   💱 處理匯率...")
        if self._has_cache('TWD=X'):
            twd_data = self.cache['TWD=X']
            self.exchange_rate = round(twd_data['Close'].iloc[-1], 2)
            print(f"      ✅ 最新匯率: {self.exchange_rate}")
            print(f"      ✅ 歷史匯率: {len(twd_data)} 筆")
        else:
            print(f"      ⚠️ 無匯率歷史數據，使用預設值: {self.exchange_rate}")
        
        # 儲存快取並標記初始化完成
        print(f"\n💾 儲存市場快取...")
        self._save_cache_to_disk()
        self.initialized = True
        print(f"✅ 市場資料預載完成\n")
    
    def get_index_data(self, symbol: str, period: str = "2y", aligned_data: dict = None) -> pd.DataFrame:
        """
        獲取指數歷史數據
        
        初始化後只從快取讀取，不再從 yfinance 抓取
        """
        # 從快取讀取並根據 period 切片
        if self._has_cache(symbol):
            return self._filter_by_period(self.cache[symbol], period)
        
        # 嘗試從 aligned_data 讀取
        if aligned_data and symbol in aligned_data:
            df = aligned_data[symbol].copy()
            return self._filter_by_period(df, period)
        
        # 初始化完成後不允許從 yfinance 抓取
        if self.initialized:
            print(f"⚠️ {symbol} 資料不存在（已禁止運行時抓取）")
            return pd.DataFrame()
        
        # 初始化期間允許抓取
        try:
            print(f"📥 從 yfinance 抓取 {symbol}...")
            ticker = yf.Ticker(symbol)
            df = ticker.history(period="max", interval="1d")
            df = df.tz_localize(None)
            df = df.sort_index()
            
            if not df.empty:
                self.cache[symbol] = df
                self.cache_time[symbol] = datetime.now()
                self._save_cache_to_disk()
            
            return self._filter_by_period(df, period)
        except Exception as e:
            print(f"Error fetching {symbol}: {e}")
            return pd.DataFrame()
    
    def get_weighted_kline(self, symbol: str, period: str = "2y", aligned_data: dict = None) -> list:
        """獲取 K 線數據（供前端圖表）"""
        df = self.get_index_data(symbol, period, aligned_data)
        
        if df.empty:
            return []
        
        kline_data = []
        for idx, row in df.iterrows():
            if pd.isna(row['Open']) or pd.isna(row['Close']):
                continue
            
            kline_data.append({
                'time': idx.strftime('%Y-%m-%d'),
                'open': round(row['Open'], 2),
                'high': round(row['High'], 2),
                'low': round(row['Low'], 2),
                'close': round(row['Close'], 2),
                'volume': int(row['Volume']) if not pd.isna(row['Volume']) else 0
            })
        
        return kline_data
    
    def get_global_weighted_index(self, period: str = "2y", aligned_data: dict = None) -> list:
        """計算國際加權指數 (NASDAQ 與台股 1:1 權重)"""
        nasdaq_df = self.get_index_data('^IXIC', period, aligned_data)
        twii_df = self.get_index_data('^TWII', period, aligned_data)
        
        if nasdaq_df.empty or twii_df.empty:
            return []
        
        common_dates = nasdaq_df.index.intersection(twii_df.index)
        
        if len(common_dates) == 0:
            return []
        
        kline_data = []
        
        for date in sorted(common_dates):
            nq = nasdaq_df.loc[date]
            tw = twii_df.loc[date]
            
            if tw['Close'] == 0:
                continue
            
            scale_factor = nq['Close'] / tw['Close']
            
            weighted_open = (nq['Open'] + tw['Open'] * scale_factor) / 2
            weighted_high = (nq['High'] + tw['High'] * scale_factor) / 2
            weighted_low = (nq['Low'] + tw['Low'] * scale_factor) / 2
            weighted_close = (nq['Close'] + tw['Close'] * scale_factor) / 2
            
            actual_high = max(weighted_open, weighted_high, weighted_low, weighted_close)
            actual_low = min(weighted_open, weighted_high, weighted_low, weighted_close)
            
            total_volume = int(nq['Volume'] + tw['Volume'])
            
            kline_data.append({
                'time': date.strftime('%Y-%m-%d'),
                'open': round(weighted_open, 2),
                'high': round(actual_high, 2),
                'low': round(actual_low, 2),
                'close': round(weighted_close, 2),
                'volume': total_volume
            })
        
        return kline_data
    
    def get_all_market_data(self, period: str = "2y", aligned_data: dict = None) -> dict:
        """獲取所有市場數據（從快取切片）"""
        return {
            'global': self.get_global_weighted_index(period, aligned_data),
            'nasdaq': self.get_weighted_kline('^IXIC', period, aligned_data),
            'twii': self.get_weighted_kline('^TWII', period, aligned_data),
            'gold': self.get_weighted_kline('GC=F', period, aligned_data),
            'btc': self.get_weighted_kline('BTC-USD', period, aligned_data),
            'bonds': self.get_weighted_kline('TLT', period, aligned_data)
        }
    
    def get_exchange_rate(self) -> float:
        """獲取美元兌台幣匯率（從快取讀取）"""
        return self.exchange_rate
    
    def get_exchange_rate_history(self, period: str = "6y") -> dict:
        """
        獲取歷史匯率數據
        
        Returns:
            {date_str: rate} 例如 {'2024-01-02': 31.5, '2024-01-03': 31.6, ...}
        """
        if not self._has_cache('TWD=X'):
            return {}
        
        df = self._filter_by_period(self.cache['TWD=X'], period)
        if df.empty:
            return {}
        
        # 轉換為 {date: rate} 格式
        result = {}
        for date, row in df.iterrows():
            date_str = date.strftime('%Y-%m-%d')
            result[date_str] = round(row['Close'], 4)
        
        return result


def get_usd_twd_rate() -> float:
    """獲取美元兌台幣匯率（已棄用，請使用 MarketDataLoader.get_exchange_rate）"""
    return 32.0
