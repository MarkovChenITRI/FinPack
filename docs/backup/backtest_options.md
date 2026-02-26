# 回測條件選項手冊

本手冊詳列所有回測條件的完整規格，包含條件定義、觸發邏輯、風險特性，以及推薦組合。

---

## 一、條件分類架構

| 類別 | 用途 | 選擇模式 |
|------|------|----------|
| **買入範圍** | 篩選候選股票池 | 複選（至少選一） |
| **成長動能** | 動能驗證過濾 | 單選或不選 |
| **選股方式** | 最終排序與選取 | 單選或不選 |
| **賣出條件** | 出場時機判斷 | 複選 |
| **再平衡** | 資金投入時機 | 單選 |

---

## 二、買入條件

### 買入範圍（複選，至少選一）

| 條件 | 鍵值 | 觸發邏輯 | 風險特性 |
|------|------|----------|----------|
| **Sharpe Top-N** | `sharpe_rank` | 股票在 Sharpe 排名前 N 名 | 基礎過濾，熊市仍可能買入 |
| **Sharpe 門檻** | `sharpe_threshold` | Sharpe 值 ≥ 門檻值 | **強過濾**，熊市自動停買 |
| **Sharpe 連續** | `sharpe_streak` | 連續 N 天維持在 Sharpe Top-15 | **強過濾**，過濾假突破 |

**設計哲學**：
- `sharpe_rank` 為最寬鬆的基礎篩選，確保有候選股可選
- `sharpe_threshold`、`sharpe_streak` 為強過濾條件，熊市時因條件嚴格而自動停買

---

### 成長動能（單選或不選）

| 條件 | 鍵值 | 觸發邏輯 | 風險特性 |
|------|------|----------|----------|
| **Growth Top-K** | `growth_rank` | Growth 排名在前 K 名 | 追求短期動能，熊市風險高 |
| **Growth 連續** | `growth_streak` | 連續 N 天 Growth 排名 ≤ 50% | 驗證持續動能，過濾假突破 |

**設計哲學**：
- `growth_rank` 追求短期爆發力，適合牛市
- `growth_streak` 驗證動能持續性，過濾假突破，適合全天候

---

### 選股方式（單選或不選）

| 條件 | 鍵值 | 觸發邏輯 | 風險特性 |
|------|------|----------|----------|
| **按 Sharpe 順序** | `sort_sharpe` | 依 Sharpe 排名順序選股 | 集中選股，報酬集中 |
| **按產業分散** | `sort_industry` | 依產業分散 + Sharpe 排序 | 產業分散，降低單一產業風險 |

**設計哲學**：
- `sort_sharpe` 讓報酬來源集中於最強標的
- `sort_industry` 確保產業分散，降低單一產業崩盤風險

---

### 買入條件風險矩陣

| # | sharpe_rank | sharpe_threshold | sharpe_streak | growth_rank | growth_streak | sort_sharpe | sort_industry | 風險 | 說明 |
|---|:-----------:|:----------------:|:-------------:|:-----------:|:-------------:|:-----------:|:-------------:|:----:|------|
| 1 | ✗ | ✗ | ✗ | - | - | - | - | 🔴 高 | ⚠️ 請至少選擇一個買入範圍條件 |
| 2 | ✓ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ⚖️ 平衡 | 僅使用基礎過濾：建議配合動能/選股條件 |
| 3 | ✗ | ✓ | ✗ | ✗ | ✗ | ✗ | ✗ | 🟢 低 | 🛡️ 強過濾保守策略，熊市自動停買 |
| 4 | * | ✓ | * | ✗ | ✓ | ✗ | ✓ | 🟢 低 | 🛡️ **熊市最安全組合**：強過濾 + 連續動能 + 產業分散 |
| 5 | ✓ | ✗ | ✗ | ✓ | ✗ | ✓ | ✗ | 🔴 高 | ⚠️ 牛市最佳但熊市高風險 |
| 6 | ✓ | ✗ | ✗ | ✗ | ✓ | ✗ | ✓ | ⚖️ 平衡 | ⚖️ **全天候推薦（預設）**：牛市抓強者，熊市自動保護 |

> **圖例**：✓ = 選中、✗ = 未選中、* = 任意、- = 不適用

---

### 推薦買入策略

