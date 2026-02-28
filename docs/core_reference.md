# core/ 模組參考文件

> 取代舊版 `src_document.md`（原文件已移至 `docs/backup/`）
> 最後更新：2026-02

---

## 一、設計架構

### 1.1 層級職責

`core/` 為**純資料層**，負責：資料取得、快取、日期對齊、指標計算、幣別處理。

**禁止包含**：交易邏輯、回測演算、Flask 路由（皆屬其他層職責）。

### 1.2 核心設計模式

| 模式 | 說明 |
|------|------|
| **Singleton** | `DataContainer` 在模組載入時建立全域實例，透過 `from core import container` 存取 |
| **快取優先** | 優先載入 pickle 快取，僅在快取過期或強制刷新時才抓取新資料 |
| **原始/衍生分離** | 原始 OHLCV 持久化至 pickle；衍生指標（三大矩陣）每次啟動時重新計算 |

### 1.3 模組結構與資料流

```
core/
├── config.py       # 配置常數
├── currency.py     # Money 幣別類型 + FX 匯率
├── data.py         # 外部資料取得 + 快取 I/O
├── align.py        # 日期對齊
├── indicator.py    # 衍生指標計算
├── market.py       # MarketDataLoader（市場指數、匯率快取）
├── container.py    # DataContainer singleton + 工具函數
└── __init__.py     # 統一匯出介面
```

**資料流向**：
```
[TradingView API] → data.py    → watchlist, stock_info
[yfinance]        → data.py    → raw_data (pickle 快取)
[yfinance]        → market.py  → market_data (pickle 快取)
                                  ↓
                          align.py → aligned_data, unified_dates
                                          ↓
                          indicator.py → sharpe_matrix, ranking_matrix, growth_matrix
                                                ↓
                          DataContainer ← 路由層 API 呼叫
```

---

## 二、配置定義（config.py）

所有常數集中於此，禁止在其他模組硬編碼。

| 配置項 | 類型 | 預設值 | 說明 |
|--------|------|--------|------|
| `CACHE_DIR` | `Path` | `./cache/` | 快取資料夾路徑 |
| `STOCK_CACHE_FILE` | `Path` | `cache/stock_data.pkl` | 股票資料快取路徑 |
| `MARKET_CACHE_FILE` | `Path` | `cache/market_data.pkl` | 市場資料快取路徑 |
| `SHARPE_WINDOW` | `int` | 252 | Sharpe Ratio 滾動視窗（交易日數） |
| `RISK_FREE_RATE` | `float` | 0.04 | 年化無風險利率 |
| `DATA_PERIOD` | `str` | `'6y'` | yfinance 資料抓取期間 |
| `CACHE_MAX_STALENESS_DAYS` | `int` | 1 | 快取過期門檻（天） |
| `NON_TRADABLE_INDUSTRIES` | `Set[str]` | 見 config.py | TradingView 不可交易分類 |
| `MIN_STOCKS_FOR_VALID_DAY` | `int` | 50 | 有效交易日最少股票數 |
| `FEES['US']` | `dict` | rate=0.003, min=$15 | 美股手續費 |
| `FEES['TW']` | `dict` | rate=0.006 | 台股手續費 |

---

## 三、幣別系統（currency.py）

### 3.1 Money 類型

```python
from core.currency import Money, Currency, twd, usd

# 建立金額
initial = twd(1_000_000)  # Money(amount=1000000, currency=Currency.TWD)
price   = usd(150.50)     # Money(amount=150.5,   currency=Currency.USD)

# 算術運算（同幣別才合法）
total = twd(500_000) + twd(300_000)   # OK → twd(800000)
diff  = usd(200) - usd(50)            # OK → usd(150)
# bad = twd(100) + usd(50)            # → CurrencyMismatchError

# 常用屬性
initial.amount    # 1000000.0 (float)
initial.currency  # Currency.TWD
initial.is_twd()  # True
initial.is_usd()  # False
```

