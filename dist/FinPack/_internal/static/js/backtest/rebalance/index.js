/**
 * 再平衡策略註冊表
 * 
 * 統一匯出所有再平衡策略，提供策略查詢與管理
 */

import { Immediate } from './immediate.js';
import { Batch } from './batch.js';
import { Delayed } from './delayed.js';
import { Concentrated } from './concentrated.js';
import { None } from './none.js';

/**
 * 策略註冊表
 */
const RebalanceStrategyRegistry = {
    immediate: Immediate,
    batch: Batch,
    delayed: Delayed,
    concentrated: Concentrated,
    none: None
};

/**
 * 建立策略實例
 * @param {string} id - 策略 ID
 * @returns {RebalanceStrategyBase|null}
 */
export function createRebalanceStrategy(id) {
    const StrategyClass = RebalanceStrategyRegistry[id];
    return StrategyClass ? new StrategyClass() : null;
}

/**
 * 取得所有策略 ID
 * @returns {string[]}
 */
export function getAllRebalanceStrategyIds() {
    return Object.keys(RebalanceStrategyRegistry);
}

/**
 * 取得所有策略資訊
 * @returns {Object[]}
 */
export function getAllRebalanceStrategies() {
    return Object.keys(RebalanceStrategyRegistry).map(id => {
        const strategy = createRebalanceStrategy(id);
        return strategy ? strategy.getInfo() : null;
    }).filter(Boolean);
}

/**
 * 建立並設定策略
 * @param {string} id - 策略 ID
 * @param {Object} params - 參數
 * @returns {RebalanceStrategyBase|null}
 */
export function createAndConfigureStrategy(id, params = {}) {
    const strategy = createRebalanceStrategy(id);
    if (strategy) {
        strategy.setEnabled(true);
        strategy.setParams(params);
    }
    return strategy;
}

// 匯出所有策略類
export {
    Immediate,
    Batch,
    Delayed,
    Concentrated,
    None
};
