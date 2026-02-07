/**
 * Concentrated - 集中投入策略
 * 
 * 說明: 只在買入標的排名前 K 有明確領先時才投入
 * （高確信度出手，牛市高報酬但熊市危險）
 */

import { RebalanceStrategyBase } from './base.js';

export class Concentrated extends RebalanceStrategyBase {
    constructor() {
        super(
            'concentrated',
            '集中投入',
            '只在買入標的排名前 K 有明確領先時才投入'
        );
        this.params = this.getDefaultParams();
    }
    
    getDefaultParams() {
        return {
            concentrate_top_k: 3,  // 只投資排名前 K 名
            leadMargin: 0.3       // 領先差距門檻（Sharpe 值差 > 30%）
        };
    }
    
    getParamConfig() {
        return [
            {
                id: 'concentrate_top_k',
                label: '集中投資前 K 名',
                type: 'number',
                min: 1,
                max: 10,
                step: 1,
                default: 3
            },
            {
                id: 'leadMargin',
                label: '領先差距 (%)',
                type: 'number',
                min: 0.1,
                max: 1,
                step: 0.1,
                default: 0.3
            }
        ];
    }
    
    /**
     * 檢查買入標的是否有明確領先
     */
    shouldRebalance(context) {
        const { currentHoldings, targetStocks, sharpeValues, ranking, market } = context;
        const topK = this.params.concentrate_top_k || 3;
        const leadMargin = this.params.leadMargin || 0.3;
        
        const currentSet = new Set(currentHoldings);
        const targetSet = new Set(targetStocks);
        
        // 檢查是否有需要買入的標的
        let needsBuy = false;
        for (const ticker of targetSet) {
            if (!currentSet.has(ticker)) {
                needsBuy = true;
                break;
            }
        }
        
        if (!needsBuy) return false;
        
        if (!sharpeValues || !ranking?.sharpe) {
            return false;
        }
        
        // 取得排名前 K 和 K+1~2K 的股票
        const topKTickers = [];
        const nextKTickers = [];
        
        if (market === 'global' || market === 'us') {
            const usRanking = ranking.sharpe.US || [];
            usRanking.slice(0, topK).forEach(t => topKTickers.push(t));
            usRanking.slice(topK, topK * 2).forEach(t => nextKTickers.push(t));
        }
        if (market === 'global' || market === 'tw') {
            const twRanking = ranking.sharpe.TW || [];
            twRanking.slice(0, topK).forEach(t => topKTickers.push(t));
            twRanking.slice(topK, topK * 2).forEach(t => nextKTickers.push(t));
        }
        
        // 計算 Top-K 的平均 Sharpe
        const topKAvg = this._avgSharpe(topKTickers, sharpeValues);
        
        // 計算 Next-K 的平均 Sharpe
        const nextKAvg = this._avgSharpe(nextKTickers, sharpeValues);
        
        // 如果 nextKAvg 為 0 或負值，且 topKAvg 為正，視為領先
        if (nextKAvg <= 0 && topKAvg > 0) {
            return true;
        }
        
        // 檢查 Top-K 是否明確領先 Next-K（差距 > leadMargin）
        if (nextKAvg > 0) {
            const leadRatio = (topKAvg - nextKAvg) / Math.abs(nextKAvg);
            return leadRatio >= leadMargin;
        }
        
        return false;
    }
    
    /**
     * 計算平均 Sharpe
     */
    _avgSharpe(tickers, sharpeValues) {
        if (tickers.length === 0) return 0;
        
        const sum = tickers.reduce((acc, ticker) => {
            const val = sharpeValues[ticker];
            return acc + (val !== undefined ? val : 0);
        }, 0);
        
        return sum / tickers.length;
    }
}
