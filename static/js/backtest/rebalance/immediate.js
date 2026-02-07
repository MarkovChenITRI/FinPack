/**
 * Immediate - 立即再平衡策略
 * 
 * 說明: 每次選股變動時立即執行再平衡
 */

import { RebalanceStrategyBase } from './base.js';

export class Immediate extends RebalanceStrategyBase {
    constructor() {
        super(
            'immediate',
            '立即再平衡',
            '每次選股變動時立即執行再平衡，賣出舊股買入新股'
        );
        this.params = this.getDefaultParams();
    }
    
    getDefaultParams() {
        return {};
    }
    
    /**
     * 只要目標股票與當前持倉不同就再平衡
     */
    shouldRebalance(context) {
        const { currentHoldings, targetStocks } = context;
        
        const currentSet = new Set(currentHoldings);
        const targetSet = new Set(targetStocks);
        
        // 檢查是否有不同
        if (currentSet.size !== targetSet.size) return true;
        
        for (const ticker of currentSet) {
            if (!targetSet.has(ticker)) return true;
        }
        
        return false;
    }
}
