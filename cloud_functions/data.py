"""
Cloud Functions 資料擷取模組
參考自 src/data.py，獨立實作
"""
import json
import pickle
import logging
import requests
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional
import pandas as pd
import yfinance as yf

from .config import (
    CACHE_DIR, DATA_PERIOD,
    TRADINGVIEW_WATCHLIST_ID, TRADINGVIEW_SESSION_ID,
    NON_TRADABLE_INDUSTRIES
)

logger = logging.getLogger(__name__)

# ===== 快取管理 =====

def ensure_cache_dir():
    """確保快取目錄存在"""
    CACHE_DIR.mkdir(exist_ok=True)

def get_cache_path(name: str) -> Path:
    """取得快取檔案路徑"""
    ensure_cache_dir()
    return CACHE_DIR / f"{name}.pkl"

def is_cache_valid(cache_path: Path, max_age_hours: int = 24) -> bool:
    """檢查快取是否有效（預設24小時內）"""
    if not cache_path.exists():
        return False
    mtime = datetime.fromtimestamp(cache_path.stat().st_mtime)
    return datetime.now() - mtime < timedelta(hours=max_age_hours)

def load_cache(name: str, max_age_hours: int = 24) -> Optional[dict]:
    """載入快取"""
    cache_path = get_cache_path(name)
    if is_cache_valid(cache_path, max_age_hours):
        try:
            with open(cache_path, 'rb') as f:
                data = pickle.load(f)
                logger.info(f"Loaded cache: {name}")
                return data
        except Exception as e:
            logger.warning(f"Failed to load cache {name}: {e}")
    return None

def save_cache(name: str, data: dict):
    """儲存快取"""
    cache_path = get_cache_path(name)
    try:
        with open(cache_path, 'wb') as f:
            pickle.dump(data, f)
        logger.info(f"Saved cache: {name}")
    except Exception as e:
        logger.warning(f"Failed to save cache {name}: {e}")

# ===== TradingView Watchlist =====

def fetch_watchlist() -> tuple[dict, dict]:
    """
    從 TradingView 擷取觀察清單
    
    Returns:
        watchlist: {provider: [symbols]}
        stock_info: {symbol: {name, industry, ...}}
    """
    # 嘗試載入快取
    cached = load_cache('watchlist')
    if cached:
        return cached['watchlist'], cached['stock_info']
    
    url = f"https://www.tradingview.com/api/v1/symbols_list/custom/?list={TRADINGVIEW_WATCHLIST_ID}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Cookie': f'sessionid={TRADINGVIEW_SESSION_ID}'
    }
    
    try:
        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        logger.error(f"Failed to fetch watchlist: {e}")
        raise
    
    watchlist = {}  # {provider: [symbols]}
    stock_info = {}  # {symbol: info}
    
    for item in data.get('symbols', []):
        symbol_full = item.get('s', '')  # e.g., "NASDAQ:AAPL"
        if ':' not in symbol_full:
            continue
            
        provider, symbol = symbol_full.split(':', 1)
        
        # 建立 watchlist
        if provider not in watchlist:
            watchlist[provider] = []
        watchlist[provider].append(symbol)
        
        # 建立 stock_info
        info = item.get('f', [])
        stock_info[symbol] = {
            'symbol': symbol,
            'provider': provider,
            'name': info[0] if len(info) > 0 else symbol,
            'industry': info[4] if len(info) > 4 else 'Unknown',
            'sector': info[5] if len(info) > 5 else 'Unknown',
            'country': info[6] if len(info) > 6 else 'Unknown',
        }
    
    # 不再手動加入市場指數，信任 TradingView 的分類
    
    # 儲存快取
    save_cache('watchlist', {'watchlist': watchlist, 'stock_info': stock_info})
    
    logger.info(f"Fetched watchlist: {sum(len(v) for v in watchlist.values())} symbols")
    return watchlist, stock_info

# ===== Stock History =====