| 市場環境 | 建議組合 | 風險 |
|---------|---------|:----:|
| 🐂 牛市進取 | `sharpe_rank` + `growth_rank` + `sort_sharpe` | 🔴 高 |
| ⚖️ 全天候平衡 | `sharpe_rank` + `growth_streak` + `sort_industry`（預設） | ⚖️ 平衡 |
| 🐻 熊市防禦 | `sharpe_threshold` + `growth_streak` + `sort_industry` | 🟢 低 |

---

## 三、賣出條件（複選）

| 條件 | 鍵值 | 觸發邏輯 | 風險特性 |
|------|------|----------|----------|
| **Sharpe 失格** | `sell_sharpe_fail` | Sharpe 排名 > N 連續 M 期 | 結構性品質下降即退出 |
| **Growth 失格** | `sell_growth_fail` | mean(Growth 最近 X 天) < 0 | 趨勢斷裂即退出 |
| **未入選淘汰** | `sell_not_selected` | 股票不在買入候選名單連續 M 期 | 自然淘汰弱股 |
| **價格破底** | `sell_drawdown` | drawdown ≥ X%（預設 40%） | 嚴重下跌即停損 |
| **相對弱勢** | `sell_weakness` | Sharpe_rank > K AND Growth_rank > K 連續 M 期 | 未來性不足即退出 |

**設計哲學**：
- `sell_sharpe_fail` / `sell_growth_fail`：監控品質與動能的結構性變化
- `sell_not_selected`：溫和淘汰，適合保守投資者
- `sell_drawdown`：硬性停損，防止持續拖累
- `sell_weakness`：雙維度監控，清除長期弱勢股

---

### 賣出條件風險矩陣

| # | sharpe_fail | growth_fail | not_selected | drawdown | weakness | 風險 | 說明 |
|---|:-----------:|:-----------:|:------------:|:--------:|:--------:|:----:|------|
| 1 | ✗ | ✗ | ✗ | ✗ | ✗ | 🔴 高 | 永不賣出：僅適合極度長期持有 |
| 2 | ✓ | ✗ | ✗ | ✓ | ✗ | 🟢 低 | ⭐ **預設推薦**：品質+價格雙重保護 |
| 3 | ✓ | ✗ | ✓ | ✓ | ✗ | 🟢 低 | 🛡️ **熊市最安全**：三重保護 |
| 4 | ✓ | ✓ | ✓ | ✓ | ✓ | 🟢 低 | 完整保護：所有條件啟用 |

> **圖例**：✓ = 選中、✗ = 未選中

---

### 推薦賣出策略

| 市場環境 | 建議組合 | 風險 |
|---------|---------|:----:|
| 🐂 牛市進取 | `sell_sharpe_fail` + `sell_drawdown` | 🟢 低 |
| ⚖️ 全天候平衡 | `sell_sharpe_fail` + `sell_drawdown`（預設） | 🟢 低 |
| 🐻 熊市防禦 | `sell_sharpe_fail` + `sell_not_selected` + `sell_drawdown` | 🟢 低 |

---

## 四、再平衡條件（單選）

| 條件 | 鍵值 | 觸發邏輯 | 風險特性 |
|------|------|----------|----------|
| **立即投入** | `rebal_immediate` | 無條件投入，符合買入條件即全額投入 | 牛市最佳，熊市風險極高 |
| **分批投入** | `rebal_batch` | 固定比例投入（如每次 20%），平滑成本 | **全天候推薦** |
| **延遲投入** | `rebal_delayed` | 等市場轉強再進場（Sharpe_top5_avg > 0） | 熊市防禦，避免假突破 |
| **集中投入** | `rebal_concentrated` | 只在買入標的排名前 K 有明確領先時才投入 | 牛市高報酬，熊市危險 |
| **保留現金** | `rebal_none` | 永不投入，僅用於觀察模式 | 風險最低，報酬最低 |

**設計哲學**：
- `rebal_immediate` 追求最大參與度，適合確認牛市
- `rebal_batch` 平滑成本，降低擇時風險
- `rebal_delayed` 等待市場確認轉強，避免假突破
- `rebal_concentrated` 只在高確信度時出手
- `rebal_none` 純觀察模式

---

### 再平衡條件風險矩陣

