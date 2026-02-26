# 回測策略綜合風險評估

本文件定義買入、賣出、再平衡三類條件組合後的**綜合風險評級**，供 UI 顯示與策略選擇參考。

---

## 一、單一維度風險分類

### 買入條件風險等級

| 風險 | 典型配置 | 特徵 |
|:----:|----------|------|
| 🔴 高 | `sharpe_rank` + `growth_rank` + `sort_sharpe` | 追漲集中，熊市易重傷 |
| ⚖️ 平衡 | `sharpe_rank` + `growth_streak` + `sort_industry` ⭐預設 | 平衡配置，牛熊兼顧 |
| 🟢 低 | `sharpe_threshold` + `growth_streak` + `sort_industry` | 強過濾，熊市自動停買 |

**判定邏輯**：
- 🔴 高：僅用 `sharpe_rank` + 追漲動能（`growth_rank`）+ 集中選股（`sort_sharpe`）
- ⚖️ 平衡：基礎過濾 + 連續動能驗證 + 產業分散
- 🟢 低：啟用強過濾（`sharpe_threshold` 或 `sharpe_streak`）

---

### 賣出條件風險等級

| 風險 | 典型配置 | 特徵 |
|:----:|----------|------|
| 🔴 高 | 無任何賣出條件 | 永不止損，風險無限 |
| ⚖️ 平衡 | 僅 `sell_drawdown` 或僅 `sell_sharpe_fail` | 單一保護，可能漏網 |
| 🟢 低 | `sell_sharpe_fail` + `sell_drawdown` ⭐預設 | 品質+價格雙重保護 |

**判定邏輯**：
- 🔴 高：未啟用任何賣出條件
- ⚖️ 平衡：僅啟用 1 個賣出條件
- 🟢 低：啟用 2 個以上賣出條件（含雙重保護組合）

---

### 再平衡條件風險等級

| 風險 | 條件 | 特徵 |
|:----:|------|------|
| 🔴 高 | `rebal_immediate`、`rebal_concentrated` | 全額進場或集中押注 |
| ⚖️ 平衡 | `rebal_batch` ⭐預設 | 分批投入，平滑成本 |
| 🟢 低 | `rebal_delayed`、`rebal_none` | 等待確認或保留現金 |

---

## 二、綜合風險評估矩陣

根據三個維度的風險等級組合，計算**綜合風險評級**：

### 風險計算規則

```
綜合分數 = 買入風險分 + 賣出風險分 + 再平衡風險分

風險分數對照：
  🔴 高 = 3
  ⚖️ 平衡 = 2
  🟢 低 = 1

綜合評級：
  3-4 分 → 🟢 低風險
  5-6 分 → ⚖️ 平衡
  7-9 分 → 🔴 高風險
```

---

### 完整組合矩陣

