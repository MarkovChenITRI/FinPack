/**
 * SortSharpe - 按 Sharpe 排序選股
 * 
 * 類別: C (挑選排序)
 * 說明: 從通過 A/B 條件的股票中，按 Sharpe 排序選取前 N 檔
 */

import { BuyConditionBase } from './base.js';

export class SortSharpe extends BuyConditionBase {
    constructor() {
        super(
            'sort_sharpe',
            '按 Sharpe 排序',
            '從候選股票中按 Sharpe 排序選取前 N 檔',
            'C'
        );
        this.params = this.getDefaultParams();
    }
    
    getDefaultParams() {
        return {
            selectN: 5
        };
    }
    
    getParamConfig() {
        return [
            {
                id: 'selectN',
                label: '選取數量',
                type: 'number',
                min: 1,
                max: 20,
                step: 1,
                default: 5
            }
        ];
    }
    
    /**
     * 按 Sharpe 排序選取股票
     */
    filter(tickers, context) {
        const { sharpeValues } = context;
        const { selectN } = this.params;
        
        if (!sharpeValues || tickers.length === 0) return [];
        
        // 排序並選取前 N 檔
        return tickers
            .filter(t => sharpeValues[t] !== undefined)
            .sort((a, b) => (sharpeValues[b] || 0) - (sharpeValues[a] || 0))
            .slice(0, selectN);
    }
}