### 3.2 FX 匯率（FX 類別）

```python
from core.currency import FX, usd, twd

fx = FX(use_cache=True)   # 從 pickle 快取載入歷史匯率；快取不存在時使用預設率

# 查詢特定日期匯率（USD/TWD）
rate = fx.rate('2025-01-15')   # float，約 32.5

# 幣別轉換
amount_twd = fx.to_twd(usd(1000), '2025-01-15')     # twd(32500)
amount_usd = fx.to_usd(twd(100_000), '2025-01-15')  # usd(3076.92)

# 字串表示
str(fx)   # 顯示當前匯率與資料範圍
```

**注意**：`FX` 的匯率歷史儲存在 `cache/market_data.pkl`（由 `MarketDataLoader` 填充），若快取不存在則使用預設匯率 32.0 TWD/USD。

---

## 四、資料來源（data.py）

### 4.1 核心函數

| 函數 | 返回值 | 用途 |
|------|--------|------|
| `fetch_watchlist()` | `(watchlist, stock_info)` | 從 TradingView 取得觀察清單與元資料 |
| `fetch_stock_history(ticker, period)` | `DataFrame` | 從 yfinance 取得單一股票 OHLCV |
| `fetch_all_stock_data()` | `(raw_data, watchlist, stock_info)` | 批量抓取所有股票資料 |
| `load_stock_cache()` | `(raw_data, watchlist, stock_info, last_update)` | 從 pickle 載入快取 |
| `save_stock_cache(raw_data, watchlist, stock_info)` | `None` | 將資料存入 pickle 快取 |
| `smart_load_or_fetch()` | `(raw_data, watchlist, stock_info, last_update)` | 快取優先策略（快取未過期則直接載入） |

### 4.2 資料格式

| 結構 | 格式 |
|------|------|
| `raw_data` | `Dict[str, DataFrame]`，key 為 ticker，DataFrame 含 OHLCV，index 為 DatetimeIndex |
| `stock_info` | `Dict[str, Dict]`，key 為 ticker，Dict 含 `{country, industry, provider}` |
| `watchlist` | `Dict[str, Dict]`，key 為 industry，Dict 含 `{provider: [codes]}` |

---

## 五、日期對齊（align.py）

### 主函數

```python
from core.align import align_data_with_bfill

aligned_data, unified_dates = align_data_with_bfill(raw_data)
```

**演算法步驟**：
1. 取所有股票交易日的**聯集**
2. 過濾**稀疏日期**（保留有至少 `MIN_STOCKS_FOR_VALID_DAY` 支股票資料的日期）
3. **前向填補**（forward-fill）缺失值
4. 返回對齊後的 `Dict` 與統一的 `DatetimeIndex`

### 輔助函數

```python
from core.align import align_close_prices

close_df = align_close_prices(raw_data)
# 簡化版，直接返回對齊後的收盤價 DataFrame
```

---

## 六、衍生指標（indicator.py）

### 6.1 函數層（純函數）

| 函數 | 輸入 | 輸出 | 說明 |
|------|------|------|------|
| `calculate_sharpe(close_series)` | `Series` | `Series` | 252 日滾動 Sharpe |
| `calculate_ranking_matrix(sharpe_matrix)` | `DataFrame` | `DataFrame` | 每日 Sharpe 排名（1=最高） |
| `calculate_growth_matrix(ranking_matrix)` | `DataFrame` | `DataFrame` | 排名變化（正值=上升） |
| `calculate_all_indicators(aligned_data)` | `Dict` | `(sharpe, ranking, growth)` | 一次計算三矩陣 |

### 6.2 Indicators 類別（OOP 介面）

```python
from core.indicator import Indicators

indicators = Indicators(close_df, stock_info)

# 懶載入屬性（首次存取時計算）
indicators.sharpe                  # DataFrame：Sharpe 矩陣
indicators.rank                    # DataFrame：排名矩陣
indicators.growth                  # DataFrame：Growth 矩陣
indicators.sharpe_rank_by_country  # Dict[str, DataFrame]：依國家分組的排名
indicators.growth_rank_by_country  # Dict[str, DataFrame]：依國家分組的 Growth 排名
```