| # | 買入風險 | 賣出風險 | 再平衡風險 | 總分 | 綜合評級 | 策略特性 |
|:-:|:--------:|:--------:|:----------:|:----:|:--------:|----------|
| 1 | 🟢 低 | 🟢 低 | 🟢 低 | 3 | 🟢 低 | 🛡️ **極度防禦**：熊市最安全，但牛市報酬有限 |
| 2 | 🟢 低 | 🟢 低 | ⚖️ 平衡 | 4 | 🟢 低 | 🛡️ **熊市推薦**：強過濾 + 分批投入，穩健成長 |
| 3 | ⚖️ 平衡 | 🟢 低 | 🟢 低 | 4 | 🟢 低 | 🛡️ 基礎選股 + 完整保護 + 保守投入 |
| 4 | 🟢 低 | ⚖️ 平衡 | 🟢 低 | 4 | 🟢 低 | 強過濾 + 單一保護 + 保守投入 |
| 5 | ⚖️ 平衡 | 🟢 低 | ⚖️ 平衡 | 5 | ⚖️ 平衡 | ⭐ **全天候推薦（預設）**：牛市抓強者，熊市有保護 |
| 6 | 🟢 低 | 🟢 低 | 🔴 高 | 5 | ⚖️ 平衡 | 強過濾 + 完整保護 + 積極投入 |
| 7 | ⚖️ 平衡 | ⚖️ 平衡 | ⚖️ 平衡 | 6 | ⚖️ 平衡 | 三維度皆平衡，適合多數投資者 |
| 8 | 🔴 高 | 🟢 低 | 🟢 低 | 5 | ⚖️ 平衡 | 進取選股 + 完整保護 + 保守投入 |
| 9 | 🟢 低 | 🔴 高 | ⚖️ 平衡 | 6 | ⚖️ 平衡 | ⚠️ 強過濾但無賣出保護，持倉風險高 |
| 10 | ⚖️ 平衡 | 🔴 高 | ⚖️ 平衡 | 7 | 🔴 高 | ⚠️ 無賣出保護，虧損可能擴大 |
| 11 | 🔴 高 | ⚖️ 平衡 | ⚖️ 平衡 | 7 | 🔴 高 | ⚠️ 進取選股 + 單一保護，熊市風險高 |
| 12 | ⚖️ 平衡 | ⚖️ 平衡 | 🔴 高 | 7 | 🔴 高 | ⚠️ 全額進場，擇時風險高 |
| 13 | 🔴 高 | 🟢 低 | 🔴 高 | 7 | 🔴 高 | ⚠️ 進取兩端，熊市危險 |
| 14 | 🔴 高 | 🔴 高 | ⚖️ 平衡 | 8 | 🔴 高 | 🚨 進取選股 + 無保護，極高風險 |
| 15 | ⚖️ 平衡 | 🔴 高 | 🔴 高 | 8 | 🔴 高 | 🚨 無賣出保護 + 全額進場 |
| 16 | 🔴 高 | ⚖️ 平衡 | 🔴 高 | 8 | 🔴 高 | 🚨 牛市最佳但熊市致命 |
| 17 | 🔴 高 | 🔴 高 | 🔴 高 | 9 | 🔴 高 | 🚨 **極度激進**：僅適合確認牛市 |

---

## 三、典型策略組合

### 🐻 熊市防禦策略

| 維度 | 配置 | 風險 |
|------|------|:----:|
| 買入 | `sharpe_threshold` + `growth_streak` + `sort_industry` | 🟢 低 |
| 賣出 | `sell_sharpe_fail` + `sell_not_selected` + `sell_drawdown` | 🟢 低 |
| 再平衡 | `rebal_delayed` 或 `rebal_batch` | 🟢 低 |
| **綜合** | - | **🟢 低** |

**特性說明**：
- 強過濾確保熊市自動停買
- 三重賣出保護防止虧損擴大
- 等待市場轉強或分批投入降低擇時風險
- 適合熊市或不確定市場環境

---

### ⚖️ 全天候平衡策略（預設）

| 維度 | 配置 | 風險 |
|------|------|:----:|
| 買入 | `sharpe_rank` + `growth_streak` + `sort_industry` | ⚖️ 平衡 |
| 賣出 | `sell_sharpe_fail` + `sell_drawdown` | 🟢 低 |
| 再平衡 | `rebal_batch` | ⚖️ 平衡 |
| **綜合** | - | **⚖️ 平衡** |

**特性說明**：
- 基礎過濾 + 連續動能驗證，牛市能抓強者
- 產業分散降低單一產業風險
- 品質+價格雙重保護，熊市自動減倉
- 分批投入平滑成本，降低擇時壓力
- 適合大多數投資者與市場環境

---

### 🐂 牛市進取策略

| 維度 | 配置 | 風險 |
|------|------|:----:|
| 買入 | `sharpe_rank` + `growth_rank` + `sort_sharpe` | 🔴 高 |
| 賣出 | `sell_sharpe_fail` + `sell_drawdown` | 🟢 低 |
| 再平衡 | `rebal_immediate` 或 `rebal_concentrated` | 🔴 高 |
| **綜合** | - | **🔴 高** |

