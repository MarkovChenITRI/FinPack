/**
 * SharpeThreshold - Sharpe 門檻條件
 * 
 * 類別: A (範圍過濾)
 * 說明: 篩選 Sharpe 值超過門檻的股票，熊市會自動停買
 */

import { BuyConditionBase } from './base.js';

export class SharpeThreshold extends BuyConditionBase {
    constructor() {
        super(
            'sharpe_threshold',
            'Sharpe 門檻',
            '篩選 Sharpe 值超過門檻的股票，熊市會自動減少買入',
            'A'
        );
        this.params = this.getDefaultParams();
    }
    
    getDefaultParams() {
        return {
            sharpe_threshold: 0.5
        };
    }
    
    getParamConfig() {
        return [
            {
                id: 'sharpe_threshold',
                label: '門檻值',
                type: 'number',
                min: 0,
                max: 3,
                step: 0.1,
                default: 0.5
            }
        ];
    }
    
    /**
     * 過濾出 Sharpe 值超過門檻的股票
     */
    filter(tickers, context) {
        const { sharpeValues } = context;
        const threshold = this.params.sharpe_threshold || 0.5;
        
        if (!sharpeValues) return tickers;
        
        return tickers.filter(ticker => {
            const sharpe = sharpeValues[ticker];
            return sharpe !== undefined && sharpe >= threshold;
        });
    }
}
