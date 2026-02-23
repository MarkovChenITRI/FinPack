/**
 * Batch - 分批投入策略
 * 
 * 說明: 固定比例投入（如每次 20%），平滑成本，降低擇時風險
 */

import { RebalanceStrategyBase } from './base.js';

export class Batch extends RebalanceStrategyBase {
    constructor() {
        super(
            'batch',
            '分批投入',
            '固定比例投入（如每次 20%），平滑成本，降低擇時風險'
        );
        this.params = this.getDefaultParams();
    }
    
    getDefaultParams() {
        return {
            investRatio: 0.2  // 每次投入可用現金的 20%
        };
    }
    
    getParamConfig() {
        return [
            {
                id: 'investRatio',
                label: '投入比例 (%)',
                type: 'number',
                min: 10,
                max: 100,
                step: 10,
                default: 20,
                transform: v => v / 100  // UI 顯示 20，內部用 0.2
            }
        ];
    }
    
    /**
     * 分批投入：每次只允許投入一定比例，平滑成本
     * 返回 true 表示允許投入（但金額由 execute 中的比例控制）
     */
    shouldRebalance(context) {
        const { currentHoldings, targetStocks } = context;
        
        // 檢查是否有需要買入的標的
        const currentSet = new Set(currentHoldings);
        const targetSet = new Set(targetStocks);
        
        for (const ticker of targetSet) {
            if (!currentSet.has(ticker)) {
                return true;  // 有新標的需要買入
            }
        }
        
        return false;
    }
    
    /**
     * 執行分批投入再平衡
     * 只投入可用現金的固定比例，平滑成本
     */
    execute(trade, targetStocks, prices, stockInfo, date, options = {}) {
        const results = { sells: [], buys: [] };
        const investRatio = this.params.investRatio || 0.2;
        const exchangeRate = options.exchangeRate || 32.0;
        
        // 找出需要買入的（在目標中但未持有）
        const toBuy = targetStocks.filter(t => !trade.portfolio.hasPosition(t));
        
        if (toBuy.length === 0) return results;
        
        // 計算本次可投入的總金額 = 現金 × 投入比例
        const availableCash = trade.portfolio.getCash();
        const investAmount = availableCash * investRatio;
        
        // 平均分配到要買的標的
        const amountPerStock = investAmount / toBuy.length;
        
        for (const ticker of toBuy) {
            const price = prices[ticker];
            const info = stockInfo[ticker];
            
            if (price !== undefined && info) {
                const result = trade.executeBuy(ticker, price, info.country, date, {
                    amount: amountPerStock,
                    exchangeRate
                });
                results.buys.push({ ticker, ...result });
            }
        }
        
        return results;
    }
    
    /**
     * 返回本次應該投入的現金比例
     */
    getInvestRatio() {
        return this.params.investRatio || 0.2;
    }
}
