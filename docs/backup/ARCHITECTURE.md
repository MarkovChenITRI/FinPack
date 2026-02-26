# FinPack 架構設計 v3（後端計算版）

## 設計理念

**後端計算**：回測邏輯在 Python 後端執行，前端負責 UI 呈現與參數配置。

**貨幣安全**：所有金額使用 `Money` 類型，強制幣別檢查，避免 TWD/USD 混用錯誤。

**匯率自動處理**：`FX` 類別提供日期對應匯率，買賣美股時自動轉換。

---

## 目錄結構

```
FinPack/
├── main.py                    # Flask Web 服務入口
├── run.py                     # CLI 回測入口（開發用）
├── requirements.txt           # pip 套件相依
├── pyproject.toml             # 專案元資訊
├── build.ps1                  # PyInstaller 打包腳本
│
├── core/                      # 📦 核心業務邏輯
│   ├── __init__.py
│   ├── config.py              # 統一配置（路徑、參數、手續費）
│   ├── currency.py            # Money 類型、FX 匯率轉換
│   ├── data.py                # yfinance 抓取 + pickle 快取
│   ├── align.py               # 日期對齊（前向填充）
│   └── indicator.py           # 指標計算（Sharpe、Growth、排名）
│
├── backtest/                  # 📊 回測引擎
│   ├── __init__.py            # 匯出 BacktestEngine、format_backtest_report
│   ├── engine.py              # 回測主程式（買賣執行、權益計算）
│   └── report.py              # 回測結果格式化
│
├── web/                       # 🌐 Flask Web 應用
│   ├── __init__.py            # DataContainer 單例
│   ├── container.py           # 資料容器（快取 + 指標）
│   ├── market.py              # 市場資料載入器（指數、匯率）
│   └── routes/                # API 路由
│       ├── __init__.py
│       ├── market.py          # /api/market-data, /api/kline/<symbol>
│       ├── stock.py           # /api/stocks, /api/industry/data
│       └── backtest.py        # /api/backtest/run, /api/backtest/config
│
├── static/                    # 前端靜態檔案
│   ├── css/style.css
│   └── js/
│       ├── app.js             # 應用入口
│       ├── config.js          # API 端點配置
│       ├── api/               # API 呼叫封裝
│       ├── components/        # UI 元件（圖表等）
│       └── utils/             # 工具函數
│
├── templates/
│   └── index.html             # SPA 單頁入口
│
├── cache/                     # 資料快取目錄
│   ├── stock_data.pkl         # 股票資料快取
│   └── market_data.pkl        # 市場指數快取
│
├── tests/                     # 單元測試
│   ├── test_currency.py
│   ├── test_engine_integration.py
│   └── ...
│
└── docs/                      # 文件
    ├── ARCHITECTURE.md        # 本文件
    └── ...
```

---

## 層級職責

### 後端（Python）

| 層級 | 職責 |
|------|------|
| `core/` | 資料抓取、快取、指標計算、幣別處理 |
| `backtest/` | 回測邏輯：買賣條件、再平衡、權益追蹤 |
| `web/routes/` | 提供 JSON API，執行回測並回傳結果 |

### 前端（JavaScript）

| 層級 | 職責 |
|------|------|
| `api/` | 呼叫後端 API |
| `components/` | 圖表、表格等 UI 元件 |
| `utils/` | 格式化、快取工具 |

---

## 貨幣系統

### Money 類型

```python
from core.currency import twd, usd, Money

# 建立金額
initial = twd(1_000_000)   # $1,000,000 TWD
price = usd(150.50)        # $150.50 USD

# 加減法（同幣別安全）
total = twd(100) + twd(200)  # OK
# mixed = twd(100) + usd(50)  # CurrencyMismatchError
```

### FX 匯率轉換

```python
from core.currency import FX, usd, twd

fx = FX(use_cache=True)

# 查詢特定日期匯率
rate = fx.rate('2025-01-15')  # 約 32.5

# 轉換幣別
amount_usd = usd(1000)
amount_twd = fx.to_twd(amount_usd, '2025-01-15')  # twd(32500)

budget_twd = twd(100_000)
budget_usd = fx.to_usd(budget_twd, '2025-01-15')  # usd(3076.92)
```

