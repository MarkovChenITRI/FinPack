/**
 * GrowthStreak - Growth 連續條件
 * 
 * 類別: B (動能過濾)
 * 說明: 篩選連續 N 期維持 Growth 排名 ≤ 50% 的股票（驗證持續動能）
 */

import { BuyConditionBase } from './base.js';

export class GrowthStreak extends BuyConditionBase {
    constructor() {
        super(
            'growth_streak',
            'Growth 連續',
            '篩選連續 N 期維持 Growth 排名前 50% 的股票，驗證真實動能',
            'B'
        );
        this.params = this.getDefaultParams();
    }
    
    getDefaultParams() {
        return {
            growth_consecutive_days: 3,
            rankPercentile: 50  // 排名前 50%
        };
    }
    
    getParamConfig() {
        return [
            {
                id: 'growth_consecutive_days',
                label: '連續期數',
                type: 'number',
                min: 2,
                max: 10,
                step: 1,
                default: 3
            },
            {
                id: 'rankPercentile',
                label: '排名百分位 (%)',
                type: 'number',
                min: 10,
                max: 100,
                step: 10,
                default: 50
            }
        ];
    }
    
    /**
     * 過濾出連續維持 Growth 排名前 X% 的股票
     */
    filter(tickers, context) {
        const { history, date, market } = context;
        const periods = this.params.growth_consecutive_days || 3;
        const percentile = this.params.rankPercentile || 50;
        
        if (!history?.growthRank) return tickers;
        
        // 取得最近 N 期的日期
        const dates = Object.keys(history.growthRank).sort();
        const currentIndex = dates.indexOf(date);
        
        if (currentIndex < periods - 1) {
            return [];
        }
        
        const recentDates = dates.slice(currentIndex - periods + 1, currentIndex + 1);
        
        // 找出在所有期間都在排名前 X% 的股票
        const consistentTickers = new Set(tickers);
        
        for (const d of recentDates) {
            const dayRank = history.growthRank[d];
            if (!dayRank) continue;
            
            const topPctSet = new Set();
            
            // 根據市場設定決定使用哪些排名
            if (market === 'global' || market === 'us') {
                const usRanking = dayRank.US || [];
                const topN = Math.ceil(usRanking.length * percentile / 100);
                usRanking.slice(0, topN).forEach(t => topPctSet.add(t));
            }
            if (market === 'global' || market === 'tw') {
                const twRanking = dayRank.TW || [];
                const topN = Math.ceil(twRanking.length * percentile / 100);
                twRanking.slice(0, topN).forEach(t => topPctSet.add(t));
            }
            
            // 移除不在該期排名前 X% 的股票
            for (const ticker of consistentTickers) {
                if (!topPctSet.has(ticker)) {
                    consistentTickers.delete(ticker);
                }
            }
        }
        
        return Array.from(consistentTickers);
    }
}
