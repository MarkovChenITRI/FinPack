/**
 * SharpeFail - Sharpe 失格條件
 * 
 * 說明: 當股票連續 N 期掉出 Sharpe Top-K 時賣出
 */

import { SellConditionBase } from './base.js';

export class SharpeFail extends SellConditionBase {
    constructor() {
        super(
            'sharpe_fail',
            'Sharpe 失格',
            '當股票連續 N 期掉出 Sharpe Top-K 時賣出'
        );
        this.params = this.getDefaultParams();
    }
    
    getDefaultParams() {
        return {
            sharpe_disqualify_periods: 3,
            sharpe_disqualify_n: 15
        };
    }
    
    getParamConfig() {
        return [
            {
                id: 'sharpe_disqualify_periods',
                label: '連續期數',
                type: 'number',
                min: 1,
                max: 10,
                step: 1,
                default: 3
            },
            {
                id: 'sharpe_disqualify_n',
                label: 'Top K',
                type: 'number',
                min: 5,
                max: 50,
                step: 5,
                default: 15
            }
        ];
    }
    
    /**
     * 檢查是否觸發 Sharpe 失格
     */
    check(ticker, position, context) {
        const { history, date, market, stockInfo } = context;
        const periods = this.params.sharpe_disqualify_periods || 3;
        const topK = this.params.sharpe_disqualify_n || 15;
        
        if (!history?.sharpeRank) {
            return { shouldSell: false, reason: '' };
        }
        
        const dates = Object.keys(history.sharpeRank).sort();
        const currentIndex = dates.indexOf(date);
        
        if (currentIndex < periods - 1) {
            return { shouldSell: false, reason: '' };
        }
        
        const recentDates = dates.slice(currentIndex - periods + 1, currentIndex + 1);
        const country = stockInfo?.[ticker]?.country || 'US';
        
        // 檢查是否連續 N 期都不在 Top-K
        let consecutiveFail = 0;
        
        for (const d of recentDates) {
            const dayRank = history.sharpeRank[d];
            if (!dayRank) continue;
            
            const ranking = dayRank[country] || [];
            const inTopK = ranking.slice(0, topK).includes(ticker);
            
            if (!inTopK) {
                consecutiveFail++;
            } else {
                consecutiveFail = 0;  // 重置
            }
        }
        
        if (consecutiveFail >= periods) {
            return {
                shouldSell: true,
                reason: `Sharpe 連續 ${periods} 期掉出 Top-${topK}`
            };
        }
        
        return { shouldSell: false, reason: '' };
    }
}
