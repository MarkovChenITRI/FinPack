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
    DATA_PERIOD, MARKET_INDICES, MARKET_CACHE_MAX_AGE_HOURS
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
    抓取所有股票資料（含市場指數）
    
    Returns:
        (raw_data, watchlist, stock_info)
    """
    watchlist, stock_info = fetch_watchlist()
    
    if not watchlist:
        print("⚠️ 無法取得 watchlist")
        return {}, {}, {}
    
    raw_data = {}
    
    # 先抓取市場指數
    print(f"📈 抓取市場指數（{DATA_PERIOD}）...")
    for ticker, provider, country in MARKET_INDICES:
        print(f"  抓取 {ticker}...", end=" ")
        df = fetch_stock_history(ticker)
        
        if df.empty:
            print("❌ 無資料")
            continue
        
        raw_data[ticker] = df
        stock_info[ticker] = {
            'country': country,
            'industry': 'Market Index',
            'provider': provider,
            'original_code': ticker
        }
        print(f"✅ {len(df)} 筆")
    
    # 抓取股票
    stock_tickers = [t for t in stock_info.keys() if t not in [m[0] for m in MARKET_INDICES]]
    print(f"📊 共 {len(stock_tickers)} 檔股票待抓取")
    
    for i, ticker in enumerate(stock_tickers):
        print(f"  [{i+1}/{len(stock_tickers)}] 抓取 {ticker}...", end=" ")
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
    if not STOCK_CACHE_FILE.exists():
        return {}, {}, {}, None
    
    try:
        with open(STOCK_CACHE_FILE, 'rb') as f:
            cache = pickle.load(f)
        
        cache_time = cache.get('last_update')
        if cache_time:
            cache_age = datetime.now() - cache_time
            if cache_age > timedelta(days=1):
                print("⚠️ 快取已過期，將重新抓取")
                return {}, {}, {}, None
        
        return (
            cache.get('raw_data', {}),
            cache.get('watchlist', {}),
            cache.get('stock_info', {}),
            cache.get('last_update')
        )
    except Exception as e:
        print(f"⚠️ 載入快取失敗: {e}")
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
        print(f"💾 已儲存快取至 {STOCK_CACHE_FILE}")
    except Exception as e:
        print(f"⚠️ 儲存快取失敗: {e}")


# ===== 市場資料加載 =====

class MarketDataLoader:
    """市場數據加載器"""
    
    def __init__(self):
        self.cache = {}
        self.cache_time = {}
        self.cache_max_age = timedelta(hours=MARKET_CACHE_MAX_AGE_HOURS)
        
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
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
    
    def get_index_data(self, symbol: str, period: str = "2y", aligned_data: dict = None) -> pd.DataFrame:
        """
        獲取指數歷史數據
        
        優先順序：
        1. 內部快取
        2. aligned_data（已對齊的股票資料）
        3. yfinance 即時抓取
        """
        cache_key = f"{symbol}_{period}"
        
        # 1. 檢查內部快取
        if self._is_cache_valid(cache_key):
            return self.cache[cache_key].copy()
        
        # 2. 嘗試從 aligned_data 讀取
        if aligned_data and symbol in aligned_data:
            df = aligned_data[symbol].copy()
            # 根據 period 過濾
            if period in ['1y', '2y', '5y', '6y']:
                years = int(period[0])
                cutoff = datetime.now() - timedelta(days=years * 365)
                df = df[df.index >= cutoff]
            elif period == '6mo':
                cutoff = datetime.now() - timedelta(days=180)
                df = df[df.index >= cutoff]
            elif period == '3mo':
                cutoff = datetime.now() - timedelta(days=90)
                df = df[df.index >= cutoff]
            
            if not df.empty:
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
            if cache_key in self.cache:
                return self.cache[cache_key].copy()
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
        """獲取所有市場數據"""
        return {
            'global': self.get_global_weighted_index(period, aligned_data),
            'nasdaq': self.get_weighted_kline('^IXIC', period, aligned_data),
            'twii': self.get_weighted_kline('^TWII', period, aligned_data),
            'gold': self.get_weighted_kline('GC=F', period, aligned_data),
            'btc': self.get_weighted_kline('BTC-USD', period, aligned_data),
            'bonds': self.get_weighted_kline('TLT', period, aligned_data)
        }


def get_usd_twd_rate() -> float:
    """獲取美元兌台幣匯率"""
    try:
        ticker = yf.Ticker("TWD=X")
        data = ticker.history(period="1d")
        if not data.empty:
            return round(data['Close'].iloc[-1], 2)
    except:
        pass
    return 32.0
