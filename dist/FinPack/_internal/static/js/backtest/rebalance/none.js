/**
 * None - 不再平衡策略
 * 
 * 說明: 不執行再平衡，只有在賣出條件觸發時才賣出
 */

import { RebalanceStrategyBase } from './base.js';

export class None extends RebalanceStrategyBase {
    constructor() {
        super(
            'none',
            '不再平衡',
            '不主動再平衡，只有在賣出條件觸發時才清倉'
        );
        this.params = this.getDefaultParams();
    }
    
    getDefaultParams() {
        return {};
    }
    
    /**
     * 永遠不主動再平衡
     */
    shouldRebalance(context) {
        return false;
    }
    
    /**
     * 不執行任何操作
     */
    execute(trade, targetStocks, prices, stockInfo, date, options = {}) {
        return { sells: [], buys: [] };
    }
}
