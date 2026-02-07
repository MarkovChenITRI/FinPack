/**
 * GrowthFail - Growth 失格條件
 * 
 * 說明: 當股票最近 X 天 Growth 平均值 < 0 時賣出（趨勢斷裂）
 */

import { SellConditionBase } from './base.js';

export class GrowthFail extends SellConditionBase {
    constructor() {
        super(
            'growth_fail',
            'Growth 失格',
            '當股票最近 X 天 Growth 平均值 < 0 時賣出（趨勢斷裂）'
        );
        this.params = this.getDefaultParams();
    }
    
    getDefaultParams() {
        return {
            growth_disqualify_days: 5,
            threshold: 0
        };
    }
    
    getParamConfig() {
        return [
            {
                id: 'growth_disqualify_days',
                label: '平均期數',
                type: 'number',
                min: 1,
                max: 20,
                step: 1,
                default: 5
            },
            {
                id: 'threshold',
                label: '門檻值',
                type: 'number',
                min: -0.5,
                max: 0.5,
                step: 0.05,
                default: 0
            }
        ];
    }
    
    /**
     * 檢查是否觸發 Growth 失格（平均值 < 門檻）
     */
    check(ticker, position, context) {
        const { history, date } = context;
        const periods = this.params.growth_disqualify_days || 5;
        const threshold = this.params.threshold || 0;
        
        if (!history?.growthValues) {
            return { shouldSell: false, reason: '' };
        }
        
        const dates = Object.keys(history.growthValues).sort();
        const currentIndex = dates.indexOf(date);
        
        if (currentIndex < periods - 1) {
            return { shouldSell: false, reason: '' };
        }
        
        const recentDates = dates.slice(currentIndex - periods + 1, currentIndex + 1);
        
        // 計算最近 N 天的 Growth 平均值
        const growthValues = [];
        for (const d of recentDates) {
            const growth = history.growthValues[d]?.[ticker];
            if (growth !== undefined) {
                growthValues.push(growth);
            }
        }
        
        if (growthValues.length === 0) {
            return { shouldSell: false, reason: '' };
        }
        
        const avgGrowth = growthValues.reduce((a, b) => a + b, 0) / growthValues.length;
        
        if (avgGrowth < threshold) {
            return {
                shouldSell: true,
                reason: `最近 ${periods} 期 Growth 平均值 ${avgGrowth.toFixed(3)} < ${threshold}`
            };
        }
        
        return { shouldSell: false, reason: '' };
    }
}
