# Smart Money Concepts (SMC) 量化策略評估報告

**交易對**: BTC-USD
**報告日期**: 2026-03-01
**策略框架**: ICT / Smart Money Concepts

---

## 1. 策略概述

Smart Money Concepts (SMC) 是由 ICT（Inner Circle Trader）發展的市場結構分析框架，核心理念是：**機構投資者（大資金）的行為會在 K 線結構中留下可識別的痕跡**，散戶可藉由讀取這些痕跡來跟進機構方向。

### 1.1 核心概念清單

| 概念 | 英文縮寫 | 說明 |
|------|---------|------|
| 突破結構 | BOS | 價格突破前期高/低點，確認趨勢方向 |
| 性質改變 | CHOCH | 反向的第一次 BOS，代表趨勢可能翻轉 |
| 公平價值缺口 | FVG | 三根 K 線之間的跳空區域，為未填補的不平衡 |
| 訂單區塊 | OB | 機構大量掛單前的最後一根反向 K 線 |
| 流動性池 | LP | 止損單集中的區域（等高/等低點） |
| 折扣/溢價區 | Discount/Premium | 擺動區間 50% 線以下/以上 |
| 誘多/誘空 | Inducement | 刻意製造的假突破以吸收止損單 |
| 位移 | Displacement | 大動量 K 線，常伴隨 FVG |

---

## 2. 量化可行性評估

### 2.1 可完整量化的核心概念

#### ✅ BOS / CHOCH 偵測（市場結構）
**量化方法**：Pivot 高低點偵測 + 收盤價突破判斷

```
Swing High(i): High[i] == max(High[i-n : i+n+1])，需 n 根確認
Bullish BOS: Close[i] > 最近確認的 Swing High
Bullish CHOCH: 在下跌序列中的第一次 Bullish BOS
```

**量化難度**: ⭐（容易）
**參數敏感度**: Pivot lookback 窗口（建議 5-10 bars）會影響結構識別粒度

---

#### ✅ FVG 偵測（公平價值缺口）
**量化方法**：三根 K 線模式

```
Bullish FVG: Low[i] > High[i-2]   → 缺口在 High[i-2] ~ Low[i] 之間
Bearish FVG: High[i] < Low[i-2]   → 缺口在 High[i] ~ Low[i-2] 之間
FVG 失效: 當價格收盤穿越缺口中點則標記為已填補
```

**量化難度**: ⭐（容易）
**注意事項**: FVG 是否算「有效」存在主觀判斷，可量化為：FVG 大小 > 平均 ATR 的 X%

---

#### ✅ Order Block 偵測（訂單區塊）
**量化方法**：移位 + 大動量條件

```
位移條件: Candle Body[j] > 1.5 × 平均 Body（前 N 根）
Bullish OB: 位移前的最後一根看跌 K 線（Open > Close）
Bearish OB: 位移前的最後一根看漲 K 線（Close > Open）
OB 有效範圍: [OB.Low, OB.High]
OB 失效: 價格收盤穿越 OB 另一側
```

**量化難度**: ⭐⭐（中等）
**主觀性來源**: 何謂「足夠大」的位移需要設定閾值

---

#### ✅ 流動性池識別（等高/等低）
**量化方法**：swing 點群聚偵測

```
Equal Highs: 兩個以上 Swing High 在 tolerance% 範圍內
Equal Lows: 兩個以上 Swing Low 在 tolerance% 範圍內
buy-side liquidity (BSL): 在等高點之上（機構會掃這裡的止損）
sell-side liquidity (SSL): 在等低點之下
```

**量化難度**: ⭐⭐（中等）
**容忍度參數**: 通常設 0.1%–0.3% 視市場波動度調整

---

#### ✅ 折扣/溢價區（Discount / Premium）
**量化方法**：擺動區間中點計算

```
Swing Range: 最近 Swing Low ~ Swing High
Equilibrium (50%): (Swing High + Swing Low) / 2
Discount Zone: price < Equilibrium（適合做多進場）
Premium Zone: price > Equilibrium（適合做空進場）
```

**量化難度**: ⭐（容易）

---

### 2.2 部分量化的概念

#### ⚠️ Displacement（位移）
量化為「大動量 K 線」是可行的，但「足夠大」的閾值需經過歷史最佳化，且不同市場環境下適合的閾值不同。建議基於滾動 ATR 設定相對標準。

#### ⚠️ Inducement（誘多/誘空）
本質上是後見之明概念——只有在假突破後價格反轉才能確認是誘多/誘空。即時識別幾乎不可能，因此在量化策略中通常跳過此條件，改用 FVG / OB 作為進場依據。

#### ⚠️ 多時間框架 (MTF) 整合
概念本身可量化（在 4H 找結構，在 1H 找 OB 進場），但在單一 DataFrame 中整合多時間框架數據需要額外的時間對齊邏輯。本系統採用**單一時間框架**（4H）簡化實作。

---

### 2.3 難以量化的概念

#### ❌ 機構意圖（Institutional Intent）
無法直接從 OHLCV 量化，只能從上述間接指標推斷。

#### ❌ 市場概況（Market Maker Profile）
涉及對訂單簿深度的理解，純 OHLCV 回測無法捕捉。

---

## 3. 量化策略設計（BTC-USD 4H）

### 3.1 資料選擇