def convert_symbol_for_yfinance(symbol: str, provider: str) -> str:
    """
    將 TradingView 格式轉換為 yfinance 格式
    """
    # 台股轉換
    if provider == 'TWSE':
        return f"{symbol}.TW"
    elif provider == 'TPEX':
        return f"{symbol}.TWO"
    # 美股與其他直接使用
    return symbol

def fetch_stock_history(symbol: str, provider: str = 'NASDAQ', 
                        period: str = None) -> Optional[pd.DataFrame]:
    """
    擷取單一股票歷史資料
    
    Args:
        symbol: 股票代碼
        provider: 交易所
        period: 資料期間（預設使用 DATA_PERIOD）
    
    Returns:
        DataFrame with columns: [Open, High, Low, Close, Volume]
    """
    if period is None:
        period = DATA_PERIOD
        
    yf_symbol = convert_symbol_for_yfinance(symbol, provider)
    
    try:
        ticker = yf.Ticker(yf_symbol)
        df = ticker.history(period=period)
        
        if df.empty:
            logger.warning(f"No data for {symbol}")
            return None
            
        # 清理資料
        df = df[['Open', 'High', 'Low', 'Close', 'Volume']].copy()
        df.index = pd.to_datetime(df.index).tz_localize(None)
        df.index.name = 'Date'
        
        return df
        
    except Exception as e:
        logger.warning(f"Failed to fetch {symbol}: {e}")
        return None

def fetch_all_stocks(watchlist: dict, stock_info: dict, 
                     period: str = None, use_cache: bool = True) -> dict:
    """
    擷取所有股票的歷史資料
    
    Args:
        watchlist: {provider: [symbols]}
        stock_info: {symbol: info}
        period: 資料期間
        use_cache: 是否使用快取
    
    Returns:
        {symbol: DataFrame}
    """
    if period is None:
        period = DATA_PERIOD
    
    # 嘗試載入快取
    if use_cache:
        cached = load_cache('stock_history')
        if cached:
            return cached
    
    all_data = {}
    total_symbols = sum(len(v) for v in watchlist.values())
    processed = 0
    
    for provider, symbols in watchlist.items():
        for symbol in symbols:
            processed += 1
            if processed % 50 == 0:
                logger.info(f"Fetching... {processed}/{total_symbols}")
            
            df = fetch_stock_history(symbol, provider, period)
            if df is not None and len(df) > 100:  # 至少有100天資料
                all_data[symbol] = df
    
    logger.info(f"Fetched {len(all_data)} stocks successfully")
    
    # 儲存快取
    if use_cache and all_data:
        save_cache('stock_history', all_data)
    
    return all_data

# ===== Data Container =====

class DataContainer:
    """
    資料容器，整合所有資料
    """
    def __init__(self):
        self.watchlist = {}
        self.stock_info = {}
        self.stock_data = {}
        self.aligned_close = None
        self.date_index = None
        
    def load_all(self, use_cache: bool = True):
        """載入所有資料"""
        logger.info("Loading watchlist...")
        self.watchlist, self.stock_info = fetch_watchlist()
        
        logger.info("Loading stock history...")
        self.stock_data = fetch_all_stocks(
            self.watchlist, self.stock_info, use_cache=use_cache
        )
        
        logger.info("Aligning data...")
        self._align_data()
        
        logger.info(f"Data loaded: {len(self.stock_data)} stocks, {len(self.date_index)} days")
        
    def _align_data(self):
        """對齊所有股票資料到相同日期"""
        from .align import align_close_prices
        self.aligned_close, self.date_index = align_close_prices(self.stock_data)
        
    def get_close_matrix(self) -> pd.DataFrame:
        """取得對齊後的收盤價矩陣"""
        return self.aligned_close
    
    def get_stock_info(self, symbol: str) -> dict:
        """取得股票資訊"""
        return self.stock_info.get(symbol, {})
    
    def get_tradable_symbols(self) -> list:
        """取得可交易的股票清單（根據 TradingView 分類排除不可交易標的）"""
        return [
            s for s in self.aligned_close.columns
            if self.stock_info.get(s, {}).get('industry') not in NON_TRADABLE_INDUSTRIES
        ]
