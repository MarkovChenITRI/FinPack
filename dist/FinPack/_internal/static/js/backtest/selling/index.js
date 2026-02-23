/**
 * 賣出條件註冊表
 * 
 * 統一匯出所有賣出條件，提供條件查詢與管理
 */

import { SharpeFail } from './sharpe_fail.js';
import { GrowthFail } from './growth_fail.js';
import { NotSelected } from './not_selected.js';
import { Drawdown } from './drawdown.js';
import { Weakness } from './weakness.js';

/**
 * 條件註冊表
 */
const SellConditionRegistry = {
    sharpe_fail: SharpeFail,
    growth_fail: GrowthFail,
    not_selected: NotSelected,
    drawdown: Drawdown,
    weakness: Weakness
};

/**
 * 建立條件實例
 * @param {string} id - 條件 ID
 * @returns {SellConditionBase|null}
 */
export function createSellCondition(id) {
    const ConditionClass = SellConditionRegistry[id];
    return ConditionClass ? new ConditionClass() : null;
}

/**
 * 取得所有條件 ID
 * @returns {string[]}
 */
export function getAllSellConditionIds() {
    return Object.keys(SellConditionRegistry);
}

/**
 * 取得所有條件資訊
 * @returns {Object[]}
 */
export function getAllSellConditions() {
    return Object.keys(SellConditionRegistry).map(id => {
        const condition = createSellCondition(id);
        return condition ? condition.getInfo() : null;
    }).filter(Boolean);
}

/**
 * 批量建立並設定條件
 * @param {Object} config - {id: {enabled, params}}
 * @returns {SellConditionBase[]}
 */
export function createSellConditions(config) {
    const conditions = [];
    
    for (const [id, settings] of Object.entries(config)) {
        const condition = createSellCondition(id);
        if (condition) {
            condition.setEnabled(settings.enabled !== false);
            if (settings.params) {
                condition.setParams(settings.params);
            }
            conditions.push(condition);
        }
    }
    
    return conditions;
}

/**
 * 檢查持倉是否應該賣出
 * @param {string} ticker - 股票代碼
 * @param {Object} position - 持倉資訊
 * @param {SellConditionBase[]} conditions - 條件列表
 * @param {Object} context - 上下文
 * @returns {Object} {shouldSell: boolean, reasons: string[]}
 */
export function checkSellConditions(ticker, position, conditions, context) {
    const reasons = [];
    
    for (const condition of conditions) {
        if (!condition.enabled) continue;
        
        const result = condition.check(ticker, position, context);
        
        if (result.shouldSell) {
            reasons.push({
                conditionId: condition.id,
                conditionName: condition.name,
                reason: result.reason
            });
        }
    }
    
    return {
        shouldSell: reasons.length > 0,
        reasons
    };
}

// 匯出所有條件類
export {
    SharpeFail,
    GrowthFail,
    NotSelected,
    Drawdown,
    Weakness
};
