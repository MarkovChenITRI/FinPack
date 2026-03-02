# FinPackV2 系統設計文件 — BTC-USD SMC 合約回測平台

## 系統概述

FinPackV2 是一個針對 BTC-USD 的 Smart Money Concepts (SMC) 量化策略分析與合約回測平台。
系統在伺服器啟動時預先計算所有 SMC 指標，前端透過 K 線圖視覺化信號並提供互動式合約參數設定進行回測。

---

## 功能模組

### 1. 後端：SMC 指標預計算服務
- 伺服器啟動時載入 BTC-USD 歷史日線資料（6年）
- 預先計算所有 SMC 指標：Pivot、BOS/CHOCH、FVG、Order Block、流動性池
- 結果序列化為 JSON，透過 API 提供給前端
- 資料快取以 pickle 儲存，最大過期時間 1 天

### 2. 後端：合約回測引擎
- 支援多方（Long）/ 空方（Short）
- 槓桿輸入影響強平價計算：
  - Long 強平價 = 入場價 × (1 - 1/槓桿)
  - Short 強平價 = 入場價 × (1 + 1/槓桿)
- 安全驗證：強平價觸碰比止損更早則跳過該筆交易
- 止盈目標：流動性池（Liquidity Pool）位置
- 止損設定：Order Block 底部/頂部
- PnL 計算：含槓桿、手續費（0.1%）

### 3. 前端：K 線圖 + 信號視覺化
- 使用 Lightweight Charts 渲染 BTC-USD K 線
- 勾選方塊切換各類 SMC 信號的顯示：
  - BOS（結構突破）→ 標記（Marker）
  - CHOCH（結構轉換）→ 標記（Marker）
  - FVG 缺口（多方/空方）→ 半透明色帶
  - Order Block → 高亮矩形帶
  - 流動性池 → 水平虛線
- Timeframe 切換：1D / 4H / 1H

### 4. 前端：合約設定與回測面板
- 使用者參數輸入：
  - 初始資金（USD）
  - 槓桿倍數（1x–100x）
  - 回測起始日期
  - 方向：多方 / 空方 / 雙向
  - 每筆風險比例（%）
- 進場條件勾選：偏向確認、折扣區間、FVG 回補、OB 觸碰
- 出場條件：止損%、流動性池 TP、結構反轉退出、最大持倉K棒數
- 回測結果展示：
  - 總報酬、勝率、最大回撤、Sharpe Ratio
  - 權益曲線圖（Lightweight Charts）
  - BTC Buy & Hold 基準對比（Alpha）
  - 交易明細表

---

## API 端點規格

### 市場資料
```
GET /api/health
→ { status, symbol, latest_close, initialized }

GET /api/kline/btc?timeframe=1d&period=1y
→ { symbol, timeframe, data: [{time, open, high, low, close, volume}...] }

GET /api/market-status
→ { symbol, price, change_pct, timestamp }
```

### SMC 信號
```
GET /api/btc/signals?timeframe=1d
→ {
    bos:            [{time, price, type, direction}...],
    choch:          [{time, price, type, direction}...],
    fvgs:           [{time_start, time_end, top, bottom, type, filled}...],
    order_blocks:   [{time, top, bottom, type, invalidated}...],
    liquidity_pools:[{price, type, touch_count}...]
  }
```

### 回測
```
GET /api/backtest/config
→ { options: {...}, defaults: {...} }

POST /api/backtest/run
Body: {
  initial_capital: 10000,
  leverage:        10,
  risk_per_trade:  0.02,
  timeframe:       "1d",
  start_date:      "2022-01-01",
  end_date:        null,
  allow_long:      true,
  allow_short:     false,
  entry_conditions: { require_bias, require_discount, require_fvg, require_ob },
  exit_conditions:  { stop_loss_pct, take_profit_liquidity, structure_exit, max_holding_bars }
}
→ {
    success: true,
    result: {
      metrics: {
        total_trades, win_rate, total_return, max_drawdown,
        sharpe_ratio, benchmark_return, alpha
      },
      equity_curve: [{time, equity}...],
      trades: [{entry_time, exit_time, direction, entry_price, exit_price,
                stop_loss, take_profit, liq_price, pnl, pnl_pct, reason}...]
    }
  }
```

---

## 前端頁面結構

