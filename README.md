# FinPack - 全球市場看盤與回測系統

## 系統架構總覽

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                                 資料來源                                        │
│                              yfinance API                                       │
└─────────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              後端 (Python/Flask)                                │
├─────────────────────────────────────────────────────────────────────────────────┤
│  utils/stock_cache.py  ← 核心數據快取                                           │
│    ├── raw_data        原始 OHLCV (yfinance 下載)                               │
│    ├── aligned_data    日期對齊後的 OHLCV (bfill/ffill)                         │
│    ├── sharpe_matrix   Sharpe Ratio 矩陣 (日期 × 股票)                          │
│    └── slope_matrix    排名變化矩陣 (日期 × 股票)                               │
│                                                                                 │
│  utils/market.py       大盤指數 K 線數據                                         │
│                                                                                 │
│  app.py                Flask API 進入點                                          │
│    ├── /api/market-data      → K 線圖數據                                       │
│    ├── /api/industry/data    → Sharpe/Slope 矩陣                                │
│    ├── /api/stock-price      → 交易價格查詢                                      │
│    ├── /api/backtest/prices  → 回測價格批量查詢                                  │
│    └── /api/stocks           → 股票清單                                         │
└─────────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              前端 (JavaScript)                                  │
├─────────────────────────────────────────────────────────────────────────────────┤
│  static/js/main.js              入口點 → FinPackApp.init()                      │
│                                                                                 │
│  static/js/modules/                                                             │
│    ├── FinPackApp.js            主應用程式，初始化所有元件                       │
│    ├── MarketChart.js           K 線圖 (Lightweight Charts)                     │
│    ├── IndustryDataCache.js     前端數據快取，預計算 Top 15                      │
│    ├── IndustryBarChart.js      柱狀圖 (Chart.js)                               │
│    ├── TradeSimulator.js        交易模擬器                                       │
│    └── BacktestEngine.js        回測引擎                                        │
│                                                                                 │
│  templates/index.html           主頁面 DOM 結構                                  │
│  static/css/style.css           全域樣式                                         │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 資料流說明

### 1. 後端資料流 (啟動時)

```
yfinance API
    │
    ▼ 下載 6 年 OHLCV
stock_cache.raw_data
    │
    ▼ _align_data_with_bfill() 統一日期
stock_cache.aligned_data
    │
    ▼ _calculate_all_indicators()
stock_cache.sharpe_matrix    (Sharpe Ratio)
stock_cache.slope_matrix     (排名變化)
```

### 2. 前端資料流 (頁面載入時)

```
main.js
    │
    ▼ DOMContentLoaded
FinPackApp.init()
    │
    ├─► loadMarketData() ──► /api/market-data ──► MarketChart.setData()
    │
    ├─► industryDataCache.load() ──► /api/industry/data
    │       │
    │       ▼ 預計算每日 Top 15
    │   precomputed[mode][dataType][date]
    │
    ├─► sharpeChart.loadData() ──► industryDataCache.getTopAnalysis()
    │
    ├─► slopeChart.loadData() ──► industryDataCache.getTopAnalysis()
    │
    ├─► TradeSimulator.init() ──► /api/stocks
    │
    └─► BacktestEngine.init()
```

### 3. 滑鼠互動資料流 (即時)

```
滑鼠移動 K 線圖
    │
    ▼
MarketChart.handleCrosshairMove()
    │
    ▼ emitDateChange()
CustomEvent('kline-date-change')
    │
    ▼ FinPackApp 監聽
updateIndustryCharts(mode, date)
    │
    ├─► sharpeChart.loadData(mode, date) ──► 純查表 (無 API)
    │
    └─► slopeChart.loadData(mode, date) ──► 純查表 (無 API)
```

---

## 元件數據對應表

| 元件 | 數據來源 | API |
|------|----------|-----|
| K 線圖 | aligned_data | /api/market-data |
| Sharpe 柱狀圖 | sharpe_matrix | /api/industry/data (載入時) |
| 增長率柱狀圖 | slope_matrix | /api/industry/data (載入時) |
| 交易模擬器 | aligned_data | /api/stock-price |
| 回測引擎-價格 | aligned_data | /api/backtest/prices |
| 回測引擎-排名 | sharpe_matrix / slope_matrix | industryDataCache (前端) |

---

## 必須遵守的原則

### ⚠️ 數據一致性原則
- **所有元件必須使用相同的數據來源**
- K 線圖、交易模擬器、回測引擎都使用 `aligned_data`
- Sharpe/Slope 柱狀圖都使用 `sharpe_matrix` / `slope_matrix`
- **禁止任何元件獨立計算 Sharpe 或使用不同的價格來源**

### ⚠️ 快取原則
- **快取只存原始資料**：raw_data, watchlist, stock_info
- **不快取衍生指標**：sharpe_matrix, slope_matrix 每次啟動重算
- 好處：修改計算邏輯不需重新下載資料

### ⚠️ 日期對齊原則
- 不同市場交易日不同（週末只有加密貨幣有資料）
- `_align_data_with_bfill()` 統一所有股票的日期
- 所有 API 和計算都使用 `aligned_data`

### ⚠️ Inf/NaN 處理原則
- `_calculate_sharpe()`: rolling_std=0 → Inf → NaN
- `sharpe_matrix`: Inf/-Inf → NaN → bfill/ffill
- `slope_matrix`: 第一行 NaN → 0
- API `clean_nan()`: NaN/Inf → JSON null

---

## 目錄結構

```
FinPack/
├── app.py                      Flask API 進入點
├── debug_cache.py              快取調試工具 (開發用)
├── requirements.txt            Python 相依套件
├── pyproject.toml              專案配置
├── README.md                   本文件
│
├── utils/                      後端工具模組
│   ├── __init__.py
│   ├── stock_cache.py          核心數據快取
│   └── market.py               大盤指數數據
│
├── templates/
│   └── index.html              主頁面
│
├── static/
│   ├── css/
│   │   └── style.css           全域樣式
│   └── js/
│       ├── main.js             前端入口點
│       └── modules/
│           ├── FinPackApp.js       主應用程式
│           ├── MarketChart.js      K 線圖
│           ├── IndustryDataCache.js 前端數據快取
│           ├── IndustryBarChart.js  柱狀圖
│           ├── TradeSimulator.js    交易模擬器
│           └── BacktestEngine.js    回測引擎
│
└── cache/                      快取目錄 (自動生成)
    ├── stock_data.pkl          股票數據快取
    └── market_data.pkl         市場數據快取
```

---

## 執行方式

```bash
# 安裝相依套件
pip install -r requirements.txt

# 啟動伺服器
python app.py

# 開啟瀏覽器
http://127.0.0.1:5000
```

---

## 計算公式

### Sharpe Ratio (夏普比率)
```
Sharpe = (滾動平均超額報酬 / 滾動標準差) × √252
```
- 超額報酬 = 日報酬率 - 日無風險利率(4%/252)
- 滾動視窗 = 252 天
- 解讀：>1 優良，>2 優秀，<0 虧損

### Ranking Change (排名變化)
```
Ranking Change = Sharpe排名(yesterday) - Sharpe排名(today)
```
- +10 = 排名上升 10 位
- -5 = 排名下降 5 位
- 前端顯示為「增長率 Top 15」
