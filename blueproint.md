### 目錄結構
```
FinPack/
│
├── core/                       # 模組 A：資料層（完全獨立）
│   ├── __init__.py
│   ├── config.py               # 系統常數
│   ├── currency.py             # Money, twd, usd, FX
│   ├── data.py                 # smart_load_or_fetch
│   ├── align.py                # align_data_with_bfill
│   ├── indicator.py            # Indicators
│   └── container.py            # DataContainer, build_close_df, filter_by_market
│
├── backtest/                   # 模組 B：回測引擎（完全獨立）
│   ├── __init__.py
│   ├── config.py               # DEFAULT_CONFIG, CONDITION_OPTIONS
│   ├── engine.py               # BacktestEngine
│   └── report.py               # format_backtest_report
│
├── web/                        # 模組 C：Web 框架（完全獨立）
│   ├── __init__.py
│   ├── market.py               # MarketDataLoader
│   └── routes/
│       ├── __init__.py
│       ├── stock.py            # 股票 API（獨立）
│       ├── market.py           # 市場 API（獨立）
│       └── backtest.py         # 回測 API（工廠模式，需注入依賴）
│
├── run.py                      # CLI 入口（組裝 core + backtest）
├── main.py                     # Web 入口（組裝 core + backtest + web）
│
├── static/
├── templates/
├── cache/
├── docs/
└── tests/
```

### 模組依賴圖
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