**特性說明**：
- 追漲集中選股，抓住主升段
- 仍保留賣出保護作為最後防線
- 全額或集中投入最大化參與度
- ⚠️ 僅適合確認牛市，熊市風險極高

---

## 四、UI 顯示建議

### 風險指示器樣式

```javascript
// 風險等級對應的 UI 顯示
const RISK_DISPLAY = {
    'low': {
        emoji: '🟢',
        label: '低風險',
        color: '#22c55e',
        description: '防禦型策略，熊市保護強'
    },
    'balanced': {
        emoji: '⚖️',
        label: '平衡',
        color: '#eab308',
        description: '全天候策略，牛熊兼顧'
    },
    'high': {
        emoji: '🔴',
        label: '高風險',
        color: '#ef4444',
        description: '進取型策略，熊市風險高'
    }
};
```

### 動態描述文字

根據組合提供動態描述：

| 綜合評級 | 建議文字 |
|:--------:|----------|
| 🟢 低 | 防禦型配置：熊市自動減少曝險，牛市報酬相對受限 |
| ⚖️ 平衡 | 全天候配置：牛市能抓強者，熊市有適度保護 |
| 🔴 高 | 進取型配置：牛市報酬最大化，熊市需注意風險控制 |

---

## 五、風險計算函數（JavaScript）

```javascript
/**
 * 計算綜合風險評級
 * @param {Object} config - 回測配置
 * @returns {Object} { level: 'low'|'balanced'|'high', score: number, description: string }
 */
export function calculateRiskLevel(config) {
    const buyRisk = assessBuyRisk(config);
    const sellRisk = assessSellRisk(config);
    const rebalanceRisk = assessRebalanceRisk(config);
    
    const riskScores = { low: 1, balanced: 2, high: 3 };
    const totalScore = riskScores[buyRisk] + riskScores[sellRisk] + riskScores[rebalanceRisk];
    
    let level, description;
    if (totalScore <= 4) {
        level = 'low';
        description = '防禦型配置：熊市自動減少曝險，牛市報酬相對受限';
    } else if (totalScore <= 6) {
        level = 'balanced';
        description = '全天候配置：牛市能抓強者，熊市有適度保護';
    } else {
        level = 'high';
        description = '進取型配置：牛市報酬最大化，熊市需注意風險控制';
    }
    
    return { level, score: totalScore, description, buyRisk, sellRisk, rebalanceRisk };
}

/**
 * 評估買入條件風險
 */
function assessBuyRisk(config) {
    const filters = config.filters || [];
    const growthRule = config.growthRule;
    const pickRule = config.pickRule;
    
    // 檢查是否有強過濾
    const hasStrongFilter = filters.includes('sharpe_threshold') || filters.includes('sharpe_streak');
    
    // 檢查是否追漲集中
    const isAggressive = growthRule === 'growth_rank' && pickRule === 'sort_sharpe';
    
    if (hasStrongFilter) return 'low';
    if (isAggressive) return 'high';
    return 'balanced';
}

/**
 * 評估賣出條件風險
 */
function assessSellRisk(config) {
    const sellRules = config.sellRules || [];
    
    if (sellRules.length === 0) return 'high';
    if (sellRules.length === 1) return 'balanced';
    return 'low';  // 2 個以上賣出條件
}

/**
 * 評估再平衡條件風險
 */
function assessRebalanceRisk(config) {
    const investRule = config.investRule;
    
    if (investRule === 'rebal_immediate' || investRule === 'rebal_concentrated') {
        return 'high';
    }
    if (investRule === 'rebal_delayed' || investRule === 'rebal_none') {
        return 'low';
    }
    return 'balanced';  // rebal_batch
}
```

---

## 六、版本紀錄

| 版本 | 日期 | 說明 |
|------|------|------|
| 1.0 | 2026-02 | 初版：三維度綜合風險評估矩陣 |
