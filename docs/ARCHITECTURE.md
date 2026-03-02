# FinPackV2 架構文件 — BTC-USD SMC 合約回測平台

## 技術棧

| 層次 | 技術 |
|------|------|
| 後端框架 | Flask (Python) |
| 資料來源 | yfinance (BTC-USD, 1D/4H/1H) |
| 指標計算 | NumPy/Pandas（原生，無 TA 函式庫） |
| 前端圖表 | Lightweight Charts (TradingView) |
| 前端框架 | Vanilla JS（ES modules） |
| 打包支援 | PyInstaller（`sys._MEIPASS` 路徑處理） |

---

## 目錄結構

```
FinPackV2/
├── main.py                    # Flask 應用工廠 + 啟動入口
├── run_btc.py                 # CLI 回測入口（非 web）
├── log_setup.py               # 日誌配置
│
├── core/
│   ├── __init__.py            # 公開 API 匯出
│   ├── config.py              # 常數：路徑、快取設定
│   ├── data.py                # yfinance 抓取、4H 重採樣、快取
│   ├── smc.py                 # SMC 指標：Pivot/BOS/CHOCH/FVG/OB/LP
│   ├── smc_service.py         # 啟動時預計算 + JSON 序列化
│   ├── container.py           # BtcDataContainer singleton
│   └── currency.py            # Money 型別（USD 計算參考）
│
├── backtest/
│   ├── __init__.py            # 匯出 SMC 回測模組
│   ├── smc_config.py          # SMC 配置驗證（含 leverage）
│   ├── smc_engine.py          # SMC 回測引擎（含強平邏輯）
│   ├── engine.py              # [參考] 多資產股票回測模板
│   ├── runner.py              # [參考] pipeline 架構模板
│   ├── config.py              # [參考] 條件配置系統模板
│   ├── report.py              # [參考] 報告格式化模板
│   └── benchmark.py           # [參考] 基準比較模板
│
├── web/
│   ├── __init__.py
│   ├── market.py              # （空，保留 import 相容）
│   └── routes/
│       ├── __init__.py        # 匯出 market_bp, backtest_bp
│       ├── market.py          # /api/kline/btc, /api/market-status, /api/btc/signals
│       └── backtest.py        # /api/backtest/run, /api/backtest/config
│
├── templates/
│   └── index.html             # BTC SMC 單頁應用
│
├── static/
│   ├── css/style.css          # 深色主題 CSS
│   └── js/
│       ├── app.js             # 主協調器
│       ├── config.js          # API 端點常數
│       ├── api/
│       │   ├── client.js      # fetch 封裝
│       │   ├── btc.js         # BTC K線 + 信號 API
│       │   └── backtest.js    # 回測 API
│       ├── components/
│       │   ├── SmcChart.js    # K線圖 + SMC overlay
│       │   └── ContractPanel.js # 合約設定 + 回測結果
│       └── utils/
│           └── formatter.js   # 數字/日期格式化
│
├── cache/                     # 資料快取（.pkl 檔案）
├── logs/                      # 日誌檔案
└── docs/
    ├── ARCHITECTURE.md        # 本文件
    ├── system_design.md       # 完整系統設計規格
    ├── smart_money_evaluation.md # SMC 量化可行性評估
    └── backup/                # 舊版股票系統文件備份
```

---

## 資料流

```
[yfinance API]
     │ fetch (1D/1H)
     ▼
[core/data.py] ──快取──▶ [cache/btc_*.pkl]
     │
     ▼
[BtcDataContainer]   ← container.load('1d') at startup
     │
     ├──▶ [SmcSignalService]  ← pre-compute at startup
     │         │ pivot/BOS/CHOCH/FVG/OB/LP
     │         ▼
     │    [JSON in memory]
     │
     └──▶ [SmcEngine]  ← on demand (backtest/run)
               │ bar-by-bar simulation
               ▼
          [SmcBacktestResult]
```

---

## 啟動序列

```python
# main.py create_app()
1. container.load('1d')           # 載入 BTC-USD 1D 日線
2. smc_service.precompute()       # 預計算各 timeframe SMC 信號
3. register blueprints            # 掛載 API 路由
4. serve static files             # 前端靜態服務
```

---

## 前端初始化序列

```javascript
// app.js init()
1. GET /api/market-status            → 更新即時價格
2. GET /api/kline/btc?timeframe=1d   → K線資料
3. GET /api/btc/signals?timeframe=1d → SMC 信號
4. SmcChart.init(klineData)          → 渲染 K 線
5. SmcChart.applySignals(signals)    → 疊加信號 overlay
6. ContractPanel.init()              → 綁定回測表單
```

---

## API 路由清單

| 方法 | 路由 | 說明 |
|------|------|------|
| GET | `/api/health` | 健康檢查（BTC 初始化狀態） |
| GET | `/api/kline/btc` | BTC K線資料（?timeframe=1d&period=1y） |
| GET | `/api/market-status` | 最新 BTC 收盤價 |
| GET | `/api/btc/signals` | SMC 信號 JSON（?timeframe=1d） |
| GET | `/api/backtest/config` | 可用條件選項與預設值 |
| POST | `/api/backtest/run` | 執行 SMC 合約回測 |

---

## 關鍵設計原則

1. **無前瞻偏差**: Pivot 偵測使用右側 `lookback` 根確認，回測逐根模擬
2. **強平安全驗證**: 強平價比止損更早觸發時，該筆交易跳過不進場
3. **預計算效能**: SMC 信號在啟動時一次性計算完畢，API 回應即時
4. **單資產設計**: 整個系統只針對 BTC-USD，無多股票邏輯
5. **參考模板保留**: `backtest/engine.py` 等舊檔案作為架構參考，import 已防護
