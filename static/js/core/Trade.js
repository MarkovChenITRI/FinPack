/**
 * Trade - 交易執行模組
 * 
 * 負責：
 *   - 交易執行邏輯
 *   - 買入/賣出數量計算
 *   - 再平衡執行
 */

export class Trade {
    /**
     * @param {Portfolio} portfolio - 投資組合實例
     * @param {Object} options
     */
    constructor(portfolio, options = {}) {
        this.portfolio = portfolio;
        this.options = {
            amountPerStock: options.amountPerStock || 100000,
            maxPositions: options.maxPositions || 10,
            allowPartialFill: options.allowPartialFill !== false,
            ...options
        };
    }
    
    /**
     * 執行買入
     * @param {string} ticker - 股票代碼
     * @param {number} price - 價格
     * @param {string} country - 國家
     * @param {string} date - 日期
     * @param {Object} options - 覆蓋選項
     * @returns {Object} 交易結果
     */
    executeBuy(ticker, price, country, date, options = {}) {
        const amount = options.amount || this.options.amountPerStock;
        
        // 檢查是否達到最大持倉數
        if (!this.portfolio.hasPosition(ticker) && 
            this.portfolio.getPositionCount() >= this.options.maxPositions) {
            return {
                success: false,
                reason: 'max_positions_reached',
                limit: this.options.maxPositions
            };
        }
        
        // 計算可買股數
        let shares = this._calculateShares(amount, price, country);
        
        if (shares <= 0) {
            return {
                success: false,
                reason: 'amount_too_small'
            };
        }
        
        // 檢查現金是否足夠
        const fee = this.portfolio.calculateFee(shares * price, country);
        const totalCost = shares * price + fee;
        
        if (totalCost > this.portfolio.getCash()) {
            if (this.options.allowPartialFill) {
                // 用可用現金計算最大可買股數
                shares = this._calculateMaxAffordableShares(price, country);
                if (shares <= 0) {
                    return {
                        success: false,
                        reason: 'insufficient_cash'
                    };
                }
            } else {
                return {
                    success: false,
                    reason: 'insufficient_cash'
                };
            }
        }
        
        return this.portfolio.buy(ticker, shares, price, country, date);
    }
    
    /**
     * 執行賣出
     * @param {string} ticker
     * @param {number} price
     * @param {string} date
     * @param {string} reason
     * @param {Object} options
     * @returns {Object}
     */
    executeSell(ticker, price, date, reason = '', options = {}) {
        const shares = options.shares || 0;  // 0 表示全部賣出
        return this.portfolio.sell(ticker, shares, price, date, reason);
    }
    
    /**
     * 執行全部賣出
     * @param {Object} prices - ticker -> price
     * @param {string} date
     * @param {string} reason
     * @returns {Array} 交易結果列表
     */
    executeSellAll(prices, date, reason = '') {
        const results = [];
        const holdings = this.portfolio.getHoldings();
        
        for (const ticker of holdings) {
            const price = prices[ticker];
            if (price !== undefined) {
                const result = this.executeSell(ticker, price, date, reason);
                results.push({ ticker, ...result });
            }
        }
        
        return results;
    }
    
    /**
     * 執行再平衡
     * @param {string[]} targetTickers - 目標持股列表
     * @param {Object} prices - ticker -> price
     * @param {Object} stockInfo - ticker -> {country}
     * @param {string} date
     * @returns {Object} {sells: [], buys: []}
     */
    executeRebalance(targetTickers, prices, stockInfo, date) {
        const results = { sells: [], buys: [] };
        
        // 找出需要賣出的（持有但不在目標中）
        const currentHoldings = new Set(this.portfolio.getHoldings());
        const targetSet = new Set(targetTickers);
        
        for (const ticker of currentHoldings) {
            if (!targetSet.has(ticker)) {
                const price = prices[ticker];
                if (price !== undefined) {
                    const result = this.executeSell(ticker, price, date, 'rebalance');
                    results.sells.push({ ticker, ...result });
                }
            }
        }
        
        // 找出需要買入的（在目標中但未持有）
        for (const ticker of targetTickers) {
            if (!this.portfolio.hasPosition(ticker)) {
                const price = prices[ticker];
                const info = stockInfo[ticker];
                if (price !== undefined && info) {
                    const result = this.executeBuy(ticker, price, info.country, date);
                    results.buys.push({ ticker, ...result });
                }
            }
        }
        
        return results;
    }
    
    /**
     * 計算可買股數
     * @param {number} amount - 預算金額
     * @param {number} price - 價格
     * @param {string} country - 國家
     * @returns {number}
     */
    _calculateShares(amount, price, country) {
        // 台股需要整張(1000股)，美股不限
        if (country.toUpperCase() === 'TW') {
            const lots = Math.floor(amount / (price * 1000));
            return lots * 1000;
        } else {
            return Math.floor(amount / price);
        }
    }
    
    /**
     * 根據可用現金計算最大可買股數
     * @param {number} price
     * @param {string} country
     * @returns {number}
     */
    _calculateMaxAffordableShares(price, country) {
        const cash = this.portfolio.getCash();
        const feeRate = this.portfolio.fees[country.toLowerCase()]?.rate || 0.003;
        
        // 解方程: shares * price * (1 + feeRate) <= cash
        let maxShares = Math.floor(cash / (price * (1 + feeRate)));
        
        // 台股需要整張
        if (country.toUpperCase() === 'TW') {
            maxShares = Math.floor(maxShares / 1000) * 1000;
        }
        
        return maxShares;
    }
    
    /**
     * 預估買入成本
     * @param {string} ticker
     * @param {number} price
     * @param {string} country
     * @param {number} amount
     * @returns {Object}
     */
    estimateBuyCost(ticker, price, country, amount = null) {
        amount = amount || this.options.amountPerStock;
        const shares = this._calculateShares(amount, price, country);
        const cost = shares * price;
        const fee = this.portfolio.calculateFee(cost, country);
        
        return {
            ticker,
            shares,
            price,
            cost,
            fee,
            total: cost + fee
        };
    }
    
    /**
     * 預估賣出收入
     * @param {string} ticker
     * @param {number} price
     * @returns {Object|null}
     */
    estimateSellProceeds(ticker, price) {
        const position = this.portfolio.getPosition(ticker);
        if (!position) return null;
        
        const amount = position.shares * price;
        const fee = this.portfolio.calculateFee(amount, position.country);
        const net = amount - fee;
        const profit = net - (position.shares * position.avgCost);
        
        return {
            ticker,
            shares: position.shares,
            price,
            amount,
            fee,
            net,
            profit,
            profitPct: (profit / (position.shares * position.avgCost)) * 100
        };
    }
}
