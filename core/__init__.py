"""
FinPackV2 核心模組（BTC-USD SMC 版）

提供以下功能：
- BTC-USD OHLCV 資料抓取與快取（data.py）
- Smart Money Concepts 指標計算（smc.py）
- 資料容器（container.py）
"""
from .config import (
    BASE_DIR, CACHE_DIR, BTC_CACHE_FILE,
    CACHE_MAX_STALENESS_DAYS,
    BTC_SYMBOL, DATA_PERIOD, FEES,
)
from .data import (
    fetch_btc_ohlcv,
    smart_load_btc,
    save_btc_cache,
    slice_ohlcv,
)
from .smc import (
    SmcIndicators, SmcSignals,
    FVG, OrderBlock, StructurePoint, LiquidityPool,
    detect_pivots, detect_structure, detect_fvgs,
    detect_order_blocks, detect_liquidity_pools,
)
from .container import BtcDataContainer, container
from .smc_service import SmcSignalService, smc_service