| 項目 | 設定 |
|------|------|
| 交易對 | BTC-USD |
| 時間框架 | 4H（yfinance 可取得最近 730 天的 1H 資料） |
| 備選 | 1D（長期回測用，可達 6 年以上） |
| 資料來源 | yfinance `BTC-USD` |

> **注意**: yfinance 提供 1H 間隔最多 730 天歷史，4H 需從 1H 重採樣。
> 日線資料可取得 6 年以上，適合長期策略驗證。

---

### 3.2 進場規則（做多）

| 步驟 | 條件 |
|------|------|
| 1️⃣ 結構確認 | 最新 BOS/CHOCH 為多頭方向（Bullish BOS/CHOCH） |
| 2️⃣ 折扣區 | 當前收盤價 < 最近擺動區間的 50% 中點 |
| 3️⃣ 觸發訊號 | 價格進入：有效 Bullish FVG **或** Bullish OB 區間 |
| 4️⃣ 進場 | 訊號 K 線收盤時以市價進場（模擬下一根 K 線開盤） |

進場訊號優先順序：OB > FVG（OB 被視為更強的機構痕跡）

---

### 3.3 出場規則（做多）

| 優先序 | 條件 | 說明 |
|--------|------|------|
| 1 | 止損（固定） | 進場後跌破 OB.Low × (1 - stop_pct) |
| 2 | 止盈（流動性） | 到達最近 buy-side liquidity（前高 / 等高點） |
| 3 | 結構翻空 | 發生 Bearish CHOCH |
| 4 | 最大持倉期限 | 超過 max_holding_bars 根 K 線仍未觸及止盈 |

---

### 3.4 做空規則（對稱反向）

| 步驟 | 條件 |
|------|------|
| 結構 | Bearish BOS/CHOCH 確認 |
| 溢價區 | 當前收盤價 > 50% 中點 |
| 觸發 | 進入 Bearish FVG 或 Bearish OB |
| 止損 | 進場後漲破 OB.High × (1 + stop_pct) |
| 止盈 | 最近 sell-side liquidity（前低 / 等低點） |

---

### 3.5 風險管理

```
max_position_size = 1（單資產策略，同時只持有一個方向）
stop_loss_pct    = 2%（從 OB 另一側計算）
take_profit_pct  = 動態（流動性池位置決定）
risk_per_trade   = 初始資金的 2%（根據止損距離調整部位大小）
```

---

## 4. 回測基準設定

| 項目 | 設定 |
|------|------|
| 初始資金 | $10,000 USD |
| 手續費 | 0.1%（Spot），0.05% Maker / 0.1% Taker |
| 滑點 | 不模擬（保守估計以手續費覆蓋） |
| 基準 | BTC-USD Buy & Hold |
| 評估期間 | 2022-01-01 ~ 2025-12-31（含熊市/牛市週期） |

---

## 5. 量化可行性總結

### 5.1 整體評分

| 維度 | 評分 | 說明 |
|------|------|------|
| 概念量化可行性 | 7/10 | 核心訊號（BOS/FVG/OB）可完整量化 |
| 參數敏感度 | 中 | Pivot lookback 和 displacement 閾值影響顯著 |
| 過擬合風險 | 高 | 多個可調參數，需嚴格 Walk-Forward 驗證 |
| 執行可行性 | 高 | yfinance 提供充足資料，無資料取得障礙 |
| 加密貨幣適用性 | 中高 | 24/7 市場使 Session 邏輯較弱，但 BOS/FVG/OB 仍有效 |

### 5.2 核心限制

1. **後見之明偏差**（Look-ahead Bias）：Pivot 確認需要右側 N 根 K 線，在即時交易中存在延遲。回測中必須明確標記 pivot 的「識別時間」為確認時刻（非最高/最低時刻）。

2. **過度最佳化**：SMC 有大量可調參數（pivot lookback、FVG 最小大小、OB 位移閾值等），必須使用滾動走向前分析（Walk-Forward Analysis）避免曲線擬合。

3. **主觀性殘留**：即使量化，不同交易者對「有效 OB」的定義仍有歧異。本系統採用最保守的客觀定義。

4. **多時間框架整合**：本實作使用單一時間框架（4H 或 1D）以保持回測準確性，放棄多時間框架的精確入場。

### 5.3 最終結論

**SMC 策略可以進行量化編寫**，程度達到約 70–75% 的概念覆蓋率。核心的 BOS/CHOCH、FVG、OB、流動性池均能以明確規則實作。未量化的部分（Inducement、機構意圖）在實際策略中以風險管理規則替代。

建議使用**日線或 4H 資料**對 BTC-USD 進行回測，優先驗證策略的 **Win Rate（勝率）** 和 **Risk/Reward Ratio（風報比）** 是否符合預期。

---

## 6. 相關檔案索引

| 檔案 | 功能 |
|------|------|
| `core/smc.py` | SMC 指標計算（FVG、OB、BOS、CHOCH、流動性池、折扣區） |
| `core/data.py` | BTC-USD OHLCV 資料抓取與快取 |
| `backtest/smc_config.py` | SMC 策略參數配置（預設值、驗證） |
| `backtest/smc_engine.py` | SMC 專用回測引擎（單資產、雙向交易） |
| `run_btc.py` | CLI 入口點（執行 BTC-USD SMC 策略回測） |

---

*本報告由 FinPackV2 自動生成，基於 ICT SMC 框架進行量化評估。*
