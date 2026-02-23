/**
 * Drawdown - 回撤停損條件
 * 
 * 說明: 當股票從買入價下跌超過指定百分比時賣出
 */

import { SellConditionBase } from './base.js';

export class Drawdown extends SellConditionBase {
    constructor() {
        super(
            'drawdown',
            '回撤停損',
            '當股票從買入價或最高價下跌超過指定百分比時賣出'
        );
        this.params = this.getDefaultParams();
    }
    
    getDefaultParams() {
        return {
            price_breakdown_pct: 40,
            fromHighest: false  // true: 從最高價計算，false: 從買入價計算
        };
    }
    
    getParamConfig() {
        return [
            {
                id: 'price_breakdown_pct',
                label: '回撤比例 (%)',
                type: 'number',
                min: 5,
                max: 80,
                step: 5,
                default: 40
            },
            {
                id: 'fromHighest',
                label: '從最高價計算',
                type: 'boolean',
                default: false
            }
        ];
    }
    
    /**
     * 檢查是否觸發回撤停損
     */
    check(ticker, position, context) {
        const { price, priceHistory } = context;
        const drawdownPct = this.params.price_breakdown_pct || 40;
        const fromHighest = this.params.fromHighest || false;
        
        if (!price || !position.avgCost) {
            return { shouldSell: false, reason: '' };
        }
        
        let referencePrice = position.avgCost;
        
        if (fromHighest && priceHistory?.[ticker]) {
            // 計算持有期間的最高價
            const entryDate = position.entryDate;
            const prices = priceHistory[ticker];
            const highestPrice = Math.max(
                ...Object.entries(prices)
                    .filter(([d]) => d >= entryDate)
                    .map(([, p]) => p)
            );
            referencePrice = Math.max(referencePrice, highestPrice);
        }
        
        const currentDrawdown = ((referencePrice - price) / referencePrice) * 100;
        
        if (currentDrawdown >= drawdownPct) {
            return {
                shouldSell: true,
                reason: `回撤 ${currentDrawdown.toFixed(1)}% 超過停損點 ${drawdownPct}%`
            };
        }
        
        return { shouldSell: false, reason: '' };
    }
}
