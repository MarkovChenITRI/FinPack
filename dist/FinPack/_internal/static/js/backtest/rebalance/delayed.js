/**
 * Delayed - 延遲投入策略
 * 
 * 說明: 等市場轉強再進場（Sharpe_top5_avg > 0），避免假突破
 */

import { RebalanceStrategyBase } from './base.js';

export class Delayed extends RebalanceStrategyBase {
    constructor() {
        super(
            'delayed',
            '延遲投入',
            '等市場轉強再進場（Sharpe Top-5 平均 > 0），避免假突破'
        );
        this.params = this.getDefaultParams();
    }
    
    getDefaultParams() {
        return {
            topN: 5,
            sharpeThreshold: 0
        };
    }
    
    getParamConfig() {
        return [
            {
                id: 'topN',
                label: 'Top N 參考',
                type: 'number',
                min: 3,
                max: 15,
                step: 1,
                default: 5
            },
            {
                id: 'sharpeThreshold',
                label: 'Sharpe 門檻',
                type: 'number',
                min: -0.5,
                max: 1,
                step: 0.1,
                default: 0
            }
        ];
    }
    
    /**
     * 檢查市場是否轉強（Sharpe Top-K 平均值 > 門檻）
     */
    shouldRebalance(context) {
        const { sharpeValues, ranking, market, currentHoldings, targetStocks } = context;
        const topN = this.params.topN || 5;
        const threshold = this.params.sharpeThreshold || 0;
        
        // 如果沒有需要買入的，不需要再平衡
        const currentSet = new Set(currentHoldings);
        const targetSet = new Set(targetStocks);
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
        
        // 計算 Sharpe Top-N 的平均值
        const topTickers = [];
        
        if (market === 'global' || market === 'us') {
            const usRanking = ranking.sharpe.US || [];
            usRanking.slice(0, topN).forEach(t => topTickers.push(t));
        }
        if (market === 'global' || market === 'tw') {
            const twRanking = ranking.sharpe.TW || [];
            twRanking.slice(0, topN).forEach(t => topTickers.push(t));
        }
        
        // 計算平均 Sharpe
        const sharpeSum = topTickers.reduce((sum, ticker) => {
            const val = sharpeValues[ticker];
            return sum + (val !== undefined ? val : 0);
        }, 0);
        
        const avgSharpe = topTickers.length > 0 ? sharpeSum / topTickers.length : 0;
        
        // 只在市場轉強時允許再平衡（買入）
        return avgSharpe > threshold;
    }
}
