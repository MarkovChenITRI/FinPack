# web/ 路由層參考文件

> 最後更新：2026-02

---

## 一、架構概覽

```
web/
├── __init__.py        # 匯出 MarketDataLoader
├── market.py          # MarketDataLoader（市場指數、匯率快取）
└── routes/
    ├── __init__.py    # 匯出 stock_bp, market_bp, backtest_bp
    ├── stock.py       # 股票相關 API
    ├── market.py      # 市場看板 API
    └── backtest.py    # 回測執行 API
```

Flask 應用在 `main.py` 中透過 `register_blueprints()` 將三個 Blueprint 掛載至 `/api` 前綴。

---

## 二、MarketDataLoader（core/market.py）

`MarketDataLoader` 已移至 `core/market.py`（資料層）。`web/market.py` 現為薄 re-export，`web/__init__.py` 無需修改。

路由層透過 `container` 委派方法存取，無需直接 import `MarketDataLoader`：

```python
# 路由層推薦用法（透過 container）
from core import container
data = container.get_market_data(period)
kline = container.get_kline(symbol, period)
rate = container.get_exchange_rate()
```

### 預載符號

| 符號 | 說明 |
|------|------|
| `^IXIC` | NASDAQ 綜合指數 |
| `^TWII` | 台灣加權指數 |
| `GC=F` | 黃金期貨 |
| `BTC-USD` | 比特幣 |
| `TLT` | 美國長期公債 ETF |
| `^GSPC` | S&P 500 |
| `TWD=X` | 美元兌台幣匯率 |

