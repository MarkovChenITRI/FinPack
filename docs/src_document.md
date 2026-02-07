# src/ 資料基礎設施層規範

> 本文件定義 `src/` 層的架構、職責與 API 規範，供開發者維護及擴充時參考。

---

## 一、設計架構

### 1.1 層級職責

`src/` 為**純資料層**，負責：資料取得、快取、對齊、指標計算。  
**禁止包含**：交易邏輯、回測演算、UI 互動（皆屬前端 JavaScript 職責）。

### 1.2 核心設計模式

| 模式 | 說明 |
|------|------|
| **Singleton** | `DataContainer` 為全域唯一實例，透過 `get_container()` 存取 |
| **快取優先** | 優先載入 pickle 快取，僅在不存在或明確刷新時才抓取 |
| **原始/衍生分離** | 原始 OHLCV 資料持久化；衍生指標（三大矩陣）每次啟動時重算 |

### 1.3 模組結構與資料流

```
src/
├── config.py       # 配置常數
├── data.py         # 外部資料取得 + 快取 I/O
├── align.py        # 日期對齊
├── indicator.py    # 衍生指標計算
└── __init__.py     # DataContainer Singleton（對外入口）
```

**資料流向**：
```
[yfinance/TradingView] → data.py → raw_data (pickle 快取)
                                       ↓
                               align.py → aligned_data, unified_dates
                                              ↓
                               indicator.py → sharpe_matrix, ranking_matrix, growth_matrix
                                                    ↓
                               DataContainer ← routes/ API 呼叫
```

---

## 二、配置定義（config.py）

所有常數集中於此，禁止在其他模組硬編碼。

| 配置項 | 類型 | 說明 |
|--------|------|------|
| `CACHE_DIR` | `Path` | 快取資料夾路徑 |
| `STOCK_CACHE_FILE` | `str` | 股票資料快取檔名 |
| `MARKET_CACHE_FILE` | `str` | 市場資料快取檔名 |
| `SHARPE_WINDOW` | `int` | Sharpe Ratio 滾動窗口（預設 252 交易日） |
| `RISK_FREE_RATE` | `float` | 年化無風險利率（預設 0.04） |
| `SLOPE_WINDOW` | `int` | 排名變化統計窗口 |
| `TRADINGVIEW_LIST_ID` | `str` | TradingView 觀察清單 ID |
| `MARKET_INDICES` | `List[str]` | 追蹤的市場指數代碼 |

---

## 三、資料來源（data.py）

### 3.1 核心函數

| 函數 | 返回值 | 用途 | 相依功能 |
|------|--------|------|----------|
| `fetch_watchlist()` | `(watchlist, stock_info)` | 從 TradingView 取得觀察清單與元資料 | `DataContainer.__init__` |
| `fetch_stock_history(ticker, period)` | `DataFrame` | 從 yfinance 取得單一股票 OHLCV | 內部使用 |
| `fetch_all_stock_data()` | `(raw_data, watchlist, stock_info)` | 批量抓取所有股票資料 | `DataContainer.load_or_fetch` |
| `load_stock_cache()` | `(raw_data, watchlist, stock_info, last_update)` | 從 pickle 載入快取 | `DataContainer.load_or_fetch` |
| `save_stock_cache(...)` | `None` | 將資料存入 pickle 快取 | `DataContainer.load_or_fetch` |
| `get_usd_twd_rate()` | `float` | 取得即時美元兌台幣匯率 | `routes/market.py` |

### 3.2 MarketDataLoader 類別

| 方法 | 返回值 | 用途 | 相依功能 |
|------|--------|------|----------|
| `get_index_data(symbol, period)` | `List[Dict]` | 取得單一指數 K 線數據 | `get_all_market_data` 內部 |
| `get_weighted_kline(symbols, weights, period)` | `List[Dict]` | 計算加權指數 K 線 | `DataContainer.get_kline` |
| `get_all_market_data(period)` | `Dict` | 取得所有市場指數面板資料 | `engine/routes/market.py` |

### 3.3 資料格式

