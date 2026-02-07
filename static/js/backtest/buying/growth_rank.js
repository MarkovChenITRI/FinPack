/**
 * GrowthRank - Growth 排名條件
 * 
 * 類別: B (動能過濾)
 * 說明: 篩選 Growth 排名前 N 名的股票
 */

import { BuyConditionBase } from './base.js';

export class GrowthRank extends BuyConditionBase {
    constructor() {
        super(
            'growth_rank',
            'Growth 排名',
            '篩選 Growth（成長率）排名前 N 名的股票，牛市佳但熊市追反彈',
            'B'
        );
        this.params = this.getDefaultParams();
    }
    
    getDefaultParams() {
        return {
            growth_top_k: 15
        };
    }
    
    getParamConfig() {
        return [
            {
                id: 'growth_top_k',
                label: 'Top N',
                type: 'number',
                min: 5,
                max: 50,
                step: 5,
                default: 15
            }
        ];
    }
    
    /**
     * 過濾出 Growth 排名前 N 名的股票
     */
    filter(tickers, context) {
        const { ranking, market } = context;
        const topN = this.params.growth_top_k || 15;
        
        if (!ranking?.growth) return tickers;
        
        const selectedTickers = new Set();
        
        if (market === 'global' || market === 'us') {
            const usRanking = ranking.growth.US || [];
            usRanking.slice(0, topN).forEach(t => selectedTickers.add(t));
        }
        
        if (market === 'global' || market === 'tw') {
            const twRanking = ranking.growth.TW || [];
            twRanking.slice(0, topN).forEach(t => selectedTickers.add(t));
        }
        
        return tickers.filter(t => selectedTickers.has(t));
    }
}