### 6.3 公式定義

**Sharpe Ratio**（252 日滾動）：

$$\text{Sharpe} = \frac{\bar{R} - R_f}{\sigma_R} \times \sqrt{252}$$

其中 $\bar{R}$ 為視窗內日報酬均值，$R_f$ 為日化無風險利率，$\sigma_R$ 為視窗內日報酬標準差。

**Growth**（排名變化）：

$$\text{Growth}_t = \text{Rank}_{t-1} - \text{Rank}_t$$

正值代表排名上升（例：#20 → #10 = Growth +10），負值代表下降。

---

## 七、DataContainer API（container.py）

### 7.1 存取方式

```python
from core import container          # 取得全域單例
from core.container import DataContainer  # 取得類別（需自行實例化）
```

> **注意**：不存在 `get_container()` 或 `refresh_container()` 函數，直接 import `container` 即可。

### 7.2 模組級工具函數

```python
from core.container import build_close_df, filter_by_market
# 或
from core import build_close_df, filter_by_market

# 建立收盤價矩陣
close_df = build_close_df(aligned_data)
# aligned_data: Dict[str, DataFrame]
# 返回: DataFrame [Date × Symbol]

# 依市場過濾
filtered_close, filtered_info = filter_by_market(close_df, stock_info, market)
# market: 'us' | 'tw' | 'global'
```

### 7.3 DataContainer 屬性

**原始資料（快取持久化）**：

| 屬性 | 類型 | 說明 |
|------|------|------|
| `raw_data` | `Dict[str, DataFrame]` | yfinance 原始 OHLCV |
| `watchlist` | `Dict` | TradingView 觀察清單 |
| `stock_info` | `Dict[str, Dict]` | 股票元資料（country/industry） |
| `last_update` | `datetime` | 最後更新時間 |
| `initialized` | `bool` | 初始化是否完成 |

**衍生資料（每次啟動時計算）**：

| 屬性 | 類型 | 說明 |
|------|------|------|
| `aligned_data` | `Dict[str, DataFrame]` | 日期對齊後的 OHLCV |
| `unified_dates` | `DatetimeIndex` | 統一的交易日序列 |
| `sharpe_matrix` | `DataFrame` | 全股票 Sharpe 矩陣 |
| `ranking_matrix` | `DataFrame` | 全股票排名矩陣 |
| `growth_matrix` | `DataFrame` | 全股票 Growth 矩陣 |
| `fx` | `FX` | 匯率服務實例 |
| `market_loader` | `MarketDataLoader` | 市場指數與匯率快取服務（`core/market.py`） |

### 7.4 DataContainer 方法

#### 生命週期

| 方法 | 說明 |
|------|------|
| `load_or_fetch(force_refresh=False)` | 載入快取或重新抓取全部資料，`auto_load=True` 時在 `__init__` 自動呼叫 |
| `refresh()` | 強制重新抓取資料 |

#### 收盤價矩陣

| 方法 | 返回值 | 說明 |
|------|--------|------|
| `get_close_df(market='global')` | `DataFrame` | 取得收盤價矩陣，可依市場過濾 |
| `get_filtered_stock_info(market='global')` | `dict` | 取得過濾後的股票資訊 |

#### 股票查詢

| 方法 | 返回值 | 說明 |
|------|--------|------|
| `get_all_tickers()` | `List[str]` | 所有可用股票代碼 |
| `get_tickers_by_country(country)` | `List[str]` | 依國家（'US'/'TW'）篩選 |
| `get_tickers_by_industry(industry)` | `List[str]` | 依產業篩選 |
| `get_industries()` | `List[str]` | 所有產業名稱 |
| `get_stock_info(ticker)` | `Dict` | 單一股票元資料 |