| 結構 | 格式 |
|------|------|
| `raw_data` | `Dict[ticker: str, DataFrame(OHLCV)]`，index 為 datetime |
| `stock_info` | `Dict[ticker: str, {country, industry, provider}]` |
| `watchlist` | `Dict[industry: str, {provider: [codes]}]` |

---

## 四、日期對齊（align.py）

**函數**：`align_data_with_bfill(raw_data) → (aligned_data, unified_dates)`

**演算法**：
1. 取所有股票交易日的聯集
2. 過濾稀疏日期（僅保留多數股票有資料的日期）
3. 前向填補（bfill）缺失值
4. 返回對齊後的 `Dict` 與統一的 `DatetimeIndex`

**相依功能**：`DataContainer.load_or_fetch` → 作為指標計算前置步驟

---

## 五、衍生指標（indicator.py）

### 5.1 指標計算函數

| 函數 | 輸入 | 輸出 | 用途 | 相依功能 |
|------|------|------|------|----------|
| `calculate_sharpe(close_series)` | `Series` | `Series` | 計算滾動 Sharpe Ratio | 內部使用 |
| `calculate_ranking_matrix(sharpe_matrix)` | `DataFrame` | `DataFrame` | 計算每日 Sharpe 排名 | 內部使用 |
| `calculate_growth_matrix(ranking_matrix)` | `DataFrame` | `DataFrame` | 計算排名變化 | 內部使用 |
| `calculate_all_indicators(aligned_data)` | `Dict` | `(sharpe, ranking, growth)` | 計算所有衍生指標 | 初始化時呼叫 |

### 5.2 三大矩陣定義

| 矩陣 | 維度 | 數值意義 | 用途 | 相依功能 |
|------|------|----------|------|----------|
| `sharpe_matrix` | 日期 × 股票 | Sharpe Ratio 原始值 | 風險調整報酬評估 | `routes/stock.py` API |
| `ranking_matrix` | 日期 × 股票 | Sharpe 排名（1 = 最高） | Top-N 篩選、相對排名判斷 | `routes/stock.py` API |
| `growth_matrix` | 日期 × 股票 | 排名變化（正值 = 上升） | 成長動能判斷、Growth Top-N | `routes/stock.py` API |

### 5.3 公式定義

**Sharpe Ratio**（252 日滾動）：
$$\text{Sharpe} = \frac{\bar{R} - R_f}{\sigma_R} \times \sqrt{252}$$

- $\bar{R}$：窗口內日報酬均值
- $R_f$：日化無風險利率
- $\sigma_R$：窗口內日報酬標準差

**Growth**（排名變化）：
$$\text{Growth}_t = \text{Rank}_{t-1} - \text{Rank}_t$$

- 正值：排名上升（#20 → #10 = +10）
- 負值：排名下降

---

## 六、DataContainer API

### 6.1 Singleton 存取

```python
from src import get_container, refresh_container

container = get_container()      # 取得（懶載入）
container = refresh_container()  # 強制重載
```

### 6.2 屬性總覽

**原始資料（快取持久化）**：

| 屬性 | 類型 | 來源 |
|------|------|------|
| `raw_data` | `Dict[str, DataFrame]` | yfinance |
| `watchlist` | `Dict` | TradingView |
| `stock_info` | `Dict[str, Dict]` | TradingView |
| `last_update` | `datetime` | 系統時間 |

**衍生資料（啟動時計算）**：

| 屬性 | 類型 | 計算來源 |
|------|------|----------|
| `aligned_data` | `Dict[str, DataFrame]` | `align_data_with_bfill()` |
| `unified_dates` | `DatetimeIndex` | `align_data_with_bfill()` |
| `sharpe_matrix` | `DataFrame` | `calculate_all_indicators()` |
| `ranking_matrix` | `DataFrame` | `calculate_all_indicators()` |
| `growth_matrix` | `DataFrame` | `calculate_all_indicators()` |
| `slope_matrix` | `property` | **已棄用別名** → `growth_matrix` |

### 6.3 方法 API

#### 生命週期

| 方法 | 用途 | 相依功能 |
|------|------|----------|
| `load_or_fetch(force_refresh)` | 載入快取或重新抓取所有資料 | 初始化自動呼叫 |
| `refresh()` | 強制清除快取並重新抓取 | `routes/stock.py` `/api/cache/refresh` |

