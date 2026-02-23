/**
 * Portfolio - 投資組合管理模組
 * 
 * 負責：
 *   - 持倉追蹤
 *   - 現金與總值計算
 *   - 部位管理
 */

export class Portfolio {
    /**
     * @param {Object} options
     * @param {number} options.initialCapital - 初始資金
     * @param {Object} options.fees - 手續費結構 {us: {rate, minFee}, tw: {rate, minFee}}
     */
    constructor(options = {}) {
        this.initialCapital = options.initialCapital || 1000000;
        this.fees = options.fees || {
            us: { rate: 0.003, minFee: 15 },   // 美股：0.3%，最低 15 USD
            tw: { rate: 0.006, minFee: 0 }     // 台股：0.6%
        };
        
        this.reset();
    }
    
    /**
     * 重置投資組合
     */
    reset() {
        this.cash = this.initialCapital;
        this.positions = new Map();  // ticker -> {shares, avgCost, country}
        this.history = [];           // 歷史記錄
        this.tradeLog = [];          // 交易紀錄
    }
    
    /**
     * 取得當前持倉
     * @returns {Map} ticker -> position
     */
    getPositions() {
        return new Map(this.positions);
    }
    
    /**
     * 取得持有的股票代碼列表
     * @returns {string[]}
     */
    getHoldings() {
        return Array.from(this.positions.keys());
    }
    
    /**
     * 取得特定股票的持倉
     * @param {string} ticker
     * @returns {Object|null}
     */
    getPosition(ticker) {
        return this.positions.get(ticker) || null;
    }
    
    /**
     * 檢查是否持有特定股票
     * @param {string} ticker
     * @returns {boolean}
     */
    hasPosition(ticker) {
        return this.positions.has(ticker);
    }
    
    /**
     * 取得持倉數量
     * @returns {number}
     */
    getPositionCount() {
        return this.positions.size;
    }
    
    /**
     * 取得現金餘額
     * @returns {number}
     */
    getCash() {
        return this.cash;
    }
    
    /**
     * 計算手續費
     * @param {number} amount - 交易金額
     * @param {string} country - 國家 ('US' or 'TW')
     * @returns {number}
     */
    calculateFee(amount, country) {
        const feeConfig = this.fees[country.toLowerCase()] || this.fees.us;
        const fee = amount * feeConfig.rate;
        return Math.max(fee, feeConfig.minFee);
    }
    
    /**
     * 買入股票
     * @param {string} ticker
     * @param {number} shares - 股數
     * @param {number} price - 價格（原幣：美股 USD，台股 TWD）
     * @param {string} country - 國家
     * @param {string} date - 交易日期
     * @param {Object} options - {exchangeRate: 美元兌台幣匯率}
     * @returns {Object} 交易結果
     */
    buy(ticker, shares, price, country, date, options = {}) {
        const exchangeRate = options.exchangeRate || 32.0;
        const isUS = country.toUpperCase() === 'US';
        
        // 計算金額（TWD）
        // 美股：shares * price(USD) * exchangeRate = TWD
        // 台股：shares * price(TWD) = TWD
        const amountOriginal = shares * price;  // 原幣金額
        const amountTWD = isUS ? amountOriginal * exchangeRate : amountOriginal;
        
        const fee = this.calculateFee(amountTWD, country);
        const totalCostTWD = amountTWD + fee;
        
        if (totalCostTWD > this.cash) {
            return {
                success: false,
                reason: 'insufficient_cash',
                required: totalCostTWD,
                available: this.cash
            };
        }
        
        // 更新現金（以 TWD 計）
        this.cash -= totalCostTWD;
        
        // 更新持倉
        const existing = this.positions.get(ticker);
        if (existing) {
            // 加碼：計算新的平均成本（以原幣計）
            const totalShares = existing.shares + shares;
            const totalCostBasis = (existing.shares * existing.avgCost) + amountOriginal;
            existing.shares = totalShares;
            existing.avgCost = totalCostBasis / totalShares;
        } else {
            // 新開倉（avgCost 存原幣價格）
            this.positions.set(ticker, {
                shares,
                avgCost: price,
                country,
                entryDate: date
            });
        }
        
        // 記錄交易
        const trade = {
            action: 'BUY',
            ticker,
            shares,
            price,           // 原幣價格
            amount: amountOriginal,  // 原幣金額
            amountTWD,       // TWD 金額
            exchangeRate: isUS ? exchangeRate : 1,
            fee,
            totalCost: totalCostTWD,
            country,
            date
        };
        this.tradeLog.push(trade);
        
        return {
            success: true,
            trade
        };
    }
    