---

## API 路由

### /api/backtest/run (POST)

執行回測，回傳績效指標與權益曲線。

**Request:**
```json
{
  "initial_capital": 1000000,
  "amount_per_stock": 100000,
  "max_positions": 10,
  "market": "us",
  "start_date": "2025-01-01",
  "end_date": "2025-06-30",
  "buy_conditions": {
    "sharpe_rank": {"enabled": true, "top_n": 15},
    "sharpe_threshold": {"enabled": true, "threshold": 1.0}
  },
  "sell_conditions": {
    "drawdown": {"enabled": true, "threshold": 0.40}
  },
  "rebalance_strategy": {
    "type": "delayed",
    "top_n": 5,
    "sharpe_threshold": 0
  }
}
```

**Response:**
```json
{
  "success": true,
  "result": {
    "metrics": {
      "initial_capital": 1000000,
      "final_equity": 1150000,
      "total_return": 15.0,
      "annualized_return": 30.5,
      "max_drawdown": 8.5,
      "sharpe_ratio": 1.25,
      "win_rate": 62.5,
      "total_trades": 24
    },
    "equity_curve": [
      {"date": "2025-01-02", "equity": 1000000, "cash": 500000, ...}
    ],
    "benchmark_curve": [
      {"date": "2025-01-02", "equity": 1000000}
    ],
    "benchmark_name": "NASDAQ",
    "trades": [...],
    "current_holdings": [...]
  }
}
```

### /api/market-data (GET)

市場看板資料。

### /api/kline/\<symbol\> (GET)

單一標的 K 線資料。

### /api/stocks (GET)

股票清單。

### /api/industry/data (GET)

產業分析資料（含 Sharpe/Growth 排名）。

---

## 回測引擎

### 條件類型

**買入條件（交集）：**
- `sharpe_rank`: Sharpe 排名前 N
- `sharpe_threshold`: Sharpe 高於門檻
- `sharpe_streak`: 連續在 Top-N
- `growth_rank`: Growth 排名前 N
- `growth_streak`: 連續 Growth 達標
- `sort_sharpe`: 依 Sharpe 排序
- `sort_industry`: 產業分散

**賣出條件（聯集）：**
- `sharpe_fail`: 連續 N 期未入 Top-K
- `growth_fail`: Growth 連續為負
- `not_selected`: 連續未被選中
- `drawdown`: 回撤超過門檻
- `weakness`: 持續弱勢

**再平衡策略：**
- `immediate`: 立即執行
- `batch`: 分批進場
- `delayed`: 延遲確認
- `concentrated`: 集中投資
- `none`: 不再平衡

### 執行流程

```
每個交易日:
  1. _calc_equity() → 計算當前總資產
  2. _check_rebalance_day() → 是否為再平衡日
  3. _evaluate_sells() → 檢查賣出條件
  4. _execute_sells() → 執行賣出
  5. _evaluate_buys() → 選股 + 檢查再平衡策略
  6. _execute_buys() → 執行買入
  7. 記錄權益曲線
```

---

## 入口點

### main.py（Web 服務）

```bash
python main.py
# 啟動 Flask 伺服器，預設 http://localhost:5000
```

### run.py（CLI 回測）

```bash
python run.py --debug
# 使用快取資料執行回測，輸出結果到終端
```

---

## 配置說明

### core/config.py

| 參數 | 預設值 | 說明 |
|------|--------|------|
| `SHARPE_WINDOW` | 252 | Sharpe 計算視窗（天） |
| `RISK_FREE_RATE` | 0.04 | 無風險利率（年化） |
| `DATA_PERIOD` | '6y' | 資料抓取期間 |
| `CACHE_MAX_STALENESS_DAYS` | 1 | 快取過期天數 |

### web/routes/backtest.py

買賣條件與再平衡策略的預設參數定義在 `DEFAULT_CONFIG` 與 `CONDITION_OPTIONS`。

---

## 測試

```bash
# 執行所有測試
python -m pytest tests/

# 執行特定測試
python -m pytest tests/test_currency.py -v
python -m pytest tests/test_engine_integration.py -v
```