#### 股票查詢

| 方法 | 返回值 | 用途 | 相依功能 |
|------|--------|------|----------|
| `get_all_tickers()` | `List[str]` | 取得所有可用股票代碼 | `routes/stock.py` `/api/stocks` |
| `get_tickers_by_country(country)` | `List[str]` | 依國家（US/TW）篩選股票 | `routes/stock.py` |
| `get_tickers_by_industry(industry)` | `List[str]` | 依產業篩選股票 | `routes/stock.py` 產業篩選 |
| `get_industries()` | `List[str]` | 取得所有產業名稱清單 | `routes/stock.py` `/api/stocks/industries` |
| `get_stock_info(ticker)` | `Dict` | 取得單一股票元資料 | `routes/stock.py` |

#### 價格查詢

| 方法 | 返回值 | 用途 | 相依功能 |
|------|--------|------|----------|
| `get_stock_price(ticker, date)` | `Dict` | 取得指定日期的 OHLCV | `routes/stock.py` |
| `get_stock_ohlcv(ticker)` | `DataFrame` | 取得完整歷史 OHLCV | `routes/stock.py` K 線資料 |

#### Sharpe 查詢

| 方法 | 返回值 | 用途 | 相依功能 |
|------|--------|------|----------|
| `get_stock_sharpe(ticker)` | `Series` | 取得單一股票的 Sharpe 時間序列 | `routes/stock.py` |
| `get_sharpe_matrix(start, end)` | `DataFrame` | 取得指定日期範圍的 Sharpe 矩陣 | `routes/stock.py` `/api/industry/data` |
| `get_daily_sharpe_summary(date)` | `Dict` | 取得指定日期的 Sharpe 統計摘要 | `routes/stock.py` |

#### 排名/Growth 查詢

| 方法 | 返回值 | 用途 | 相依功能 |
|------|--------|------|----------|
| `get_ranking_matrix(start, end)` | `DataFrame` | 取得指定範圍的 Sharpe 排名矩陣 | `routes/stock.py` `/api/industry/data` |
| `get_growth_matrix(start, end)` | `DataFrame` | 取得指定範圍的排名變化矩陣 | `routes/stock.py` `/api/industry/data` |

#### 市場資料

| 方法 | 返回值 | 用途 | 相依功能 |
|------|--------|------|----------|
| `get_market_data(period)` | `Dict` | 取得所有市場指數面板資料 | `routes/market.py` |
| `get_kline(symbol, period)` | `List[Dict]` | 取得指定標的 K 線數據 | `routes/market.py` |
| `get_exchange_rate()` | `float` | 取得即時美元兌台幣匯率 | `routes/market.py` |

---

## 七、擴充規範

### 新增資料來源
1. `config.py` → 新增配置常數
2. `data.py` → 實作抓取/快取函數
3. `DataContainer` → 新增屬性與 getter

### 新增衍生指標
1. `indicator.py` → 實作計算函數
2. `calculate_all_indicators()` → 呼叫新函數並返回
3. `DataContainer` → 新增屬性儲存計算結果

### 新增股票篩選
- 命名：`get_tickers_by_*()` 或 `filter_tickers_by_*()`
- 返回：`List[str]`

---

## 八、禁止事項

| 禁止行為 | 原因 |
|----------|------|
| `src/` 引用 `routes/` | 資料層不得依賴路由層 |
| 直接操作 `_container` | 必須透過 `get_container()` |
| `src/` 實作交易邏輯 | 屬前端 JavaScript 職責 |
| 模組內硬編碼常數 | 須定義於 `config.py` |
| 繞過快取抓取資料 | 除非呼叫 `refresh()` |

---

## 九、驗證檢查點

修改 `src/` 後須驗證：

1. `get_container()` 正常取得實例
2. 三矩陣維度一致（日期 × 股票）且與 `unified_dates` 對齊
3. `growth_matrix` 正值 = 排名上升，負值 = 下降
4. 對齊後無 NaN（已填補）
5. 快取讀寫正常
