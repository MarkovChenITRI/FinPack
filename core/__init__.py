"""
FinPack 核心模組

共用資料處理與指標計算功能，供 main.py 與 run.py 共同使用
"""
from .config import (
    # 路徑
    BASE_DIR, CACHE_DIR, STOCK_CACHE_FILE, MARKET_CACHE_FILE,
    # 計算參數
    SHARPE_WINDOW, RISK_FREE_RATE, DATA_PERIOD,
    # 快取策略
    CACHE_MAX_STALENESS_DAYS, MARKET_CACHE_MAX_AGE_HOURS,
    # TradingView
    TRADINGVIEW_WATCHLIST_ID, TRADINGVIEW_SESSION_ID,
    # 資料篩選
    NON_TRADABLE_INDUSTRIES, MIN_STOCKS_FOR_VALID_DAY, MIN_STOCKS_FOR_VALID_DAY_RATIO,
    MIN_HISTORY_DAYS,
    # 後端參數
    FEES,
)
from .data import (
    fetch_watchlist, fetch_stock_history, fetch_all_stock_data,
    load_stock_cache, load_stock_cache_raw, save_stock_cache,
    smart_load_or_fetch,
)
from .align import align_data_with_bfill, align_close_prices
from .indicator import (
    calculate_sharpe, calculate_ranking_matrix, calculate_growth_matrix,
    calculate_all_indicators, compute_daily_ranks_by_country, Indicators,
)
from .currency import (
    Money, Currency, CurrencyMismatchError,
    twd, usd, FX,
)
from .container import (
    DataContainer, container,
    build_close_df, filter_by_market,
)
from .market import MarketDataLoader
