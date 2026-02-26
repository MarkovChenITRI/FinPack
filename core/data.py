"""
資料抓取模組

負責從 TradingView 和 yfinance 抓取股票資料
支援智慧快取策略：
- DEBUG 模式：使用本地快取
- 生產模式：直接從 API 擷取
"""
import pickle
import logging
import requests
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
from typing import Optional, Tuple

from .config import (
    CACHE_DIR, STOCK_CACHE_FILE,
    TRADINGVIEW_WATCHLIST_ID, TRADINGVIEW_SESSION_ID,
    DATA_PERIOD, NON_TRADABLE_INDUSTRIES, MIN_HISTORY_DAYS,
    CACHE_MAX_STALENESS_DAYS
)

logger = logging.getLogger(__name__)


# =============================================================================
# TradingView Watchlist 擷取
# =============================================================================

def fetch_watchlist() -> Tuple[dict, dict]:
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
        logger.warning(f"TradingView 無回應: {e}")
        return {}, {}
    
    watchlist = {}
    stock_info = {}
    current_key = None
    
    for item in symbols:
        if "###" in item:
            current_key = item.strip("###\u2064")
            watchlist[current_key] = {}
        elif current_key:
            if ':' not in item:
                continue
            provider, code = item.split(":", 1)
            if provider not in watchlist[current_key]:
                watchlist[current_key][provider] = []
            
            # 轉換為 yfinance 格式
            if provider in ['NASDAQ', 'NYSE', 'AMEX']:
                yf_code = code
                country = 'US'
            elif provider == 'TWSE':
                yf_code = f"{code}.TW"
                country = 'TW'
            elif provider == 'TPEX':
                yf_code = f"{code}.TWO"
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


# =============================================================================
# 股票歷史資料擷取
# =============================================================================

