/**
 * Trade - 交易執行模組
 * 
 * 負責：
 *   - 交易執行邏輯
 *   - 買入/賣出數量計算
 *   - 再平衡執行
 * 
 * 匯率處理：
 *   - amountPerStock 為 TWD 金額
 *   - 買入美股時使用當日匯率換算 USD
 */

export class Trade {
    /**
     * @param {Portfolio} portfolio - 投資組合實例
     * @param {Object} options
     */
    constructor(portfolio, options = {}) {
        this.portfolio = portfolio;
        this.options = {
            amountPerStock: options.amountPerStock || 100000,  // TWD
            maxPositions: options.maxPositions || 10,
            allowPartialFill: options.allowPartialFill !== false,
            defaultExchangeRate: options.defaultExchangeRate || 32.0,
            ...options
        };
    }
    
    /**
     * 執行買入
     * @param {string} ticker - 股票代碼
     * @param {number} price - 價格（美股為 USD，台股為 TWD）
     * @param {string} country - 國家 ('US' or 'TW')
     * @param {string} date - 日期
     * @param {Object} options - 覆蓋選項
     *   - amount: 投入金額 (TWD)
     *   - exchangeRate: 當日美元兌台幣匯率（僅美股需要）
     * @returns {Object} 交易結果
     */
    executeBuy(ticker, price, country, date, options = {}) {
        const amountTWD = options.amount || this.options.amountPerStock;
        const exchangeRate = options.exchangeRate || this.options.defaultExchangeRate;
        
        // 檢查是否達到最大持倉數
        if (!this.portfolio.hasPosition(ticker) && 
            this.portfolio.getPositionCount() >= this.options.maxPositions) {
            return {
                success: false,
                reason: 'max_positions_reached',
                limit: this.options.maxPositions
            };
        }
        
        // 計算可買股數（考慮匯率）
        let shares = this._calculateShares(amountTWD, price, country, exchangeRate);
        
        if (shares <= 0) {
            return {
                success: false,
                reason: 'amount_too_small'
            };
        }
        
        // 計算實際花費（TWD）
        // 美股：shares * price(USD) * exchangeRate = TWD
        // 台股：shares * price(TWD) = TWD
        const costInTWD = country.toUpperCase() === 'US' 
            ? shares * price * exchangeRate 
            : shares * price;
        
        // 手續費（以 TWD 計算）
        const fee = this.portfolio.calculateFee(costInTWD, country);
        const totalCostTWD = costInTWD + fee;
        
        if (totalCostTWD > this.portfolio.getCash()) {
            if (this.options.allowPartialFill) {
                // 用可用現金計算最大可買股數
                shares = this._calculateMaxAffordableShares(price, country, exchangeRate);
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
        
        // 執行買入（Portfolio 內部以 TWD 管理現金）
        return this.portfolio.buy(ticker, shares, price, country, date, { exchangeRate });
    }
    
    /**
     * 執行賣出
     * @param {string} ticker
     * @param {number} price
     * @param {string} date
     * @param {string} reason
     * @param {Object} options - {shares, exchangeRate}
     * @returns {Object}
     */
    executeSell(ticker, price, date, reason = '', options = {}) {
        const shares = options.shares || 0;  // 0 表示全部賣出
        const exchangeRate = options.exchangeRate || this.options.defaultExchangeRate;
        return this.portfolio.sell(ticker, shares, price, date, reason, { exchangeRate });
    }
    
    /**
     * 執行全部賣出
     * @param {Object} prices - ticker -> price
     * @param {string} date
     * @param {string} reason
     * @param {Object} options - {exchangeRate}
     * @returns {Array} 交易結果列表
     */
    executeSellAll(prices, date, reason = '', options = {}) {
        const results = [];
        const holdings = this.portfolio.getHoldings();
        const exchangeRate = options.exchangeRate || this.options.defaultExchangeRate;
        
        for (const ticker of holdings) {
            const price = prices[ticker];
            if (price !== undefined) {
                const result = this.executeSell(ticker, price, date, reason, { exchangeRate });
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
     * @param {Object} options - {exchangeRate: 當日匯率}
     * @returns {Object} {sells: [], buys: []}
     */
    executeRebalance(targetTickers, prices, stockInfo, date, options = {}) {
        const results = { sells: [], buys: [] };
        const exchangeRate = options.exchangeRate || this.options.defaultExchangeRate;
        
        // 找出需要賣出的（持有但不在目標中）
        const currentHoldings = new Set(this.portfolio.getHoldings());
        const targetSet = new Set(targetTickers);
        
        for (const ticker of currentHoldings) {
            if (!targetSet.has(ticker)) {
                const price = prices[ticker];
                if (price !== undefined) {
                    const result = this.executeSell(ticker, price, date, 'rebalance', { exchangeRate });
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
                    const result = this.executeBuy(ticker, price, info.country, date, { exchangeRate });
                    results.buys.push({ ticker, ...result });
                }
            }
        }
        
        return results;
    }
    
    /**
     * 計算可買股數
     * @param {number} amountTWD - 預算金額 (TWD)
     * @param {number} price - 價格（美股為 USD，台股為 TWD）
     * @param {string} country - 國家
     * @param {number} exchangeRate - 美元兌台幣匯率
     * @returns {number}
     */
    _calculateShares(amountTWD, price, country, exchangeRate = 32.0) {
        if (country.toUpperCase() === 'TW') {
            // 台股：TWD / TWD = 股數，需要整張(1000股)
            const lots = Math.floor(amountTWD / (price * 1000));
            return lots * 1000;
        } else {
            // 美股：TWD -> USD -> 股數
            // amountTWD / exchangeRate = USD 金額
            // USD 金額 / price(USD) = 股數
            const amountUSD = amountTWD / exchangeRate;
            return Math.floor(amountUSD / price);
        }
    }
    
    /**
     * 根據可用現金計算最大可買股數
     * @param {number} price - 價格（美股為 USD，台股為 TWD）
     * @param {string} country
     * @param {number} exchangeRate - 美元兌台幣匯率
     * @returns {number}
     */
    _calculateMaxAffordableShares(price, country, exchangeRate = 32.0) {
        const cashTWD = this.portfolio.getCash();
        const feeRate = this.portfolio.fees[country.toLowerCase()]?.rate || 0.003;
        
        if (country.toUpperCase() === 'TW') {
            // 台股：cash(TWD) / (price(TWD) * (1 + fee))
            let maxShares = Math.floor(cashTWD / (price * (1 + feeRate)));
            maxShares = Math.floor(maxShares / 1000) * 1000;
            return maxShares;
        } else {
            // 美股：cash(TWD) / exchangeRate = USD，再除以 price
            // 解方程: shares * price(USD) * exchangeRate * (1 + feeRate) <= cashTWD
            const maxShares = Math.floor(cashTWD / (price * exchangeRate * (1 + feeRate)));
            return maxShares;
        }
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
