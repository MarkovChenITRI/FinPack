# FinPack 架構設計 v3（Python 後端計算版）

> 最後更新：2026-02

---

## 設計理念

**後端計算**：回測邏輯完全在 Python 後端執行，前端（JavaScript）僅負責 UI 呈現與參數設定。

**貨幣安全**：所有金額使用 `Money` 類型強制幣別（TWD/USD）檢查，避免混用錯誤。

**匯率自動處理**：`FX` 類別提供日期對應匯率，美股交易時自動轉換。

**模組完全獨立**：`core` / `backtest` / `web` 三層零互相依賴，只有 `run.py` 和 `main.py` 作為組裝層。

---

## 目錄結構

```
FinPack/
│
├── core/                       # 模組 A：資料層（完全獨立）
│   ├── __init__.py             # 匯出 container, build_close_df, filter_by_market, Indicators, Money, twd, usd, FX
│   ├── config.py               # 系統常數（路徑、計算參數、手續費）
│   ├── currency.py             # Money, twd, usd, FX（匯率）
│   ├── data.py                 # 資料抓取與 pickle 快取
│   ├── align.py                # align_data_with_bfill（日期對齊）
│   ├── indicator.py            # Indicators 類別（Sharpe/排名/Growth）
│   └── container.py            # DataContainer singleton + build_close_df + filter_by_market
│
├── backtest/                   # 模組 B：回測引擎（完全獨立）
│   ├── __init__.py             # 匯出 BacktestEngine, BacktestResult, Trade, Position, TradeType, format_backtest_report
│   ├── config.py               # DEFAULT_CONFIG, CONDITION_OPTIONS, merge_config（唯一真相來源）
│   ├── engine.py               # BacktestEngine（買賣執行、權益追蹤）
│   └── report.py               # format_backtest_report（CLI 報告格式化）
│
├── web/                        # 模組 C：Flask Web 框架（完全獨立）
│   ├── __init__.py             # 匯出 MarketDataLoader
│   ├── market.py               # MarketDataLoader（市場指數、匯率快取）
│   └── routes/
│       ├── __init__.py         # 匯出 stock_bp, market_bp, backtest_bp
│       ├── stock.py            # /api/stocks, /api/industry/data
│       ├── market.py           # /api/market-data, /api/kline, /api/exchange-rate
│       └── backtest.py         # /api/backtest/run, /api/backtest/config
│
├── run.py                      # CLI 入口（組裝 core + backtest）
├── main.py                     # Web 入口（組裝 core + backtest + web）
│
├── static/                     # 前端靜態資產（CSS / JS）
├── templates/                  # HTML 模板（index.html）
├── cache/                      # pickle 快取目錄
│   ├── stock_data.pkl
│   └── market_data.pkl
├── tests/                      # 單元測試
└── docs/                       # 本文件目錄
    └── backup/                 # 舊版文件備份（v2 JS 架構）
```

---

## 模組依賴圖

```
     ┌─────────┐     ┌───────────┐     ┌─────────┐
     │  core/  │     │ backtest/ │     │  web/   │
     │(資料層) │     │ (引擎層)  │     │(路由層) │
     └────┬────┘     └─────┬─────┘     └────┬────┘
          │                │                │
          │    無互相依賴   │                │
          └────────┬───────┴────────┬───────┘
                   │                │
                   ▼                ▼
            ┌────────────┐   ┌────────────┐
            │   run.py   │   │  main.py   │
            │   (CLI)    │   │   (Web)    │
            │ core+back  │   │core+back+web│
            └────────────┘   └────────────┘
```

**禁止的依賴關係**：
- `core/` 不得引用 `backtest/` 或 `web/`
- `backtest/` 不得引用 `web/`
- 三模組之間不得互相直接呼叫

---

## 層級職責

### 一、core/（資料層）

| 檔案 | 職責 |
|------|------|
| `config.py` | 全域常數（路徑、Sharpe 視窗、無風險利率、手續費） |
| `currency.py` | `Money` 幣別安全類型、`FX` 匯率查詢 |
| `data.py` | yfinance/TradingView 資料抓取、pickle 快取讀寫 |
| `align.py` | 多股票日期對齊（前向填充） |
| `indicator.py` | Sharpe Ratio、排名矩陣、Growth 矩陣計算 |
| `container.py` | `DataContainer` singleton（統一資料存取介面）、`build_close_df()`、`filter_by_market()` |

### 二、backtest/（回測引擎層）

| 檔案 | 職責 |
|------|------|
| `config.py` | 條件選項（`CONDITION_OPTIONS`）、預設參數（`DEFAULT_CONFIG`）、`merge_config()` |
| `engine.py` | `BacktestEngine`：逐日買賣執行、持倉管理、績效計算 |
| `report.py` | `format_backtest_report()`：CLI 文字報告格式化 |

### 三、web/（路由層）

| 檔案 | 職責 |
|------|------|
| `market.py` | `MarketDataLoader`：市場指數 K 線快取（yfinance） |
| `routes/stock.py` | 股票清單、產業分析 API |
| `routes/market.py` | 市場看板、K 線、匯率 API |
| `routes/backtest.py` | 回測執行 API |

