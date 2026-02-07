/**
 * SimulatorSession - 模擬交易會話
 * 
 * 負責：
 *   - 管理模擬交易的投資組合
 *   - 執行買賣操作
 *   - 持倉追蹤與績效計算
 */

import { Portfolio } from '../core/Portfolio.js';
import { Trade } from '../core/Trade.js';
import { Report } from '../core/Report.js';

export class SimulatorSession {
    /**
     * @param {Object} options
     *   - initialCapital: 初始資金
     *   - fees: 手續費結構
     *   - sessionId: 會話 ID（用於本地儲存）
     */
    constructor(options = {}) {
        this.sessionId = options.sessionId || 'default';
        this.options = {
            initialCapital: options.initialCapital || 1000000,
            fees: options.fees || {
                us: { rate: 0.003, minFee: 15 },
                tw: { rate: 0.006, minFee: 0 }
            }
        };
        
        this.portfolio = new Portfolio({
            initialCapital: this.options.initialCapital,
            fees: this.options.fees
        });
        
        this.trade = new Trade(this.portfolio, {
            amountPerStock: 100000,
            maxPositions: 20
        });
        
        // 嘗試從本地儲存恢復
        this._loadFromStorage();
    }
    
    /**
     * 買入股票
     * @param {string} ticker
     * @param {number} shares
     * @param {number} price
     * @param {string} country
     * @returns {Object}
     */
    buy(ticker, shares, price, country) {
        const date = new Date().toISOString().split('T')[0];
        const result = this.portfolio.buy(ticker, shares, price, country, date);
        
        if (result.success) {
            this._saveToStorage();
        }
        
        return result;
    }
    
    /**
     * 賣出股票
     * @param {string} ticker
     * @param {number} shares - 0 表示全部賣出
     * @param {number} price
     * @returns {Object}
     */
    sell(ticker, shares, price) {
        const date = new Date().toISOString().split('T')[0];
        const result = this.portfolio.sell(ticker, shares, price, date, 'manual');
        
        if (result.success) {
            this._saveToStorage();
        }
        
        return result;
    }
    
    /**
     * 取得當前持倉
     * @returns {Array}
     */
    getPositions() {
        const positions = [];
        
        for (const [ticker, pos] of this.portfolio.getPositions()) {
            positions.push({
                ticker,
                shares: pos.shares,
                avgCost: pos.avgCost,
                country: pos.country,
                entryDate: pos.entryDate,
                costBasis: pos.shares * pos.avgCost
            });
        }
        
        return positions;
    }
    
    /**
     * 更新持倉的當前價格與損益
     * @param {Object} prices - ticker -> price
     * @returns {Array}
     */
    getPositionsWithPL(prices) {
        const positions = this.getPositions();
        
        return positions.map(pos => {
            const currentPrice = prices[pos.ticker];
            const marketValue = currentPrice ? pos.shares * currentPrice : null;
            const unrealizedPL = marketValue ? marketValue - pos.costBasis : null;
            const unrealizedPLPct = unrealizedPL ? (unrealizedPL / pos.costBasis) * 100 : null;
            
            return {
                ...pos,
                currentPrice,
                marketValue,
                unrealizedPL,
                unrealizedPLPct
            };
        });
    }
    
    /**
     * 取得帳戶摘要
     * @param {Object} prices - 當前價格
     * @returns {Object}
     */
    getSummary(prices = {}) {
        const value = this.portfolio.calculateValue(prices);
        const positions = this.getPositionsWithPL(prices);
        
        // 計算未實現損益
        const unrealizedPL = positions.reduce((sum, p) => sum + (p.unrealizedPL || 0), 0);
        
        // 計算已實現損益（從交易紀錄）
        const trades = this.portfolio.getTradeLog();
        const realizedPL = trades
            .filter(t => t.action === 'SELL')
            .reduce((sum, t) => sum + (t.profit || 0), 0);
        
        return {
            initialCapital: this.options.initialCapital,
            cash: value.cash,
            positionValue: value.positionValue,
            totalValue: value.totalValue,
            positionCount: positions.length,
            unrealizedPL,
            realizedPL,
            totalPL: unrealizedPL + realizedPL,
            returnPct: ((value.totalValue - this.options.initialCapital) / this.options.initialCapital) * 100
        };
    }
    
    /**
     * 取得交易歷史
     * @returns {Array}
     */
    getTradeHistory() {
        return this.portfolio.getTradeLog();
    }
    
    /**
     * 取得績效報告
     * @returns {Object}
     */
    getReport() {
        const report = new Report(this.portfolio);
        return report.calculateMetrics();
    }
    
    /**
     * 預估買入
     * @param {string} ticker
     * @param {number} amount - 預算金額
     * @param {number} price
     * @param {string} country
     * @returns {Object}
     */
    estimateBuy(ticker, amount, price, country) {
        return this.trade.estimateBuyCost(ticker, price, country, amount);
    }
    
    /**
     * 預估賣出
     * @param {string} ticker
     * @param {number} price
     * @returns {Object|null}
     */
    estimateSell(ticker, price) {
        return this.trade.estimateSellProceeds(ticker, price);
    }
    
    /**
     * 重置會話
     */
    reset() {
        this.portfolio.reset();
        this._saveToStorage();
    }
    
    /**
     * 儲存到本地儲存
     */
    _saveToStorage() {
        try {
            const data = this.portfolio.export();
            localStorage.setItem(`finpack_simulator_${this.sessionId}`, JSON.stringify(data));
        } catch (e) {
            console.warn('無法儲存模擬交易數據:', e);
        }
    }
    
    /**
     * 從本地儲存載入
     */
    _loadFromStorage() {
        try {
            const saved = localStorage.getItem(`finpack_simulator_${this.sessionId}`);
            if (saved) {
                const data = JSON.parse(saved);
                this.portfolio.import(data);
                console.log('✅ 已恢復模擬交易數據');
            }
        } catch (e) {
            console.warn('無法載入模擬交易數據:', e);
        }
    }
    
    /**
     * 匯出會話數據
     * @returns {Object}
     */
    export() {
        return {
            sessionId: this.sessionId,
            options: this.options,
            portfolio: this.portfolio.export(),
            exportTime: new Date().toISOString()
        };
    }
    
    /**
     * 匯入會話數據
     * @param {Object} data
     */
    import(data) {
        if (data.options) {
            this.options = data.options;
        }
        if (data.portfolio) {
            this.portfolio.import(data.portfolio);
        }
        this._saveToStorage();
    }
}