| # | 條件 | 牛市表現 | 熊市表現 | 風險 | 說明 |
|---|------|----------|----------|:----:|------|
| 1 | `rebal_immediate` | 報酬最高（追行情） | 最危險（買在反彈） | 🔴 高 | ⚠️ 牛市最佳但熊市風險極高 |
| 2 | `rebal_batch` | 平滑成長 | 保護效果強 | ⚖️ 平衡 | ⚖️ **全天候推薦**：熊市自動減少曝險 |
| 3 | `rebal_delayed` | 等市場轉強再進 | 避免假突破 | 🟢 低 | 🛡️ 等待 Sharpe_top5_avg > 0 確認市場轉強 |
| 4 | `rebal_concentrated` | 抓住主升段 | 熊市不建議 | 🔴 高 | ⚠️ 只在領先明確時出手 |
| 5 | `rebal_none` | 報酬最低 | 風險最低 | 🟢 低 | 🛡️ 僅供觀察或極端保守策略 |

---

### 推薦再平衡策略

| 市場環境 | 建議條件 | 風險 |
|---------|---------|:----:|
| 🐂 牛市進取 | `rebal_immediate` 或 `rebal_concentrated` | 🔴 高 |
| ⚖️ 全天候平衡 | `rebal_batch`（預設） | ⚖️ 平衡 |
| 🐻 熊市防禦 | `rebal_delayed` 或 `rebal_none` | 🟢 低 |

---

## 五、程式碼對照表

### 條件註冊表映射（JavaScript）

```javascript
// static/js/backtest/buying/index.js
export const BuyConditionRegistry = {
    _conditions: {
        // 買入範圍（複選）
        'sharpe_rank': SharpeRankCondition,
        'sharpe_threshold': SharpeThresholdCondition,
        'sharpe_streak': SharpeStreakCondition,
        // 成長動能（單選）
        'growth_rank': GrowthRankCondition,
        'growth_streak': GrowthStreakCondition,
        // 選股方式（單選）
        'sort_sharpe': SortSharpeCondition,
        'sort_industry': SortIndustryCondition,
    }
};

// static/js/backtest/selling/index.js
export const SellConditionRegistry = {
    _conditions: {
        'sharpe_fail': SharpeFailCondition,
        'growth_fail': GrowthFailCondition,
        'not_selected': NotSelectedCondition,
        'drawdown': DrawdownCondition,
        'weakness': WeaknessCondition,
    }
};

// static/js/backtest/rebalance/index.js
export const RebalanceConditionRegistry = {
    _conditions: {
        'immediate': ImmediateCondition,
        'batch': BatchCondition,
        'delayed': DelayedCondition,
        'concentrated': ConcentratedCondition,
        'none': NoneCondition,
    }
};
```

---

## 六、擴充指南

### 新增買入條件

1. 在 `static/js/backtest/buying/` 建立新檔案，繼承 `BuyCondition` 基類
2. 實現 `evaluate(date, prices, ranking, portfolio) -> Array<Object>`
3. 在 `buying/index.js` 加入新鍵值到 `BuyConditionRegistry._conditions`
4. 在本文件新增說明

```javascript
// 範例：static/js/backtest/buying/momentum.js
import { BuyCondition } from './base.js';

export class MomentumCondition extends BuyCondition {
    constructor(config = {}) {
        super('momentum', '動量選股');
        this.lookback = config.lookback || 20;
    }
    
    evaluate(date, prices, ranking, portfolio) {
        // 實現選股邏輯
        return candidates;
    }
}
```

### 新增賣出條件

1. 在 `static/js/backtest/selling/` 建立新檔案，繼承 `SellCondition` 基類
2. 實現 `evaluate(date, ticker, position, prices, ranking) -> boolean`
3. 在 `selling/index.js` 加入新鍵值到 `SellConditionRegistry._conditions`
4. 在本文件新增說明

### 新增再平衡條件

1. 在 `static/js/backtest/rebalance/` 建立新檔案，繼承 `RebalanceCondition` 基類
2. 實現 `evaluate(date, portfolio, prices) -> boolean`
3. 在 `rebalance/index.js` 加入新鍵值到 `RebalanceConditionRegistry._conditions`
4. 在本文件新增說明

---

## 七、版本紀錄

| 版本 | 日期 | 說明 |
|------|------|------|
| 1.0 | 2025-01 | 初版：完整條件矩陣與推薦策略 |
| 2.0 | 2025-02 | 移除無意義前綴代碼，改用語意化鍵值 |
| 3.0 | 2025-06 | 前端化：條件邏輯移至 JavaScript，後端僅提供資料 |
