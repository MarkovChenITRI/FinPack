"""
市場數據工具 - 提供美股/台股大盤加權K線數據
"""
import yfinance as yf
import pandas as pd
import numpy as np
import pickle
from pathlib import Path
from datetime import datetime, timedelta


# 快取目錄
CACHE_DIR = Path(__file__).parent.parent / "cache"
MARKET_CACHE_FILE = CACHE_DIR / "market_data.pkl"


class MarketDataLoader:
    """市場數據加載器（含持久化快取）"""
    
    def __init__(self):
        self.cache = {}
        self.cache_time = {}
        self.cache_max_age = timedelta(hours=6)  # 快取有效期 6 小時
        
        # 確保快取目錄存在
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        
        # 載入持久化快取
        self._load_cache_from_disk()
    
    def _load_cache_from_disk(self):
        """從磁碟載入快取"""
        if MARKET_CACHE_FILE.exists():
            try:
                with open(MARKET_CACHE_FILE, 'rb') as f:
                    saved = pickle.load(f)
                    self.cache = saved.get('data', {})
                    self.cache_time = saved.get('time', {})
                    print(f"📊 載入市場資料快取 ({len(self.cache)} 項)")
            except Exception as e:
                print(f"⚠️ 載入市場快取失敗: {e}")
                self.cache = {}
                self.cache_time = {}
    
    def _save_cache_to_disk(self):
        """將快取存入磁碟"""
        try:
            with open(MARKET_CACHE_FILE, 'wb') as f:
                pickle.dump({
                    'data': self.cache,
                    'time': self.cache_time
                }, f)
        except Exception as e:
            print(f"⚠️ 儲存市場快取失敗: {e}")
    
    def _is_cache_valid(self, cache_key: str) -> bool:
        """檢查快取是否有效"""
        if cache_key not in self.cache or cache_key not in self.cache_time:
            return False
        
        age = datetime.now() - self.cache_time[cache_key]
        return age < self.cache_max_age
    
    def _get_from_stock_cache(self, symbol: str, period: str) -> pd.DataFrame:
        """嘗試從 stock_cache 讀取市場指數資料"""
        try:
            from utils.stock_cache import get_stock_cache
            stock_cache = get_stock_cache()
            
            if symbol in stock_cache.raw_data:
                df = stock_cache.raw_data[symbol].copy()
                
                # 根據 period 過濾資料
                if period in ['1y', '2y', '5y']:
                    years = int(period[0])
                    cutoff = datetime.now() - timedelta(days=years * 365)
                    df = df[df.index >= cutoff]
                elif period == '6mo':
                    cutoff = datetime.now() - timedelta(days=180)
                    df = df[df.index >= cutoff]
                elif period == '3mo':
                    cutoff = datetime.now() - timedelta(days=90)
                    df = df[df.index >= cutoff]
                elif period == '1mo':
                    cutoff = datetime.now() - timedelta(days=30)
                    df = df[df.index >= cutoff]
                
                return df
        except Exception as e:
            print(f"⚠️ 無法從 stock_cache 讀取 {symbol}: {e}")
        
        return pd.DataFrame()
    
    def _build_fallback_index(self, period: str) -> list:
        """
        使用快取股票建構近似指數（當無法取得市場指數時的備用方案）
        
        使用 stock_cache 中的美股與台股，計算等權重平均走勢
        
        Args:
            period: 時間範圍 (1y, 2y, 5y)
            
        Returns:
            list of dict: K線資料格式
        """
        return self._build_regional_index(period, region='all')
    
    def _build_regional_index(self, period: str, region: str = 'all') -> list:
        """
        使用快取股票建構區域指數
        
        Args:
            period: 時間範圍 (1y, 2y, 5y)
            region: 區域 ('us' = 美股, 'tw' = 台股, 'all' = 全部)
            
        Returns:
            list of dict: K線資料格式
        """
        try:
            from utils.stock_cache import get_stock_cache
            stock_cache = get_stock_cache()
            
            if not stock_cache.raw_data:
                print("⚠️ stock_cache 為空，無法建構備用指數")
                return []
            
            # 計算時間截止點
            if period in ['1y', '2y', '5y']:
                years = int(period[0])
                cutoff = datetime.now() - timedelta(days=years * 365)
            elif period == '6mo':
                cutoff = datetime.now() - timedelta(days=180)
            elif period == '3mo':
                cutoff = datetime.now() - timedelta(days=90)
            else:
                cutoff = datetime.now() - timedelta(days=730)  # 預設 2 年
            
            # 收集所有股票的收盤價和成交量資料
            all_returns = {}
            all_volumes = {}
            
            for symbol, df in stock_cache.raw_data.items():
                if symbol.startswith('^'):  # 跳過指數本身
                    continue
                
                # 根據區域過濾
                if region == 'us' and symbol.endswith('.TW'):
                    continue
                if region == 'tw' and not symbol.endswith('.TW'):
                    continue
                    
                try:
                    df_filtered = df[df.index >= cutoff].copy()
                    if len(df_filtered) < 20:  # 至少需要 20 個交易日
                        continue
                    
                    # 計算每日報酬率
                    returns = df_filtered['Close'].pct_change().dropna()
                    
                    for date, ret in returns.items():
                        if date not in all_returns:
                            all_returns[date] = []
                            all_volumes[date] = 0
                        all_returns[date].append(ret)
                        
                        # 累加成交量
                        if date in df_filtered.index and 'Volume' in df_filtered.columns:
                            vol = df_filtered.loc[date, 'Volume']
                            if not pd.isna(vol):
                                all_volumes[date] += int(vol)
                except:
                    continue
            
            if not all_returns:
                region_name = {'us': '美股', 'tw': '台股', 'all': '全部'}.get(region, region)
                print(f"⚠️ 無法從快取股票計算報酬率 ({region_name})")
                return []
            
            # 計算每日平均報酬率並構建指數
            sorted_dates = sorted(all_returns.keys())
            index_value = 10000  # 起始值
            kline_data = []
            
            for i, date in enumerate(sorted_dates):
                daily_returns = all_returns[date]
                if len(daily_returns) < 3:  # 至少需要 3 支股票的資料
                    continue
                
                avg_return = sum(daily_returns) / len(daily_returns)
                
                # 計算開高低收（使用報酬率的變異來模擬）
                prev_value = index_value
                index_value = prev_value * (1 + avg_return)
                
                # 使用報酬率的標準差來估計當日波動
                if len(daily_returns) > 1:
                    std_return = (sum((r - avg_return) ** 2 for r in daily_returns) / len(daily_returns)) ** 0.5
                else:
                    std_return = abs(avg_return) * 0.5
                
                high = max(prev_value, index_value) * (1 + std_return * 0.5)
                low = min(prev_value, index_value) * (1 - std_return * 0.5)
                
                # 使用實際股票成交量總和
                volume = all_volumes.get(date, 0)
                
                kline_data.append({
                    'time': date.strftime('%Y-%m-%d'),
                    'open': round(prev_value, 2),
                    'high': round(high, 2),
                    'low': round(low, 2),
                    'close': round(index_value, 2),
                    'volume': volume
                })
            
            if kline_data:
                stock_count = len([s for s in stock_cache.raw_data.keys() 
                                   if not s.startswith('^') and 
                                   (region == 'all' or 
                                    (region == 'us' and not s.endswith('.TW')) or
                                    (region == 'tw' and s.endswith('.TW')))])
                region_name = {'us': '美股', 'tw': '台股', 'all': '全部'}.get(region, region)
                print(f"✅ 使用 {stock_count} 支{region_name}股票建構備用指數（{len(kline_data)} 個交易日）")
            
            return kline_data
            
        except Exception as e:
            print(f"❌ 建構備用指數失敗: {e}")
            return []
        
    def get_index_data(self, symbol: str, period: str = "2y") -> pd.DataFrame:
        """
        獲取指數歷史數據（含多重快取機制）
        
        優先順序：
        1. market.py 內部快取（有效期 6 小時）
        2. stock_cache 中的市場指數資料
        3. 從 yfinance 即時抓取
        
        Args:
            symbol: 指數代碼 (如 ^IXIC, ^TWII)
            period: 時間範圍 (1y, 2y, 5y, max)
            
        Returns:
            DataFrame with OHLCV data
        """
        cache_key = f"{symbol}_{period}"
        
        # 1. 檢查內部快取是否有效
        if self._is_cache_valid(cache_key):
            return self.cache[cache_key].copy()
        
        # 2. 嘗試從 stock_cache 讀取
        df = self._get_from_stock_cache(symbol, period)
        if not df.empty:
            print(f"✅ 從 stock_cache 載入 {symbol}")
            self.cache[cache_key] = df
            self.cache_time[cache_key] = datetime.now()
            return df.copy()
        
        # 3. 從 yfinance 抓取
        try:
            print(f"📥 從 yfinance 抓取 {symbol}...")
            ticker = yf.Ticker(symbol)
            df = ticker.history(period=period, interval="1d")
            df = df.tz_localize(None)
            df = df.sort_index()
            
            if not df.empty:
                self.cache[cache_key] = df
                self.cache_time[cache_key] = datetime.now()
                self._save_cache_to_disk()
            
            return df.copy()
            
        except Exception as e:
            print(f"Error fetching {symbol}: {e}")
            # 如果抓取失敗但有舊快取，仍然返回舊快取
            if cache_key in self.cache:
                print(f"⚠️ 使用舊快取資料: {symbol}")
                return self.cache[cache_key].copy()
            return pd.DataFrame()
    
    def get_weighted_kline(self, symbol: str, period: str = "2y", convert_to_usd: bool = False) -> list:
        """
        獲取K線數據（用於前端圖表）
        
        Args:
            symbol: 指數代碼
            period: 時間範圍
            convert_to_usd: 未使用（保留參數以相容）
            
        Returns:
            list of dict: [{time, open, high, low, close, volume}, ...]
        """
        df = self.get_index_data(symbol, period)
        
        if df.empty:
            # 備用方案：使用快取股票建構區域指數
            if symbol == '^IXIC':
                print(f"⚠️ {symbol} 無法取得，使用美股建構備用指數")
                return self._build_regional_index(period, region='us')
            elif symbol == '^TWII':
                print(f"⚠️ {symbol} 無法取得，使用台股建構備用指數")
                return self._build_regional_index(period, region='tw')
            return []
        
        kline_data = []
        for idx, row in df.iterrows():
            # 跳過無效數據 (NaN)
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
    
    def get_global_weighted_index(self, period: str = "2y") -> list:
        """
        計算國際加權指數 (NASDAQ 與台股 1:1 固定權重)
        
        計算方式: 
        縮放係數 = NASDAQ收盤價 ÷ 台股收盤價 (標準化尺度)
        加權價格 = (NASDAQ價格 + 台股價格 × 縮放係數) ÷ 2
        
        如果無法取得指數資料，使用快取股票建構近似指數
        
        Returns:
            list of dict: [{time, open, high, low, close, volume}, ...]
        """
        # 獲取原始數據
        nasdaq_df = self.get_index_data('^IXIC', period)
        twii_df = self.get_index_data('^TWII', period)
        
        if nasdaq_df.empty or twii_df.empty:
            # 備用方案：使用快取股票建構近似指數
            return self._build_fallback_index(period)
        
        # 找出共同交易日
        common_dates = nasdaq_df.index.intersection(twii_df.index)
        
        if len(common_dates) == 0:
            return []
        
        kline_data = []
        
        for date in sorted(common_dates):
            nq = nasdaq_df.loc[date]
            tw = twii_df.loc[date]
            
            if tw['Close'] == 0:
                continue
            
            # 縮放係數 = NASDAQ收盤價 ÷ 台股收盤價
            scale_factor = nq['Close'] / tw['Close']
            
            # 加權價格計算 (1:1 固定權重)
            weighted_open = (nq['Open'] + tw['Open'] * scale_factor) / 2
            weighted_high = (nq['High'] + tw['High'] * scale_factor) / 2
            weighted_low = (nq['Low'] + tw['Low'] * scale_factor) / 2
            weighted_close = (nq['Close'] + tw['Close'] * scale_factor) / 2
            
            # 確保 high >= low
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
    
    def get_all_market_data(self, period: str = "2y") -> dict:
        """
        獲取所有市場數據
        
        Returns:
            dict with 'global', 'nasdaq', 'twii', 'gold', 'btc', 'bonds' data
        """
        return {
            'global': self.get_global_weighted_index(period),
            'nasdaq': self.get_weighted_kline('^IXIC', period),
            'twii': self.get_weighted_kline('^TWII', period),
            'gold': self.get_weighted_kline('GC=F', period),      # 黃金期貨
            'btc': self.get_weighted_kline('BTC-USD', period),    # 比特幣
            'bonds': self.get_weighted_kline('TLT', period)       # 美國20年期公債 ETF
        }


# 匯率獲取
def get_usd_twd_rate() -> float:
    """獲取美元兌台幣匯率"""
    try:
        ticker = yf.Ticker("TWD=X")
        data = ticker.history(period="1d")
        if not data.empty:
            return round(data['Close'].iloc[-1], 2)
    except:
        pass
    return 32.0  # 預設匯率


# 單例實例
_market_loader = None

def get_market_loader() -> MarketDataLoader:
    """獲取市場數據加載器單例"""
    global _market_loader
    if _market_loader is None:
        _market_loader = MarketDataLoader()
        # 更新匯率
        _market_loader.usd_twd_rate = get_usd_twd_rate()
    return _market_loader
