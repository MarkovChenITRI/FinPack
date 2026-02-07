"""
FinPack 配置參數

包含：快取路徑、計算參數、TradingView 設定
"""
from pathlib import Path

# ===== 路徑設定 =====
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

# ===== 市場指數清單 =====
MARKET_INDICES = [
    ('^IXIC', 'NASDAQ', 'US'),      # NASDAQ 指數
    ('^TWII', 'TWSE', 'TW'),        # 台灣加權指數
    ('GC=F', 'CME', 'US'),          # 黃金期貨
    ('BTC-USD', 'CRYPTO', 'US'),    # 比特幣
    ('TLT', 'NYSE', 'US'),          # 美國20年期公債 ETF
]

# ===== 日期篩選 =====
MIN_STOCKS_FOR_VALID_DAY = 50  # 有效交易日最少股票數