#### 價格查詢

| 方法 | 返回值 | 說明 |
|------|--------|------|
| `get_stock_price(ticker, date)` | `Dict` | 指定日期 OHLCV（dict 格式） |
| `get_stock_ohlcv(ticker)` | `DataFrame` | 完整歷史 OHLCV（string index） |

#### Sharpe / 排名 / Growth 查詢

| 方法 | 返回值 | 說明 |
|------|--------|------|
| `get_stock_sharpe(ticker)` | `Series` | 單一股票 Sharpe 時間序列 |
| `get_sharpe_matrix(start_date, end_date)` | `DataFrame` | 指定範圍 Sharpe 矩陣 |
| `get_ranking_matrix(start_date, end_date)` | `DataFrame` | 指定範圍排名矩陣 |
| `get_growth_matrix(start_date, end_date)` | `DataFrame` | 指定範圍 Growth 矩陣 |
| `get_daily_sharpe_summary(date)` | `Dict` | 指定日期按國家分組的 Sharpe 摘要 |

#### 市場資料（委派至 market_loader）

| 方法 | 返回值 | 說明 |
|------|--------|------|
| `get_market_data(period, aligned_data=None)` | `Dict` | 取得所有市場指數面板資料 |
| `get_kline(symbol, period, aligned_data=None)` | `List[Dict]` | 取得單一標的 K 線 |
| `get_exchange_rate()` | `float` | 取得當前 USD/TWD 匯率 |
| `get_exchange_rate_history(period)` | `Dict[str, float]` | 取得歷史匯率 `{date_str: rate}` |

---

## 八、MarketDataLoader（core/market.py）

```python
from core.market import MarketDataLoader
# 或透過 container 直接使用委派方法（推薦）
from core import container
container.get_market_data(period)
```

`MarketDataLoader` 於 `DataContainer.__init__` 中自動實例化（僅讀快取，無網路）。
`main.py` 在啟動時呼叫 `container.market_loader.preload_all()` 更新快取（有網路，含 `max_staleness_days=1` 保護）。

| 方法 | 返回值 | 說明 |
|------|--------|------|
| `preload_all(aligned_data, max_staleness_days=1)` | `None` | 從 yfinance 更新市場資料快取（有網路） |
| `get_weighted_kline(symbol, period, aligned_data)` | `List[Dict]` | 取得加權指數 K 線 |
| `get_all_market_data(period, aligned_data)` | `Dict` | 取得所有市場指數面板資料 |
| `get_exchange_rate()` | `float` | 取得最新匯率 |
| `get_exchange_rate_history(period)` | `Dict` | 取得歷史匯率 |

**快取符號**：`^IXIC`（NASDAQ）、`^TWII`（台灣加權）、`GC=F`（黃金）、`BTC-USD`（比特幣）、`TLT`（長期債券）、`^GSPC`（S&P 500）、`TWD=X`（匯率）

---

## 九、擴充規範

### 新增資料來源
1. `config.py` → 新增配置常數
2. `data.py` → 實作抓取/快取函數
3. `DataContainer` → 新增屬性與 getter 方法
4. `core/__init__.py` → 加入匯出

### 新增衍生指標
1. `indicator.py` → 實作計算函數
2. `calculate_all_indicators()` → 呼叫新函數並返回
3. `DataContainer` → 新增屬性儲存計算結果

### 新增股票篩選
- 命名：`get_tickers_by_*()`
- 返回：`List[str]`

---

## 十、驗證檢查點

修改 `core/` 後確認：
1. `from core import container` 正常取得已初始化的實例
2. `container.initialized == True`
3. 三矩陣維度一致（日期 × 股票）且與 `unified_dates` 對齊
4. `growth_matrix` 正值 = 排名上升，負值 = 下降
5. 對齊後資料無過多 NaN（已填補）
6. 快取讀寫正常（pickle 版本相容）
