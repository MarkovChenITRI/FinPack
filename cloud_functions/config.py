"""
Cloud Functions 配置
"""
from pathlib import Path
import os

# ===== 路徑設定 =====
BASE_DIR = Path(__file__).parent
CACHE_DIR = BASE_DIR / "cache"

# Google Cloud Storage 設定（可選）
GCS_BUCKET = os.environ.get('GCS_BUCKET', '')
GCS_CACHE_PREFIX = 'finpack_cache/'

# ===== 計算參數 =====
SHARPE_WINDOW = 252       # Sharpe 計算視窗（天）
RISK_FREE_RATE = 0.04     # 無風險利率
DATA_PERIOD = "6y"        # 股票資料抓取期間
BACKTEST_YEARS = 4        # 回測期間（年）

# ===== TradingView 設定 =====
TRADINGVIEW_WATCHLIST_ID = os.environ.get('TRADINGVIEW_WATCHLIST_ID', '118349730')
TRADINGVIEW_SESSION_ID = os.environ.get('TRADINGVIEW_SESSION_ID', 'b379eetq1pojcel6olyymmpo1rd41nng')

# ===== 不可交易的 industry 類型 =====
# 由 TradingView 分類決定，不再硬編碼特定 ticker
NON_TRADABLE_INDUSTRIES = {'Market Index', 'Index'}

# ===== 日期篩選 =====
MIN_STOCKS_FOR_VALID_DAY = 50  # 有效交易日最少股票數

# ===== 預設回測參數 =====
DEFAULT_BACKTEST_CONFIG = {
    # 基本參數
    'initial_capital': 1000000,
    'amount_per_stock': 100000,
    'max_positions': 10,
    'market': 'global',  # 'global', 'us', 'tw'
    'rebalance_freq': 'weekly',  # 'daily', 'weekly', 'monthly'
    
    # 買入條件
    'buy_conditions': {
        'sharpe_rank': {'enabled': True, 'top_n': 15},
        'sharpe_threshold': {'enabled': True, 'threshold': 1.0},
        'sharpe_streak': {'enabled': False, 'days': 3},
        'growth_streak': {'enabled': True, 'days': 2},
        'growth_rank': {'enabled': False, 'top_k': 7},
        'sort_sharpe': {'enabled': True},
        'sort_industry': {'enabled': False},
    },
    
    # 賣出條件
    'sell_conditions': {
        'sharpe_fail': {'enabled': True, 'periods': 2, 'top_n': 15},
        'growth_fail': {'enabled': False, 'days': 5},
        'not_selected': {'enabled': False, 'periods': 3},
        'drawdown': {'enabled': True, 'threshold': 0.40},
        'weakness': {'enabled': False, 'rank_k': 20, 'periods': 3},
    },
    
    # 再平衡策略
    'rebalance_strategy': {
        'type': 'delayed',  # 'immediate', 'batch', 'delayed', 'concentrated', 'none'
        'batch_ratio': 0.20,
        'concentrate_top_k': 3,
    }
}

# ===== 手續費 =====
FEES = {
    'us': {'rate': 0.003, 'min_fee': 15},
    'tw': {'rate': 0.006, 'min_fee': 0}
}
