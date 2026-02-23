# FinPack Cloud Functions

獨立回測套件，可部署至 Google Cloud Functions。

## 檔案結構

```
cloud_functions/
├── __init__.py      # 套件入口
├── config.py        # 配置常數
├── data.py          # 資料擷取（TradingView + yfinance）
├── align.py         # 資料對齊
├── indicator.py     # 指標計算（Sharpe, Rank, Growth）
├── backtest.py      # 回測引擎（移植自 Engine.js）
├── run.py           # Entry point
└── requirements.txt # 依賴
```

## 本地測試

```bash
# 安裝依賴
pip install -r cloud_functions/requirements.txt

# 執行回測
python -m cloud_functions.run
```

## 部署至 Google Cloud Functions

```bash
gcloud functions deploy finpack-backtest \
    --runtime python311 \
    --trigger-http \
    --entry-point main \
    --source ./cloud_functions \
    --memory 2048MB \
    --timeout 540s \
    --allow-unauthenticated
```

## 環境變數

| 變數名稱 | 說明 | 預設值 |
|---------|------|--------|
| `TRADINGVIEW_WATCHLIST_ID` | TradingView 觀察清單 ID | `118349730` |
| `TRADINGVIEW_SESSION_ID` | TradingView Session ID | (內建) |
| `GCS_BUCKET` | GCS 快取 bucket（選用） | 空 |

## API 使用

### HTTP Request

```bash
curl -X POST https://YOUR_REGION-YOUR_PROJECT.cloudfunctions.net/finpack-backtest \
    -H "Content-Type: application/json" \
    -d '{"use_cache": true}'
```

### Response

```json
{
  "success": true,
  "elapsed_seconds": 45.2,
  "summary": {
    "initial_capital": 1000000,
    "final_equity": 1523456,
    "total_return": "52.35%",
    "annualized_return": "11.12%",
    "win_rate": "58.33%",
    "max_drawdown": "15.23%",
    "sharpe_ratio": 1.45,
    "total_trades": 156
  },
  "trades": [...],
  "equity_curve_sample": [...]
}
```

## 預設回測參數

- **買入**：Sharpe Top-15 + Sharpe ≥ 1 + Growth Streak 2天 + 按 Sharpe 排序
- **賣出**：Sharpe Fail 2期 + Drawdown 40%
- **再平衡**：Weekly + Delayed（等待市場強度）
- **資金**：初始 100萬，每檔 10萬，最多 10 檔