    /**
     * 賣出股票
     * @param {string} ticker
     * @param {number} shares - 股數（0 表示全部）
     * @param {number} price - 價格
     * @param {string} date - 交易日期
     * @param {string} reason - 賣出原因
     * @returns {Object} 交易結果
     */
    sell(ticker, shares, price, date, reason = '', options = {}) {
        const position = this.positions.get(ticker);
        
        if (!position) {
            return {
                success: false,
                reason: 'no_position'
            };
        }
        
        const exchangeRate = options.exchangeRate || 32.0;
        const isUS = position.country.toUpperCase() === 'US';
        
        // 如果 shares 為 0，表示全部賣出
        const sellShares = shares === 0 ? position.shares : shares;
        
        if (sellShares > position.shares) {
            return {
                success: false,
                reason: 'insufficient_shares',
                required: sellShares,
                available: position.shares
            };
        }
        
        // 計算金額
        // 美股：shares * price(USD) * exchangeRate = TWD
        // 台股：shares * price(TWD) = TWD
        const amountOriginal = sellShares * price;  // 原幣金額
        const amountTWD = isUS ? amountOriginal * exchangeRate : amountOriginal;
        
        const fee = this.calculateFee(amountTWD, position.country);
        const netProceedsTWD = amountTWD - fee;
        
        // 計算損益（以原幣計算，然後轉 TWD）
        const costBasisOriginal = sellShares * position.avgCost;
        const profitOriginal = amountOriginal - costBasisOriginal;
        const profitPct = (profitOriginal / costBasisOriginal) * 100;
        
        // 更新現金（以 TWD 計）
        this.cash += netProceedsTWD;
        
        // 更新持倉
        if (sellShares === position.shares) {
            // 全部賣出
            this.positions.delete(ticker);
        } else {
            // 部分賣出
            position.shares -= sellShares;
        }
        
        // 記錄交易
        const trade = {
            action: 'SELL',
            ticker,
            shares: sellShares,
            price,                    // 原幣價格
            amount: amountOriginal,   // 原幣金額
            amountTWD,                // TWD 金額
            exchangeRate: isUS ? exchangeRate : 1,
            fee,
            netProceeds: netProceedsTWD,
            country: position.country,
            date,
            reason,
            profit: profitOriginal,   // 原幣損益
            profitPct,
            entryDate: position.entryDate,  // 買入日期
            holdingDays: this._calculateHoldingDays(position.entryDate, date)
        };
        this.tradeLog.push(trade);
        
        return {
            success: true,
            trade
        };
    }
    
    /**
     * 計算投資組合總值（以 TWD 計）
     * @param {Object} prices - ticker -> price（原幣價格）
     * @param {number} exchangeRate - 美元兌台幣匯率
     * @returns {Object} {cash, positionValue, totalValue}
     */
    calculateValue(prices, exchangeRate = 32.0) {
        let positionValue = 0;
        
        for (const [ticker, position] of this.positions) {
            const price = prices[ticker];
            if (price !== undefined) {
                const isUS = position.country.toUpperCase() === 'US';
                // 美股：shares * price(USD) * exchangeRate = TWD
                // 台股：shares * price(TWD) = TWD
                const valueTWD = isUS 
                    ? position.shares * price * exchangeRate
                    : position.shares * price;
                positionValue += valueTWD;
            }
        }
        
        return {
            cash: this.cash,
            positionValue,
            totalValue: this.cash + positionValue
        };
    }
    
    /**
     * 記錄歷史狀態
     * @param {string} date
     * @param {Object} prices - ticker -> price（原幣價格）
     * @param {Object} stockInfo - ticker -> {industry, country}
     * @param {number} exchangeRate - 美元兌台幣匯率
     */
    recordHistory(date, prices, stockInfo = {}, exchangeRate = 32.0) {
        const value = this.calculateValue(prices, exchangeRate);
        
        // 記錄每個持倉的詳細狀態
        const holdings = {};
        for (const [ticker, position] of this.positions) {
            const currentPrice = prices[ticker] || position.avgCost;
            const isUS = position.country.toUpperCase() === 'US';
            
            // 市值（TWD）
            const marketValueTWD = isUS 
                ? position.shares * currentPrice * exchangeRate
                : position.shares * currentPrice;
            
            // 損益百分比（以原幣計算）
            const profit = ((currentPrice - position.avgCost) / position.avgCost * 100);
            const info = stockInfo[ticker] || {};
            
            holdings[ticker] = {
                shares: position.shares,
                avgCost: position.avgCost,
                currentPrice,
                marketValue: marketValueTWD,  // TWD
                profit,
                buyDate: position.entryDate,
                industry: info.industry || '',
                country: position.country,
                exchangeRate: isUS ? exchangeRate : 1
            };
        }
        
        this.history.push({
            date,
            cash: this.cash,
            holdingsValue: value.positionValue,
            equity: value.totalValue,
            holdings,
            positionCount: this.positions.size
        });
    }
    
    /**
     * 取得權益曲線數據（包含每日持有詳情）
     * @returns {Array}
     */
    getEquityCurve() {
        return this.history.map(h => ({
            date: h.date,
            cash: h.cash,
            holdingsValue: h.holdingsValue,
            equity: h.equity,
            holdings: h.holdings || {}
        }));
    }
    
    /**
     * 取得交易紀錄
     * @returns {Array}
     */
    getTradeLog() {
        return [...this.tradeLog];
    }
    
    /**
     * 計算持有天數
     */
    _calculateHoldingDays(entryDate, exitDate) {
        const entry = new Date(entryDate);
        const exit = new Date(exitDate);
        const diffTime = Math.abs(exit - entry);
        return Math.ceil(diffTime / (1000 * 60 * 60 * 24));
    }
    
    /**
     * 匯出投資組合狀態
     * @returns {Object}
     */
    export() {
        return {
            initialCapital: this.initialCapital,
            cash: this.cash,
            positions: Object.fromEntries(this.positions),
            history: this.history,
            tradeLog: this.tradeLog
        };
    }
    
    /**
     * 匯入投資組合狀態
     * @param {Object} data
     */
    import(data) {
        this.initialCapital = data.initialCapital;
        this.cash = data.cash;
        this.positions = new Map(Object.entries(data.positions));
        this.history = data.history;
        this.tradeLog = data.tradeLog;
    }
}