快取更新由 `main.py` 啟動時呼叫 `container.market_loader.preload_all()`（含 `max_staleness_days=1` 保護）。詳見 [core_reference.md](core_reference.md#八marketdataloadercoremarketpy)。

---

## 三、API 路由詳細說明

### 3.1 stock_bp（routes/stock.py）

#### GET /api/stocks

取得股票清單與排名資訊。

**Query Parameters**：
| 參數 | 說明 | 預設值 |
|------|------|--------|
| `market` | `us` / `tw` / `global` | `global` |
| `top_n` | 返回前 N 名 | `50` |

**Response**：
```json
{
  "stocks": [
    {
      "ticker": "AAPL",
      "country": "US",
      "industry": "Technology",
      "sharpe": 1.23,
      "rank": 5,
      "growth": 3.2
    }
  ],
  "count": 50
}
```

#### GET /api/industry/data

取得按產業分組的 Sharpe/Growth 排名分析。

**Query Parameters**：
| 參數 | 說明 | 預設值 |
|------|------|--------|
| `market` | `us` / `tw` / `global` | `global` |
| `days` | 最近 N 天的資料 | `30` |

---

### 3.2 market_bp（routes/market.py）

#### GET /api/market-data

市場看板資料（NASDAQ/TWII/黃金/BTC/債券等 K 線）。

**Query Parameters**：
| 參數 | 說明 | 可用值 |
|------|------|--------|
| `period` | 時間範圍 | `1mo`, `3mo`, `6mo`, `1y`, `2y`, `5y`, `max` |

**預期 Response**：
```json
{
  "global": [...],
  "nasdaq": [...],
  "twii":   [...],
  "gold":   [...],
  "btc":    [...],
  "bonds":  [...],
  "period": "1y"
}
```

#### GET /api/kline/<symbol>

單一標的 K 線資料。

**Path Parameter**：`symbol` — 股票/指數代碼（如 `^IXIC`, `AAPL`）

**Query Parameters**：
| 參數 | 說明 | 預設值 |
|------|------|--------|
| `period` | 時間範圍 | `1y` |

**預期 Response**：
```json
{
  "symbol": "^IXIC",
  "data": [{"time": "2025-01-02", "open": 18000, "high": 18200, "low": 17900, "close": 18100, "volume": 123456}],
  "count": 252
}
```

#### GET /api/exchange-rate

美元兌台幣匯率查詢。

**Query Parameters**：
| 參數 | 說明 | 預設值 |
|------|------|--------|
| `history` | 是否返回歷史資料 | `false` |

**Response**（無 history）：
```json
{"rate": 31.44}
```

**Response**（有 history）：
```json
{
  "rate": 31.44,
  "history": {"2024-01-02": 31.5, "2024-01-03": 31.6},
  "count": 252
}
```

#### GET /api/market-status

各市場最新資料日期。

**Response**：
```json
{
  "us_latest_date": "2026-02-21",
  "tw_latest_date": "2026-02-21",
  "today": "2026-02-26"
}
```

#### GET /api/date-info/<date>

指定日期的美股/台股市場資訊。

---

### 3.3 backtest_bp（routes/backtest.py）

#### GET /api/backtest/config

取得可用的回測條件選項與預設值。

**Response**：
```json
{
  "options": { "buy_conditions": {...}, "sell_conditions": {...}, "rebalance_strategies": {...} },
  "defaults": { "initial_capital": 1000000, ... }
}
```

> `options` 和 `defaults` 直接來自 `backtest/config.py`（`CONDITION_OPTIONS`、`DEFAULT_CONFIG`），與回測引擎保持同步。

#### POST /api/backtest/run

執行回測。

**Request JSON**：
```json
{
  "initial_capital": 1000000,
  "amount_per_stock": 100000,
  "max_positions": 10,
  "market": "us",
  "start_date": "2025-01-01",
  "end_date": "2025-06-30",
  "backtest_months": 6,
  "rebalance_freq": "weekly",
  "buy_conditions": {
    "sharpe_rank": {"enabled": true, "top_n": 15},
    "sharpe_threshold": {"enabled": true, "threshold": 1.0},
    "growth_streak": {"enabled": true, "days": 2, "percentile": 30},
    "sort_sharpe": {"enabled": true}
  },
  "sell_conditions": {
    "sharpe_fail": {"enabled": true, "periods": 2, "top_n": 15},
    "drawdown": {"enabled": true, "threshold": 0.40}
  },
  "rebalance_strategy": {
    "type": "delayed",
    "top_n": 5,
    "sharpe_threshold": 0
  }
}
```

**Response（成功）**：
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
      "total_trades": 24,
      "win_trades": 15,
      "loss_trades": 9
    },
    "equity_curve": [
      {"date": "2025-01-02", "equity": 1000000}
    ],
    "benchmark_curve": [{"date": "2025-01-02", "equity": 1000000}],
    "benchmark_name": "NASDAQ",
    "trades": [...],
    "current_holdings": [...],
    "cash": 200000,
    "date_range": {
      "start": "2025-01-01",
      "end": "2025-06-30",
      "trading_days": 124
    },
    "elapsed_seconds": 3.5
  }
}
```

**Response（失敗）**：
```json
{
  "success": false,
  "error": "錯誤訊息"
}
```

---

## 四、靜態資產路由（main.py）

| 路由 | 說明 |
|------|------|
| `GET /` | 返回 `templates/index.html` |
| `GET /<path>` | 從 `static/` 返回對應靜態資產 |

支援 PyInstaller 打包後的路徑解析（`get_resource_path()`）。

---

## 五、前端靜態資產結構

```
static/
├── css/
│   └── style.css
└── js/
    ├── app.js           # 應用入口
    ├── config.js        # API 端點設定
    ├── api/             # 後端 API 呼叫封裝
    ├── components/      # UI 元件（圖表等）
    └── utils/           # 工具函數

templates/
└── index.html           # SPA 單頁入口
```

前端 JavaScript 負責：
- 呼叫後端 API（`fetch`）
- 參數設定 UI
- 接收並顯示回測結果（圖表、表格）

前端 JavaScript **不負責**：
- 回測計算（交由後端 Python 執行）
- 資料抓取（交由後端 `DataContainer` 管理）

---

## 六、錯誤處理

所有路由均有 `try/except` 包裝，失敗時返回：
```json
{"error": "錯誤訊息"}
```
HTTP 狀態碼：
- `400` — 請求參數錯誤或無資料
- `500` — 伺服器內部錯誤
- `503` — 資料容器尚未初始化完成
