"""
FinPack 配置參數

包含：快取路徑、計算參數、TradingView 設定
"""
import sys
from pathlib import Path

# ===== 路徑設定 =====
if getattr(sys, 'frozen', False):
    # PyInstaller 打包後：使用 exe 所在目錄
    BASE_DIR = Path(sys.executable).parent
else:
    # 開發模式：使用原始碼目錄
    BASE_DIR = Path(__file__).parent.parent

CACHE_DIR = BASE_DIR / "cache"
STOCK_CACHE_FILE = CACHE_DIR / "stock_data.pkl"
MARKET_CACHE_FILE = CACHE_DIR / "market_data.pkl"

# ===== 計算參數 =====
SHARPE_WINDOW = 252       # Sharpe 計算視窗（天）
RISK_FREE_RATE = 0.04     # 無風險利率
DATA_PERIOD = "6y"        # 股票資料抓取期間

# ===== TradingView 設定 =====
TRADINGVIEW_WATCHLIST_ID = "118349730"
TRADINGVIEW_SESSION_ID = "b379eetq1pojcel6olyymmpo1rd41nng"

# ===== 市場數據快取 =====
MARKET_CACHE_MAX_AGE_HOURS = 6

# ===== 不可交易的 industry 類型 =====
# 由 TradingView 分組名稱決定，不再硬編碼特定 ticker
NON_TRADABLE_INDUSTRIES = {'Market Index', 'Index'}

# ===== 日期篩選 =====
MIN_STOCKS_FOR_VALID_DAY = 50  # 有效交易日最少股票數