---

## 入口點

### main.py（Web 服務）

```python
# create_app() 工廠函數職責：
# 1. get_resource_path()          → 支援 PyInstaller 打包路徑
# 2. Flask(__name__, ...)         → 初始化 Flask
# 3. container（模組級 singleton）→ import 時自動初始化
# 4. register_blueprints()        → 掛載三個 Blueprint 至 /api
# 5. GET /                        → templates/index.html
# 6. GET /<path>                  → static/ 靜態資產
# 7. GET /api/health              → 健康檢查

python main.py
# 預設 http://localhost:5000
# 環境變數：PORT（埠號）、FLASK_DEBUG（除錯模式）
```

### run.py（CLI 回測）

```python
# FRONTEND_DEFAULTS：繼承 backtest/config.py 的 DEFAULT_CONFIG
# 並將 initial_capital / amount_per_stock 包裝為 twd(...)

# run_backtest(use_cache) 處理流程：
# 1. container（共用 singleton）在 import 時已自動初始化
# 2. build_close_df(container.aligned_data)         → 收盤價矩陣 [Date × Symbol]
# 3. filter_by_market(close_df, stock_info, market)  → 依市場過濾
# 4. Indicators(close_df, stock_info)               → 計算 sharpe / rank / growth
# 5. BacktestEngine(close_df, indicators, stock_info, config, fx)
# 6. engine.run(start_date, end_date)               → BacktestResult
# 7. format_backtest_report(...)                    → 輸出至終端

python run.py --debug   # --debug 使用快取資料（不重新抓取）
```

> **重要**：`run.py` 與 `main.py` 的回測處理流程完全一致，共用同一個 `container`、`build_close_df`、`filter_by_market`、`Indicators`、`BacktestEngine`，確保 CLI 與 Web API 結果相同。

---

## 貨幣系統

### Money 類型

```python
from core.currency import twd, usd, Money

initial = twd(1_000_000)   # $1,000,000 TWD
price   = usd(150.50)      # $150.50 USD

total = twd(100) + twd(200)   # OK
# mixed = twd(100) + usd(50)  # → CurrencyMismatchError（幣別不符）
```

### FX 匯率轉換

```python
from core.currency import FX, usd, twd

fx = FX(use_cache=True)

rate   = fx.rate('2025-01-15')                    # float，約 32.5
amount = fx.to_twd(usd(1000), '2025-01-15')       # twd(32500)
budget = fx.to_usd(twd(100_000), '2025-01-15')    # usd(3076.92)
```

---

## API 路由清單

| 方法 | 路由 | 說明 |
|------|------|------|
| GET | `/api/health` | 健康檢查 |
| GET | `/api/stocks` | 股票清單 |
| GET | `/api/industry/data` | 產業 Sharpe/Growth 分析 |
| GET | `/api/market-data` | 市場看板（NASDAQ/TWII/黃金/BTC 等）⚠️ |
| GET | `/api/kline/<symbol>` | 單一標的 K 線 ⚠️ |
| GET | `/api/exchange-rate` | 美元兌台幣匯率 ⚠️ |
| GET | `/api/market-status` | 最新資料日期狀態 ⚠️ |
| GET | `/api/date-info/<date>` | 指定日期市場資訊 ⚠️ |
| GET | `/api/backtest/config` | 取得條件選項與預設值 |
| POST | `/api/backtest/run` | 執行回測（benchmark 曲線部分失效 ⚠️）|

> ⚠️ 標示的路由目前有已知問題，詳見 [known_issues.md](known_issues.md)

---

## 配置說明

### core/config.py（系統常數）

| 參數 | 預設值 | 說明 |
|------|--------|------|
| `SHARPE_WINDOW` | 252 | Sharpe 滾動視窗（天） |
| `RISK_FREE_RATE` | 0.04 | 年化無風險利率 |
| `DATA_PERIOD` | `'6y'` | yfinance 抓取期間 |
| `CACHE_MAX_STALENESS_DAYS` | 1 | 快取過期天數 |
| `FEES['US']` | rate=0.003, min=$15 USD | 美股複委託手續費 |
| `FEES['TW']` | rate=0.006 | 台股手續費（含證交稅） |

### backtest/config.py（回測配置）

條件選項與預設參數的**唯一真相來源**。詳見 [strategy_guide.md](strategy_guide.md)。

---

## 已知問題

詳見 [known_issues.md](known_issues.md)

**摘要**：
- `container.get_market_data()` / `get_kline()` / `get_exchange_rate()` 等方法不存在，市場看板 API 全部失效
- `container.market_loader` 屬性未設定，benchmark 曲線計算失敗
- `CONDITION_OPTIONS` / `DEFAULT_CONFIG` 在 `backtest/config.py` 與 `web/routes/backtest.py` 重複定義

---

## 測試

```bash
python -m pytest tests/ -v
python -m pytest tests/test_currency.py -v
python -m pytest tests/test_engine_integration.py -v
python -m pytest tests/test_batch_strategy.py -v
```