def fetch_stock_history(ticker: str, period: str = DATA_PERIOD) -> pd.DataFrame:
    """
    下載單一股票歷史數據
    
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
        logger.debug(f"{ticker}: {e}")
        return pd.DataFrame()


def fetch_all_stock_data(show_progress: bool = True) -> Tuple[dict, dict, dict]:
    """
    抓取所有股票資料
    
    Args:
        show_progress: 是否顯示進度（CLI 模式用）
    
    Returns:
        (raw_data, watchlist, stock_info)
    """
    watchlist, stock_info = fetch_watchlist()
    
    if not watchlist:
        logger.warning("無法取得 watchlist")
        return {}, {}, {}
    
    raw_data = {}
    all_tickers = list(stock_info.keys())
    total = len(all_tickers)
    
    if show_progress:
        print(f"📊 共 {total} 檔股票待抓取（{DATA_PERIOD}）")
    
    for i, ticker in enumerate(all_tickers):
        industry = stock_info[ticker].get('industry', 'Unknown')
        is_index = industry in NON_TRADABLE_INDUSTRIES
        
        if show_progress:
            prefix = "📈" if is_index else "  "
            print(f"{prefix} [{i+1}/{total}] 抓取 {ticker} ({industry})...", end=" ")
        
        df = fetch_stock_history(ticker)
        
        if df.empty:
            if show_progress:
                print("❌ 無資料")
            continue
        
        if len(df) < MIN_HISTORY_DAYS:
            if show_progress:
                print(f"⚠️ 資料太少 ({len(df)} 筆)")
            continue
        
        raw_data[ticker] = df
        if show_progress:
            print(f"✅ {len(df)} 筆")
    
    return raw_data, watchlist, stock_info


# =============================================================================
# 快取操作
# =============================================================================

def _get_cache_data_date(raw_data: dict) -> Optional[datetime]:
    """取得快取資料的最新日期"""
    if not raw_data:
        return None
    sample_ticker = next(iter(raw_data))
    sample_df = raw_data[sample_ticker]
    if sample_df.empty:
        return None
    return sample_df.index[-1].date()


def load_stock_cache_raw() -> Tuple[dict, dict, dict, Optional[datetime]]:
    """
    讀取快取檔案（不判斷時效性，直接返回）
    
    Returns:
        (raw_data, watchlist, stock_info, last_update)
    """
    if not STOCK_CACHE_FILE.exists():
        return {}, {}, {}, None
    
    try:
        with open(STOCK_CACHE_FILE, 'rb') as f:
            cache = pickle.load(f)
        return (
            cache.get('raw_data', {}),
            cache.get('watchlist', {}),
            cache.get('stock_info', {}),
            cache.get('last_update')
        )
    except Exception as e:
        logger.warning(f"載入快取失敗: {e}")
        return {}, {}, {}, None


def load_stock_cache(max_staleness_days: int = CACHE_MAX_STALENESS_DAYS) -> Tuple[dict, dict, dict, Optional[datetime]]:
    """
    智慧載入快取
    
    Args:
        max_staleness_days: 允許的最大過期天數
    
    Returns:
        (raw_data, watchlist, stock_info, last_update)
    """
    logger.info(f"Stock Cache 檔案: {STOCK_CACHE_FILE}")
    
    if not STOCK_CACHE_FILE.exists():
        logger.warning("Stock 快取檔案不存在")
        return {}, {}, {}, None
    
    raw_data, watchlist, stock_info, cache_time = load_stock_cache_raw()
    
    if not raw_data:
        logger.warning("快取中無股票資料")
        return {}, {}, {}, None
    
    # 檢查快取時效性
    cache_data_date = _get_cache_data_date(raw_data)
    if cache_data_date is None:
        logger.warning("無法取得快取資料日期")
        return {}, {}, {}, None
    
    today = datetime.now().date()
    days_diff = (today - cache_data_date).days
    
    logger.info(f"快取最新數據日期: {cache_data_date}, 差距: {days_diff} 天")
    
    if days_diff <= max_staleness_days:
        logger.info(f"快取資料在 {max_staleness_days} 天內，使用快取")
        return raw_data, watchlist, stock_info, cache_time
    else:
        logger.warning(f"快取資料已過期 {days_diff} 天")
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
        logger.info(f"已儲存 Stock 快取: {len(raw_data)} 檔股票")
    except Exception as e:
        logger.error(f"儲存 Stock 快取失敗: {e}")


def smart_load_or_fetch(use_cache: bool = False, show_progress: bool = True) -> Tuple[dict, dict, dict, Optional[datetime]]:
    """
    智慧載入策略：
    1. 若 use_cache=True，強制使用快取
    2. 先檢查快取是否過期
    3. 若過期則嘗試抓取新資料
    4. 若抓取失敗則 fallback 使用舊快取
    
    Args:
        use_cache: 是否強制使用快取（--debug 模式）
        show_progress: 是否顯示進度
    
    Returns:
        (raw_data, watchlist, stock_info, last_update)
    """
    # use_cache=True：強制使用快取
    if use_cache:
        logger.info("[DEBUG] 使用本地快取模式")
        raw_data, watchlist, stock_info, last_update = load_stock_cache_raw()
        if raw_data:
            logger.info(f"[DEBUG] 載入快取成功: {len(raw_data)} 檔股票")
            return raw_data, watchlist, stock_info, last_update
        else:
            logger.error("[DEBUG] 快取不存在或無法讀取")
            return {}, {}, {}, None
    
    # 生產模式：先檢查快取
    raw_data, watchlist, stock_info, last_update = load_stock_cache()
    
    if raw_data:
        return raw_data, watchlist, stock_info, last_update
    
    # 快取過期或不存在，嘗試抓取
    logger.info("開始抓取股票資料...")
    new_raw_data, new_watchlist, new_stock_info = fetch_all_stock_data(show_progress)
    
    if new_raw_data and len(new_raw_data) > 0:
        new_last_update = datetime.now()
        save_stock_cache(new_raw_data, new_watchlist, new_stock_info)
        logger.info(f"股票資料抓取完成: {len(new_raw_data)} 檔")
        return new_raw_data, new_watchlist, new_stock_info, new_last_update
    else:
        # 抓取失敗，fallback 到舊快取
        logger.warning("抓取失敗，嘗試使用舊快取...")
        old_raw_data, old_watchlist, old_stock_info, old_last_update = load_stock_cache_raw()
        
        if old_raw_data:
            cache_data_date = _get_cache_data_date(old_raw_data)
            logger.info(f"Fallback 使用舊快取 (資料日期: {cache_data_date})")
            return old_raw_data, old_watchlist, old_stock_info, old_last_update
        else:
            logger.error("無可用快取，無法取得資料")
            return {}, {}, {}, None


# =============================================================================
# 市場過濾工具
# =============================================================================

def filter_by_market(stock_data: dict, stock_info: dict, market: str) -> Tuple[dict, dict]:
    """
    依市場過濾股票資料
    
    Args:
        market: 'global', 'us', 'tw'
    
    Returns:
        (filtered_stock_data, filtered_stock_info)
    """
    if market == 'global':
        return stock_data, stock_info
    
    target_country = 'US' if market == 'us' else 'TW'
    filtered_symbols = {s for s, info in stock_info.items() 
                        if info.get('country') == target_country}
    
    filtered_data = {s: df for s, df in stock_data.items() if s in filtered_symbols}
    filtered_info = {s: info for s, info in stock_info.items() if s in filtered_symbols}
    
    logger.info(f"過濾後: {len(filtered_data)} 檔 {target_country} 股票")
    return filtered_data, filtered_info