```
┌─────────────────────────────────────────────────────────────────────┐
│  FinPackV2 — BTC Smart Money                          [nav/header]  │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌───────────────────────────────────┐  ┌────────────────────────┐ │
│  │  BTC-USD K線圖                    │  │  SMC 信號控制          │ │
│  │  [Timeframe: 1D | 4H | 1H]       │  │  ☑ BOS / CHOCH        │ │
│  │                                   │  │  ☑ FVG 缺口           │ │
│  │  (Lightweight Charts              │  │  ☑ Order Block         │ │
│  │   + 信號 Markers/Zones)           │  │  ☑ 流動性池            │ │
│  │                                   │  │                        │ │
│  │                                   │  │  最新價格: $XX,XXX     │ │
│  │                                   │  │  24h 變化: +X.XX%     │ │
│  └───────────────────────────────────┘  └────────────────────────┘ │
│                                                                     │
├─────────────────────────────────────────────────────────────────────┤
│  合約回測設定                                                        │
│                                                                     │
│  ┌─────────────────────────┐  ┌─────────────────────────────────┐  │
│  │  資金設定                │  │  進出場條件                      │  │
│  │  初始資金: [_____] USD   │  │  方向: ○多 ○空 ○雙向            │  │
│  │  槓桿:     [__]x         │  │  進場: ☑偏向 ☑折扣區 ☑FVG ☑OB │  │
│  │  每筆風險: [__]%         │  │  出場: SL[_]% TP:流動性 結構出 │  │
│  │  起始日期: [________]    │  │  最大持倉: [__]根K棒            │  │
│  └─────────────────────────┘  └─────────────────────────────────┘  │
│                                                                     │
│  [執行回測]                                                          │
│                                                                     │
├─────────────────────────────────────────────────────────────────────┤
│  回測結果                                                            │
│                                                                     │
│  總報酬: XX%   勝率: XX%   最大回撤: XX%   Sharpe: X.XX            │
│  BTC Buy&Hold: XX%   Alpha: +XX%                                    │
│                                                                     │
│  [權益曲線圖]                                                        │
│                                                                     │
│  [交易明細表]                                                        │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 後端模組架構

```
main.py
 ├── core/container.py     → BtcDataContainer（資料快取）
 ├── core/smc_service.py   → SmcSignalService（信號預計算）
 └── web/routes/
      ├── market.py        → /api/kline/btc, /api/market-status, /api/btc/signals
      └── backtest.py      → /api/backtest/run, /api/backtest/config

core/
 ├── config.py             → 路徑常數
 ├── data.py               → yfinance 抓取 + 快取
 ├── smc.py                → SMC 指標算法（pivot/BOS/FVG/OB/LP）
 ├── smc_service.py        → 預計算服務（序列化 JSON）
 └── container.py          → BtcDataContainer singleton

backtest/
 ├── smc_config.py         → 配置驗證（含 leverage 欄位）
 └── smc_engine.py         → 回測引擎（含強平價邏輯）
```

---

## 前端模組架構

```
static/js/
 ├── app.js                → 主程式協調器（初始化、事件綁定）
 ├── config.js             → API 端點常數
 ├── api/
 │   ├── client.js         → fetch 封裝（錯誤處理）
 │   ├── btc.js            → BTC K線 + 信號 API
 │   └── backtest.js       → 回測 API
 └── components/
      ├── SmcChart.js       → K線圖 + SMC 信號 overlay
      └── ContractPanel.js  → 合約參數設定 + 結果展示
```

---

## SMC 指標算法說明

### Pivot 偵測（無前瞻偏差）
- Pivot High[i]：第 i 根是區域最高，且往後 lookback 根均低於它
- Pivot Low[i]：第 i 根是區域最低，且往後 lookback 根均高於它
- 確認延遲：lookback 根（預設 5 根）

### BOS / CHOCH
- BOS（Break of Structure）：在多頭偏向中，價格收盤突破上一個 Swing High
- CHOCH（Change of Character）：在多頭偏向中，價格跌破上一個 Swing Low（偏向反轉）

### FVG（Fair Value Gap / 三根K棒缺口）
- 多方 FVG：第 3 根低點 > 第 1 根高點（向上跳空）
- 空方 FVG：第 3 根高點 < 第 1 根低點（向下跳空）
- ATR 過濾：缺口寬度需 > ATR × 0.1

### Order Block
- 多方 OB：位移（強勢多頭K棒，幅度 > 1.5×ATR）之前的最後一根空方K棒
- 空方 OB：位移（強勢空方K棒）之前的最後一根多方K棒
- 失效：OB 區間被收盤價穿越則標記為 invalidated

### 流動性池（Liquidity Pool）
- 在公差 0.2% 範圍內，有 2 根以上 Pivot 形成等高頂或等低底
- 視為市場主力可能掃蕩的區域

---

## 合約回測風險管理

### 強平價計算
```
Long:  liq_price = entry × (1 - 1 / leverage)
Short: liq_price = entry × (1 + 1 / leverage)
```

### 交易有效性驗證
```
Long:  有效 if liq_price < stop_loss（強平不會先於止損觸發）
Short: 有效 if liq_price > stop_loss
```

### 部位大小（風險管理）
```
risk_amount    = equity × risk_per_trade
stop_distance  = |entry - stop_loss| / entry
position_size  = risk_amount / (stop_distance × entry)
leveraged_size = position_size × leverage
```

### 盈虧計算（含手續費）
```
Long PnL  = (exit - entry) / entry × leveraged_size - fee
Short PnL = (entry - exit) / entry × leveraged_size - fee
fee       = (entry + exit) × position_size × fee_rate
```
