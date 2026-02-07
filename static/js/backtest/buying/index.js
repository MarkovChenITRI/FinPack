/**
 * 買入條件註冊表
 * 
 * 統一匯出所有買入條件，提供條件查詢與管理
 */

import { SharpeRank } from './sharpe_rank.js';
import { SharpeThreshold } from './sharpe_threshold.js';
import { SharpeStreak } from './sharpe_streak.js';
import { GrowthRank } from './growth_rank.js';
import { GrowthStreak } from './growth_streak.js';
import { SortSharpe } from './sort_sharpe.js';
import { SortIndustry } from './sort_industry.js';

/**
 * 條件註冊表
 */
const BuyConditionRegistry = {
    // A 類：範圍過濾
    sharpe_rank: SharpeRank,
    sharpe_threshold: SharpeThreshold,
    sharpe_streak: SharpeStreak,
    
    // B 類：動能過濾
    growth_rank: GrowthRank,
    growth_streak: GrowthStreak,
    
    // C 類：挑選排序
    sort_sharpe: SortSharpe,
    sort_industry: SortIndustry
};

/**
 * 建立條件實例
 * @param {string} id - 條件 ID
 * @returns {BuyConditionBase|null}
 */
export function createBuyCondition(id) {
    const ConditionClass = BuyConditionRegistry[id];
    return ConditionClass ? new ConditionClass() : null;
}

/**
 * 取得所有條件 ID
 * @returns {string[]}
 */
export function getAllBuyConditionIds() {
    return Object.keys(BuyConditionRegistry);
}

/**
 * 取得分類條件列表
 * @returns {Object} {A: [], B: [], C: []}
 */
export function getBuyConditionsByCategory() {
    const categories = { A: [], B: [], C: [] };
    
    for (const id of Object.keys(BuyConditionRegistry)) {
        const condition = createBuyCondition(id);
        if (condition) {
            categories[condition.category].push(condition.getInfo());
        }
    }
    
    return categories;
}

/**
 * 批量建立並設定條件
 * @param {Object} config - {id: {enabled, params}}
 * @returns {BuyConditionBase[]}
 */
export function createBuyConditions(config) {
    const conditions = [];
    
    for (const [id, settings] of Object.entries(config)) {
        const condition = createBuyCondition(id);
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
 * 執行買入條件鏈
 * @param {string[]} tickers - 初始股票列表
 * @param {BuyConditionBase[]} conditions - 條件列表
 * @param {Object} context - 上下文
 * @returns {string[]} 最終候選股票
 */
export function applyBuyConditions(tickers, conditions, context) {
    // 按類別分組
    const categoryA = conditions.filter(c => c.category === 'A' && c.enabled);
    const categoryB = conditions.filter(c => c.category === 'B' && c.enabled);
    const categoryC = conditions.filter(c => c.category === 'C' && c.enabled);
    
    let result = [...tickers];
    
    // Debug: 首次調用時輸出條件資訊
    const isFirstDate = context.date === Object.keys(context.history?.sharpeRank || {})[0];
    if (isFirstDate) {
        console.log('🔍 買入條件處理:', {
            初始候選數: tickers.length,
            A類條件: categoryA.map(c => `${c.id}(params=${JSON.stringify(c.params)})`),
            B類條件: categoryB.map(c => c.id),
            C類條件: categoryC.map(c => c.id)
        });
    }
    
    // A 類條件：取交集（全部必須滿足）
    for (const condition of categoryA) {
        const before = result.length;
        result = condition.filter(result, context);
        if (isFirstDate) {
            console.log(`   A類 ${condition.id}: ${before} -> ${result.length}`);
        }
    }
    
    // B 類條件：取交集
    for (const condition of categoryB) {
        const before = result.length;
        result = condition.filter(result, context);
        if (isFirstDate) {
            console.log(`   B類 ${condition.id}: ${before} -> ${result.length}`);
        }
    }
    
    // C 類條件：最後一個生效（排序選取）
    if (categoryC.length > 0) {
        const lastC = categoryC[categoryC.length - 1];
        const before = result.length;
        result = lastC.filter(result, context);
        if (isFirstDate) {
            console.log(`   C類 ${lastC.id}: ${before} -> ${result.length}`);
        }
    }
    
    return result;
}

// 匯出所有條件類
export {
    SharpeRank,
    SharpeThreshold,
    SharpeStreak,
    GrowthRank,
    GrowthStreak,
    SortSharpe,
    SortIndustry
};
