"""
資料抓取模組（BTC-USD 版）

使用 yfinance 抓取 BTC-USD OHLCV 資料，支援多種時間框架。
快取策略：pickle 本地快取，max 1 天過期。
"""
import pickle
import logging
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
from typing import Optional, Tuple

from .config import CACHE_DIR, BTC_CACHE_FILE, CACHE_MAX_STALENESS_DAYS

logger = logging.getLogger(__name__)

# 支援的時間框架 → yfinance interval 對應
INTERVAL_MAP = {
    '1d':  '1d',
    '4h':  '1h',   # yfinance 無原生 4h，從 1h 重採樣
    '1h':  '1h',
}

# yfinance 各 interval 可取得的最長歷史
MAX_PERIOD = {
    '1d': '10y',
    '1h': '730d',
}


# =============================================================================
# BTC-USD 資料抓取
# =============================================================================

def fetch_btc_ohlcv(
    symbol: str = 'BTC-USD',
    timeframe: str = '1d',
    period: str = None,
    start: str = None,
    end: str = None,
) -> pd.DataFrame:
    """
    抓取 BTC-USD OHLCV 資料

    Args:
        symbol:    yfinance 代碼（預設 'BTC-USD'）
        timeframe: '1d' | '4h' | '1h'
        period:    yfinance period 字串，例如 '2y'（與 start/end 二擇一）
        start:     開始日期字串 'YYYY-MM-DD'
        end:       結束日期字串 'YYYY-MM-DD'

    Returns:
        DataFrame: columns=[Open, High, Low, Close, Volume]，Index=DatetimeIndex
    """
    if timeframe not in INTERVAL_MAP:
        raise ValueError(f'timeframe 必須是 {list(INTERVAL_MAP)} 之一，收到: {timeframe!r}')

    yf_interval = INTERVAL_MAP[timeframe]
    default_period = MAX_PERIOD.get(yf_interval, '2y')

    try:
        ticker = yf.Ticker(symbol)
        if start:
            df = ticker.history(interval=yf_interval, start=start, end=end)
        else:
            df = ticker.history(interval=yf_interval, period=period or default_period)

        if df.empty:
            logger.warning(f'yfinance 未返回 {symbol} 資料')
            return pd.DataFrame()

        df = df.tz_localize(None) if df.index.tz is not None else df
        df = df.sort_index()
        df = df[['Open', 'High', 'Low', 'Close', 'Volume']]

        # 4h 重採樣
        if timeframe == '4h':
            df = _resample_to_4h(df)

        logger.info(f'[DATA] {symbol} {timeframe}: {len(df)} 根 K 線 '
                    f'({str(df.index[0])[:10]} ~ {str(df.index[-1])[:10]})')
        return df

    except Exception as e:
        logger.error(f'抓取 {symbol} 失敗: {e}')
        return pd.DataFrame()


def _resample_to_4h(df_1h: pd.DataFrame) -> pd.DataFrame:
    """將 1H 資料重採樣為 4H"""
    return df_1h.resample('4h').agg({
        'Open':   'first',
        'High':   'max',
        'Low':    'min',
        'Close':  'last',
        'Volume': 'sum',
    }).dropna(subset=['Open', 'Close'])


# =============================================================================
# 快取操作（與原有系統相同模式）
# =============================================================================

def load_btc_cache(timeframe: str) -> Tuple[Optional[pd.DataFrame], Optional[datetime]]:
    """
    載入 BTC 快取

    Returns:
        (df, last_update) 或 (None, None)
    """
    cache_file = _get_cache_path(timeframe)

    if not cache_file.exists():
        return None, None

    try:
        with open(cache_file, 'rb') as f:
            cache = pickle.load(f)

        df          = cache.get('df')
        last_update = cache.get('last_update')

        if df is None or df.empty:
            return None, None

        # 檢查時效
        if last_update:
            data_date = df.index[-1].date()
            days_diff = (datetime.now().date() - data_date).days
            if days_diff > CACHE_MAX_STALENESS_DAYS:
                logger.warning(f'[CACHE] BTC {timeframe} 快取已過期 ({days_diff}d)')
                return None, None

        logger.info(f'[CACHE] 載入 BTC {timeframe} 快取: {len(df)} 根')
        return df, last_update

    except Exception as e:
        logger.warning(f'[CACHE] 讀取失敗: {e}')
        return None, None


def save_btc_cache(df: pd.DataFrame, timeframe: str) -> None:
    """儲存 BTC 快取"""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file = _get_cache_path(timeframe)

    try:
        cache = {'df': df, 'last_update': datetime.now()}
        with open(cache_file, 'wb') as f:
            pickle.dump(cache, f)
        logger.info(f'[CACHE] 已儲存 BTC {timeframe} 快取: {len(df)} 根')
    except Exception as e:
        logger.error(f'[CACHE] 儲存失敗: {e}')


def smart_load_btc(
    symbol: str = 'BTC-USD',
    timeframe: str = '1d',
    period: str = None,
    start: str = None,
    end: str = None,
    use_cache: bool = False,
) -> pd.DataFrame:
    """
    智慧載入策略：
    1. use_cache=True → 強制使用本地快取（debug 模式）
    2. 先檢查快取是否過期
    3. 若過期則從 yfinance 抓取並更新快取
    4. 抓取失敗時 fallback 使用舊快取

    Returns:
        DataFrame 或空 DataFrame
    """
    if use_cache:
        df, _ = load_btc_cache(timeframe)
        if df is not None:
            return df
        logger.warning('[DEBUG] 快取不存在，嘗試即時抓取...')

    # 檢查快取
    df, _ = load_btc_cache(timeframe)
    if df is not None:
        return df

    # 從 yfinance 抓取
    logger.info(f'[DATA] 從 yfinance 抓取 {symbol} {timeframe}...')
    df = fetch_btc_ohlcv(symbol, timeframe, period, start, end)

    if not df.empty:
        save_btc_cache(df, timeframe)
        return df

    # fallback：嘗試讀取舊快取（不論時效）
    cache_file = _get_cache_path(timeframe)
    if cache_file.exists():
        logger.warning('[DATA] 抓取失敗，使用舊快取...')
        try:
            with open(cache_file, 'rb') as f:
                cache = pickle.load(f)
            old_df = cache.get('df')
            if old_df is not None and not old_df.empty:
                logger.info(f'[DATA] 使用舊快取: {len(old_df)} 根')
                return old_df
        except Exception:
            pass

    logger.error('[DATA] 無法取得 BTC 資料')
    return pd.DataFrame()


# =============================================================================
# 工具函數
# =============================================================================

def _get_cache_path(timeframe: str):
    """取得對應 timeframe 的快取路徑"""
    return BTC_CACHE_FILE.parent / f'btc_{timeframe}.pkl'


def slice_ohlcv(df: pd.DataFrame, start: str, end: str = None) -> pd.DataFrame:
    """
    裁切 OHLCV 資料到指定日期範圍

    Args:
        df:    OHLCV DataFrame
        start: 開始日期 'YYYY-MM-DD'
        end:   結束日期 'YYYY-MM-DD'（None = 最後一天）

    Returns:
        裁切後的 DataFrame（含 start 和 end）
    """
    if df.empty:
        return df

    mask = df.index >= pd.Timestamp(start)
    if end:
        mask &= df.index <= pd.Timestamp(end)

    return df[mask].copy()
