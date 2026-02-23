/**
 * NotSelected - 未入選條件
 * 
 * 說明: 當持有股票連續 N 期不在買入候選名單時賣出
 */

import { SellConditionBase } from './base.js';

export class NotSelected extends SellConditionBase {
    constructor() {
        super(
            'not_selected',
            '未入選賣出',
            '當持有股票連續 N 期不在買入候選名單時賣出'
        );
        this.params = this.getDefaultParams();
    }
    
    getDefaultParams() {
        return {
            buy_not_selected_periods: 3
        };
    }
    
    getParamConfig() {
        return [
            {
                id: 'buy_not_selected_periods',
                label: '連續期數',
                type: 'number',
                min: 1,
                max: 10,
                step: 1,
                default: 3
            }
        ];
    }
    
    /**
     * 檢查是否連續未入選
     */
    check(ticker, position, context) {
        const { selectionHistory, date } = context;
        const periods = this.params.buy_not_selected_periods || 3;
        
        if (!selectionHistory) {
            return { shouldSell: false, reason: '' };
        }
        
        const dates = Object.keys(selectionHistory).sort();
        const currentIndex = dates.indexOf(date);
        
        if (currentIndex < periods - 1) {
            return { shouldSell: false, reason: '' };
        }
        
        const recentDates = dates.slice(currentIndex - periods + 1, currentIndex + 1);
        
        // 檢查是否連續 N 期都不在候選名單
        let consecutiveNotSelected = 0;
        
        for (const d of recentDates) {
            const selected = selectionHistory[d] || [];
            
            if (!selected.includes(ticker)) {
                consecutiveNotSelected++;
            } else {
                consecutiveNotSelected = 0;
            }
        }
        
        if (consecutiveNotSelected >= periods) {
            return {
                shouldSell: true,
                reason: `連續 ${periods} 期未入選買入名單`
            };
        }
        
        return { shouldSell: false, reason: '' };
    }
}
