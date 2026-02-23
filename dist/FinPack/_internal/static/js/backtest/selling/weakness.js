/**
 * Weakness - 相對弱勢條件
 * 
 * 說明: 當股票 Sharpe 排名 > K AND Growth 排名 > K 連續 M 期時賣出
 * （未來性不足即退出）
 */

import { SellConditionBase } from './base.js';

export class Weakness extends SellConditionBase {
    constructor() {
        super(
            'weakness',
            '相對弱勢',
            '當股票 Sharpe 和 Growth 排名同時連續超出門檻時賣出'
        );
        this.params = this.getDefaultParams();
    }
    
    getDefaultParams() {
        return {
            relative_weakness_k: 20,
            relative_weakness_periods: 3
        };
    }
    
    getParamConfig() {
        return [
            {
                id: 'relative_weakness_k',
                label: '排名門檻 (K)',
                type: 'number',
                min: 10,
                max: 50,
                step: 5,
                default: 20
            },
            {
                id: 'relative_weakness_periods',
                label: '連續期數 (M)',
                type: 'number',
                min: 1,
                max: 10,
                step: 1,
                default: 3
            }
        ];
    }
    
    /**
     * 檢查是否相對弱勢（Sharpe_rank > K AND Growth_rank > K 連續 M 期）
     */
    check(ticker, position, context) {
        const { history, date, stockInfo } = context;
        const rankThreshold = this.params.relative_weakness_k || 20;
        const periods = this.params.relative_weakness_periods || 3;
        
        if (!history?.sharpeRank || !history?.growthRank) {
            return { shouldSell: false, reason: '' };
        }
        
        const dates = Object.keys(history.sharpeRank).sort();
        const currentIndex = dates.indexOf(date);
        
        if (currentIndex < periods - 1) {
            return { shouldSell: false, reason: '' };
        }
        
        const recentDates = dates.slice(currentIndex - periods + 1, currentIndex + 1);
        const country = stockInfo?.[ticker]?.country || 'US';
        
        // 檢查是否連續 M 期 Sharpe 排名 > K AND Growth 排名 > K
        let consecutiveWeak = 0;
        
        for (const d of recentDates) {
            const sharpeRank = history.sharpeRank[d];
            const growthRank = history.growthRank[d];
            
            if (!sharpeRank || !growthRank) continue;
            
            const sharpeRanking = sharpeRank[country] || [];
            const growthRanking = growthRank[country] || [];
            
            const sharpeIdx = sharpeRanking.indexOf(ticker);
            const growthIdx = growthRanking.indexOf(ticker);
            
            // 如果不在排名中，視為排名超過門檻
            const sharpeBad = sharpeIdx < 0 || sharpeIdx >= rankThreshold;
            const growthBad = growthIdx < 0 || growthIdx >= rankThreshold;
            
            // 必須同時滿足 Sharpe AND Growth 排名超過門檻
            if (sharpeBad && growthBad) {
                consecutiveWeak++;
            } else {
                consecutiveWeak = 0;  // 重置
            }
        }
        
        if (consecutiveWeak >= periods) {
            return {
                shouldSell: true,
                reason: `Sharpe 和 Growth 排名連續 ${periods} 期同時超過 ${rankThreshold}`
            };
        }
        
        return { shouldSell: false, reason: '' };
    }
}
