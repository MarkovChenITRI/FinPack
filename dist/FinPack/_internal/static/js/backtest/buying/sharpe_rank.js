/**
 * SharpeRank - Sharpe 排名條件
 * 
 * 類別: A (範圍過濾)
 * 說明: 篩選 Sharpe 排名前 N 名的股票
 */

import { BuyConditionBase } from './base.js';

export class SharpeRank extends BuyConditionBase {
    constructor() {
        super(
            'sharpe_rank',
            'Sharpe 排名',
            '篩選 Sharpe 排名前 N 名的股票，不保證穿越熊市',
            'A'
        );
        this.params = this.getDefaultParams();
    }
    
    getDefaultParams() {
        return {
            sharpe_top_n: 15
        };
    }
    
    getParamConfig() {
        return [
            {
                id: 'sharpe_top_n',
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
     * 過濾出 Sharpe 排名前 N 名的股票
     */
    filter(tickers, context) {
        const { ranking, stockInfo, market } = context;
        const topN = this.params.sharpe_top_n || 15;
        
        if (!ranking?.sharpe) return tickers;
        
        // 根據市場設定決定使用哪些排名
        const selectedTickers = new Set();
        
        if (market === 'global' || market === 'us') {
            const usRanking = ranking.sharpe.US || [];
            usRanking.slice(0, topN).forEach(t => selectedTickers.add(t));
        }
        
        if (market === 'global' || market === 'tw') {
            const twRanking = ranking.sharpe.TW || [];
            twRanking.slice(0, topN).forEach(t => selectedTickers.add(t));
        }
        
        // 返回交集
        return tickers.filter(t => selectedTickers.has(t));
    }
}
