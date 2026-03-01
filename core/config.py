"""
FinPack 統一配置模組

集中管理所有配置參數，供 main.py 與 run.py 共用
"""
import os
import sys
from pathlib import Path

# =============================================================================
# 路徑設定
# =============================================================================
if getattr(sys, 'frozen', False):
    # PyInstaller 打包後：使用 exe 所在目錄
    BASE_DIR = Path(sys.executable).parent
else:
    # 開發模式：使用原始碼目錄（core/ 的父目錄）
    BASE_DIR = Path(__file__).parent.parent

CACHE_DIR = BASE_DIR / "cache"
STOCK_CACHE_FILE = CACHE_DIR / "stock_data.pkl"
MARKET_CACHE_FILE = CACHE_DIR / "market_data.pkl"

# =============================================================================
# 計算參數
# =============================================================================
SHARPE_WINDOW = 252         # Sharpe 計算視窗（天）
RISK_FREE_RATE = 0.04       # 無風險利率（年化）
DATA_PERIOD = '6y'          # 股票資料抓取期間

# =============================================================================
# 快取策略
# =============================================================================
CACHE_MAX_STALENESS_DAYS = 1        # 允許的最大過期天數
MARKET_CACHE_MAX_AGE_HOURS = 6      # 市場資料快取時效（小時）

# =============================================================================
# TradingView API 設定（可透過環境變數覆蓋）
# =============================================================================
TRADINGVIEW_WATCHLIST_ID = os.environ.get('TRADINGVIEW_WATCHLIST_ID', '118349730')
TRADINGVIEW_SESSION_ID = os.environ.get('TRADINGVIEW_SESSION_ID', 'm46y1452r9757tr6joce9qonjrnl88ia')

# =============================================================================
# 資料篩選
# =============================================================================
NON_TRADABLE_INDUSTRIES = frozenset({'Market Index', 'Index'})
MIN_STOCKS_FOR_VALID_DAY = 50           # 有效交易日最少股票數（絕對值）
MIN_STOCKS_FOR_VALID_DAY_RATIO = 0.5    # 有效交易日最少股票比例
MIN_HISTORY_DAYS = 100                   # 股票最少需要的歷史資料天數

# =============================================================================
# 手續費設定
# =============================================================================
FEES = {
    'us': {'rate': 0.003, 'min_fee': 15},
    'tw': {'rate': 0.006, 'min_fee': 0}
}
