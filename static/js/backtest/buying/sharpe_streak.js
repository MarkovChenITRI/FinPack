/**
 * SharpeStreak - Sharpe 連續條件
 * 
 * 類別: A (範圍過濾)
 * 說明: 篩選連續 N 期維持在 Sharpe Top-K 的股票
 */

import { BuyConditionBase } from './base.js';

export class SharpeStreak extends BuyConditionBase {
    constructor() {
        super(
            'sharpe_streak',
            'Sharpe 連續',
            '篩選連續 N 期維持在 Sharpe Top-K 的股票，熊市會完美停買',
            'A'
        );
        this.params = this.getDefaultParams();
    }
    
    getDefaultParams() {
        return {
            sharpe_consecutive_days: 3,
            sharpe_top_n: 15
        };
    }
    
    getParamConfig() {
        return [
            {
                id: 'sharpe_consecutive_days',
                label: '連續期數',
                type: 'number',
                min: 2,
                max: 10,
                step: 1,
                default: 3
            },
            {
                id: 'sharpe_top_n',
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
     * 過濾出連續維持在 Top-K 的股票
     */
    filter(tickers, context) {
        const { history, date, market } = context;
        const periods = this.params.sharpe_consecutive_days || 3;
        const topK = this.params.sharpe_top_n || 15;
        
        if (!history?.sharpeRank) return tickers;
        
        // 取得最近 N 期的日期
        const dates = Object.keys(history.sharpeRank).sort();
        const currentIndex = dates.indexOf(date);
        
        if (currentIndex < periods - 1) {
            // 歷史數據不足
            return [];
        }
        
        const recentDates = dates.slice(currentIndex - periods + 1, currentIndex + 1);
        
        // 找出在所有期間都在 Top-K 的股票
        const consistentTickers = new Set(tickers);
        
        for (const d of recentDates) {
            const dayRank = history.sharpeRank[d];
            if (!dayRank) continue;
            
            const topKSet = new Set();
            
            if (market === 'global' || market === 'us') {
                (dayRank.US || []).slice(0, topK).forEach(t => topKSet.add(t));
            }
            if (market === 'global' || market === 'tw') {
                (dayRank.TW || []).slice(0, topK).forEach(t => topKSet.add(t));
            }
            
            // 移除不在該期 Top-K 的股票
            for (const ticker of consistentTickers) {
                if (!topKSet.has(ticker)) {
                    consistentTickers.delete(ticker);
                }
            }
        }
        
        return Array.from(consistentTickers);
    }
}
