/**
 * SortIndustry - 按產業分散選股
 * 
 * 類別: C (挑選排序)
 * 說明: 從每個產業中各選取 Sharpe 最高的股票，實現產業分散
 */

import { BuyConditionBase } from './base.js';

export class SortIndustry extends BuyConditionBase {
    constructor() {
        super(
            'sort_industry',
            '產業分散',
            '從每個產業中各選取 Sharpe 最高的股票，實現產業分散',
            'C'
        );
        this.params = this.getDefaultParams();
    }
    
    getDefaultParams() {
        return {
            selectN: 5,
            perIndustry: 1
        };
    }
    
    getParamConfig() {
        return [
            {
                id: 'selectN',
                label: '總選取數量',
                type: 'number',
                min: 1,
                max: 20,
                step: 1,
                default: 5
            },
            {
                id: 'perIndustry',
                label: '每產業上限',
                type: 'number',
                min: 1,
                max: 5,
                step: 1,
                default: 1
            }
        ];
    }
    
    /**
     * 按產業分散選取股票
     */
    filter(tickers, context) {
        const { sharpeValues, stockInfo } = context;
        const { selectN, perIndustry } = this.params;
        
        if (!sharpeValues || !stockInfo || tickers.length === 0) return [];
        
        // 按產業分組
        const industryGroups = {};
        
        for (const ticker of tickers) {
            const info = stockInfo[ticker];
            if (!info) continue;
            
            const industry = info.industry || '未分類';
            if (!industryGroups[industry]) {
                industryGroups[industry] = [];
            }
            industryGroups[industry].push({
                ticker,
                sharpe: sharpeValues[ticker] || 0
            });
        }
        
        // 每個產業按 Sharpe 排序
        for (const industry in industryGroups) {
            industryGroups[industry].sort((a, b) => b.sharpe - a.sharpe);
        }
        
        // 輪流從每個產業選取
        const selected = [];
        const industries = Object.keys(industryGroups).sort((a, b) => {
            // 按產業內最高 Sharpe 排序
            return (industryGroups[b][0]?.sharpe || 0) - (industryGroups[a][0]?.sharpe || 0);
        });
        
        const industryCount = {};
        let round = 0;
        
        while (selected.length < selectN && round < perIndustry) {
            for (const industry of industries) {
                if (selected.length >= selectN) break;
                
                const count = industryCount[industry] || 0;
                if (count >= perIndustry) continue;
                
                const stock = industryGroups[industry][count];
                if (stock) {
                    selected.push(stock.ticker);
                    industryCount[industry] = count + 1;
                }
            }
            round++;
        }
        
        return selected;
    }
}
