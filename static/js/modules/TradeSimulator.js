/**
 * 交易模擬器
 * 
 * 功能：
 * - 設定初始本金（台幣）
 * - 買入/賣出股票（買入用最高價，賣出用最低價）
 * - 記錄交易歷史
 * - 即時計算持倉市值和損益
 */
export class TradeSimulator {
    constructor(exchangeRate = 32.0) {
        this.initialCapital = 1000000;  // 初始本金（台幣）
        this.cash = 1000000;            // 現金餘額
        this.exchangeRate = exchangeRate;
        this.holdings = {};             // {ticker: {quantity, avgCost, country}}
        this.trades = [];               // 交易紀錄
        this.selectedDate = null;       // 鎖定的交易日期（點擊選定）
        this.displayDate = null;        // 顯示用日期（滑鼠滑動）
        this.stockList = [];            // 股票清單
        
        this.tradeIdCounter = 0;
    }
    
    async init() {
        // 載入股票清單
        await this.loadStockList();
        
        // 綁定事件
        this.bindEvents();
        
        // 更新顯示
        this.updateDisplay();
    }
    
    async loadStockList() {
        try {
            const response = await fetch('/api/stocks');
            const data = await response.json();
            this.stockList = data.stocks || [];
            
            // 填充股票下拉選單
            const select = document.getElementById('trade-stock');
            select.innerHTML = '<option value="">-- 選擇股票 --</option>';
            
            // 按國家分組並排序
            const usStocks = this.stockList.filter(s => s.country === 'US').sort((a, b) => a.ticker.localeCompare(b.ticker));
            const twStocks = this.stockList.filter(s => s.country === 'TW').sort((a, b) => a.ticker.localeCompare(b.ticker));
            
            if (usStocks.length > 0) {
                const usGroup = document.createElement('optgroup');
                usGroup.label = '🇺🇸 美股';
                usStocks.forEach(stock => {
                    const option = document.createElement('option');
                    option.value = stock.ticker;
                    option.textContent = `${stock.ticker} (${stock.industry})`;
                    option.dataset.country = 'US';
                    usGroup.appendChild(option);
                });
                select.appendChild(usGroup);
            }
            
            if (twStocks.length > 0) {
                const twGroup = document.createElement('optgroup');
                twGroup.label = '🇹🇼 台股';
                twStocks.forEach(stock => {
                    const option = document.createElement('option');
                    option.value = stock.ticker;
                    option.textContent = `${stock.ticker} (${stock.industry})`;
                    option.dataset.country = 'TW';
                    twGroup.appendChild(option);
                });
                select.appendChild(twGroup);
            }
            
            console.log(`✅ 載入 ${this.stockList.length} 檔股票`);
        } catch (error) {
            console.error('載入股票清單失敗:', error);
        }
    }
    
    bindEvents() {
        // 重設本金按鈕
        document.getElementById('reset-capital-btn').addEventListener('click', () => {
            this.resetCapital();
        });
        
        // 執行交易按鈕
        document.getElementById('submit-trade-btn').addEventListener('click', () => {
            this.submitTrade();
        });
        
        // 操作切換（買入/賣出）
        document.getElementById('trade-action').addEventListener('change', (e) => {
            this.onActionChange(e.target.value);
        });
        
        // 本金輸入變更
        document.getElementById('initial-capital').addEventListener('change', (e) => {
            const value = parseFloat(e.target.value) || 0;
            if (value > 0 && this.trades.length === 0) {
                this.initialCapital = value;
                this.cash = value;
                this.updateDisplay();
            }
        });
        
        // 監聽 K 線日期滑動事件（用於即時更新持倉市值）
        window.addEventListener('kline-date-change', (e) => {
            // 只更新市值計算用的日期，不改變交易日期
            this.displayDate = e.detail.date;
            // 重新計算持倉市值
            this.updateDisplay();
        });
        
        // 監聽 K 線日期鎖定事件（點擊鎖定，用於交易）
        window.addEventListener('kline-date-locked', (e) => {
            this.selectedDate = e.detail.date;
            this.displayDate = e.detail.date;
            this.updateTradeDateDisplay();
            this.updateDisplay();
        });
        
        // 相容舊的 kline-clicked 事件
        window.addEventListener('kline-clicked', (e) => {
            this.selectedDate = e.detail.date;
            this.displayDate = e.detail.date;
            this.updateTradeDateDisplay();
            this.updateDisplay();
        });
    }
    
    /**
     * 操作切換（買入/賣出）
     */
    onActionChange(action) {
        const amountField = document.getElementById('trade-amount-field');
        const stockSelect = document.getElementById('trade-stock');
        
        if (action === 'sell') {
            // 賣出：隱藏金額欄位，只顯示持倉股票
            amountField.style.display = 'none';
            this.updateStockSelectForSell();
        } else {
            // 買入：顯示金額欄位，顯示完整股票清單
            amountField.style.display = '';
            this.updateStockSelectForBuy();
        }
    }
    
    /**
     * 更新股票清單（買入模式：所有股票）
     */
    updateStockSelectForBuy() {
        const select = document.getElementById('trade-stock');
        select.innerHTML = '<option value="">-- 選擇股票 --</option>';
        
        // 按名稱排序
        const usStocks = this.stockList.filter(s => s.country === 'US').sort((a, b) => a.ticker.localeCompare(b.ticker));
        const twStocks = this.stockList.filter(s => s.country === 'TW').sort((a, b) => a.ticker.localeCompare(b.ticker));
        
        if (usStocks.length > 0) {
            const usGroup = document.createElement('optgroup');
            usGroup.label = '🇺🇸 美股';
            usStocks.forEach(stock => {
                const option = document.createElement('option');
                option.value = stock.ticker;
                option.textContent = `${stock.ticker} (${stock.industry})`;
                option.dataset.country = 'US';
                usGroup.appendChild(option);
            });
            select.appendChild(usGroup);
        }
        
        if (twStocks.length > 0) {
            const twGroup = document.createElement('optgroup');
            twGroup.label = '🇹🇼 台股';
            twStocks.forEach(stock => {
                const option = document.createElement('option');
                option.value = stock.ticker;
                option.textContent = `${stock.ticker} (${stock.industry})`;
                option.dataset.country = 'TW';
                twGroup.appendChild(option);
            });
            select.appendChild(twGroup);
        }
    }
    
    /**
     * 更新股票清單（賣出模式：僅持倉股票）
     */
    updateStockSelectForSell() {
        const select = document.getElementById('trade-stock');
        select.innerHTML = '<option value="">-- 選擇持倉 --</option>';
        
        const holdingTickers = Object.keys(this.holdings);
        
        if (holdingTickers.length === 0) {
            const option = document.createElement('option');
            option.value = '';
            option.textContent = '（無持倉）';
            option.disabled = true;
            select.appendChild(option);
            return;
        }
        
        // 按國家分組並排序
        const usHoldings = holdingTickers.filter(t => this.holdings[t].country === 'US').sort();
        const twHoldings = holdingTickers.filter(t => this.holdings[t].country === 'TW').sort();
        
        if (usHoldings.length > 0) {
            const usGroup = document.createElement('optgroup');
            usGroup.label = '🇺🇸 美股持倉';
            usHoldings.forEach(ticker => {
                const holding = this.holdings[ticker];
                const qtyStr = holding.quantity.toFixed(4).replace(/\.?0+$/, '');
                const option = document.createElement('option');
                option.value = ticker;
                option.textContent = `${ticker} × ${qtyStr} 股`;
                usGroup.appendChild(option);
            });
            select.appendChild(usGroup);
        }
        
        if (twHoldings.length > 0) {
            const twGroup = document.createElement('optgroup');
            twGroup.label = '🇹🇼 台股持倉';
            twHoldings.forEach(ticker => {
                const holding = this.holdings[ticker];
                const qtyStr = holding.quantity.toFixed(4).replace(/\.?0+$/, '');
                const option = document.createElement('option');
                option.value = ticker;
                option.textContent = `${ticker} × ${qtyStr} 股`;
                twGroup.appendChild(option);
            });
            select.appendChild(twGroup);
        }
    }
    
    updateTradeDateDisplay() {
        const display = document.getElementById('trade-date');
        if (this.selectedDate) {
            display.innerHTML = `<span class="trade-date-value">🔒 ${this.selectedDate}</span>`;
        } else {
            display.innerHTML = `<span class="trade-date-value">請點擊 K 線鎖定日期</span>`;
        }
    }
    
    async submitTrade() {
        // 檢查日期
        if (!this.selectedDate) {
            alert('請先點擊 K 線圖選擇交易日期！');
            return;
        }
        
        const ticker = document.getElementById('trade-stock').value;
        const action = document.getElementById('trade-action').value;
        
        if (!ticker) {
            alert('請選擇股票！');
            return;
        }
        
        // 取得股票價格
        try {
            const response = await fetch(`/api/stock-price/${ticker}?date=${this.selectedDate}`);
            const priceData = await response.json();
            
            if (priceData.error) {
                alert(`無法取得價格：${priceData.error}`);
                return;
            }
            
            const country = priceData.country;
            let quantity, price, actualAmountTWD;
            
            if (action === 'buy') {
                // === 買入邏輯 ===
                const inputAmountTWD = parseFloat(document.getElementById('trade-amount').value) || 0;
                
                if (inputAmountTWD <= 0) {
                    alert('請輸入有效的金額！');
                    return;
                }
                
                // 買入用最高價
                price = priceData.high;
                
                // 根據台幣金額計算可買股數
                if (country === 'US') {
                    quantity = inputAmountTWD / (price * this.exchangeRate);
                    actualAmountTWD = quantity * price * this.exchangeRate;
                } else {
                    quantity = inputAmountTWD / price;
                    actualAmountTWD = quantity * price;
                }
                
                // 保留小數點後4位
                quantity = Math.round(quantity * 10000) / 10000;
                
                if (quantity <= 0) {
                    alert('金額太小，無法購買任何股數！');
                    return;
                }
                
                // 檢查現金是否足夠
                if (actualAmountTWD > this.cash) {
                    alert(`現金不足！需要 $${actualAmountTWD.toLocaleString()} TWD，但只有 $${this.cash.toLocaleString()} TWD`);
                    return;
                }
                
                // 扣除現金
                this.cash -= actualAmountTWD;
                
                // 更新持倉
                if (!this.holdings[ticker]) {
                    this.holdings[ticker] = { quantity: 0, totalCost: 0, country };
                }
                this.holdings[ticker].quantity += quantity;
                this.holdings[ticker].totalCost += actualAmountTWD;
                
            } else {
                // === 賣出邏輯（全部出清） ===
                if (!this.holdings[ticker]) {
                    alert('您沒有持有這檔股票！');
                    return;
                }
                
                // 賣出用最低價，全部出清
                price = priceData.low;
                quantity = this.holdings[ticker].quantity;
                const holdingCountry = this.holdings[ticker].country;
                
                // 計算賣出金額
                if (holdingCountry === 'US') {
                    actualAmountTWD = quantity * price * this.exchangeRate;
                } else {
                    actualAmountTWD = quantity * price;
                }
                
                // 增加現金
                this.cash += actualAmountTWD;
                
                // 刪除持倉
                delete this.holdings[ticker];
                
                // 更新賣出股票清單
                this.updateStockSelectForSell();
            }
            
            // 記錄交易
            this.trades.push({
                id: ++this.tradeIdCounter,
                date: this.selectedDate,
                ticker,
                action,
                quantity,
                price,
                amountTWD: actualAmountTWD,
                country
            });
            
            // 更新顯示
            this.updateDisplay();
            
            // 買入時清空金額輸入
            if (action === 'buy') {
                document.getElementById('trade-amount').value = '100000';
            }
            
            console.log(`✅ ${action === 'buy' ? '買入' : '賣出'} ${ticker} x${quantity.toFixed(4)} @ ${price} (${country}) = $${actualAmountTWD.toFixed(0)} TWD`);
            
        } catch (error) {
            console.error('交易失敗:', error);
            alert('交易失敗，請重試');
        }
    }
    
    async cancelTrade(tradeId) {
        const tradeIndex = this.trades.findIndex(t => t.id === tradeId);
        if (tradeIndex === -1) return;
        
        const trade = this.trades[tradeIndex];
        
        // 反向操作
        if (trade.action === 'buy') {
            // 取消買入 = 退回現金，減少持倉
            this.cash += trade.amountTWD;
            if (this.holdings[trade.ticker]) {
                this.holdings[trade.ticker].quantity -= trade.quantity;
                this.holdings[trade.ticker].totalCost -= trade.amountTWD;
                if (this.holdings[trade.ticker].quantity <= 0) {
                    delete this.holdings[trade.ticker];
                }
            }
        } else {
            // 取消賣出 = 扣除現金，增加持倉
            this.cash -= trade.amountTWD;
            if (!this.holdings[trade.ticker]) {
                this.holdings[trade.ticker] = { quantity: 0, totalCost: 0, country: trade.country };
            }
            this.holdings[trade.ticker].quantity += trade.quantity;
            this.holdings[trade.ticker].totalCost += trade.amountTWD;
        }
        
        // 移除交易紀錄
        this.trades.splice(tradeIndex, 1);
        
        // 更新顯示
        this.updateDisplay();
    }
    
    /**
     * 計算到指定日期為止的持倉狀態
     * @param {string} asOfDate - 截止日期
     * @returns {Object} - 該日期的持倉狀態 {ticker: {quantity, totalCost, country}}
     */
    getHoldingsAsOfDate(asOfDate) {
        const holdings = {};
        
        if (!asOfDate) return holdings;
        
        // 按時間順序遍歷交易，只計算到 asOfDate 為止的交易
        for (const trade of this.trades) {
            // 只計算交易日期 <= asOfDate 的交易
            if (trade.date > asOfDate) continue;
            
            if (trade.action === 'buy') {
                if (!holdings[trade.ticker]) {
                    holdings[trade.ticker] = { quantity: 0, totalCost: 0, country: trade.country };
                }
                holdings[trade.ticker].quantity += trade.quantity;
                holdings[trade.ticker].totalCost += trade.amountTWD;
            } else {
                // 賣出
                if (holdings[trade.ticker]) {
                    const avgCost = holdings[trade.ticker].totalCost / holdings[trade.ticker].quantity;
                    holdings[trade.ticker].quantity -= trade.quantity;
                    holdings[trade.ticker].totalCost -= avgCost * trade.quantity;
                    
                    if (holdings[trade.ticker].quantity <= 0.0001) {
                        delete holdings[trade.ticker];
                    }
                }
            }
        }
        
        return holdings;
    }
    
    /**
     * 計算到指定日期為止的現金餘額
     * @param {string} asOfDate - 截止日期
     * @returns {number} - 該日期的現金餘額
     */
    getCashAsOfDate(asOfDate) {
        let cash = this.initialCapital;
        
        if (!asOfDate) return cash;
        
        for (const trade of this.trades) {
            if (trade.date > asOfDate) continue;
            
            if (trade.action === 'buy') {
                cash -= trade.amountTWD;
            } else {
                cash += trade.amountTWD;
            }
        }
        
        return cash;
    }
    
    /**
     * 計算到指定日期為止的已實現損益
     * @param {string} asOfDate - 截止日期
     * @returns {number} - 已實現損益
     */
    getRealizedPnLAsOfDate(asOfDate) {
        let realizedPnL = 0;
        const costBasis = {};
        
        if (!asOfDate) return realizedPnL;
        
        for (const trade of this.trades) {
            if (trade.date > asOfDate) continue;
            
            if (trade.action === 'buy') {
                if (!costBasis[trade.ticker]) {
                    costBasis[trade.ticker] = { totalQty: 0, totalCost: 0 };
                }
                costBasis[trade.ticker].totalQty += trade.quantity;
                costBasis[trade.ticker].totalCost += trade.amountTWD;
            } else {
                if (costBasis[trade.ticker] && costBasis[trade.ticker].totalQty > 0) {
                    const avgCost = costBasis[trade.ticker].totalCost / costBasis[trade.ticker].totalQty;
                    const costOfSold = avgCost * trade.quantity;
                    const proceeds = trade.amountTWD;
                    realizedPnL += proceeds - costOfSold;
                    
                    costBasis[trade.ticker].totalQty -= trade.quantity;
                    costBasis[trade.ticker].totalCost -= costOfSold;
                }
            }
        }
        
        return realizedPnL;
    }
    
    async calculateHoldingsValueWithPnL() {
        // 使用 displayDate（滑鼠滑動的日期）來計算市值
        const dateForValue = this.displayDate || this.selectedDate;
        
        const result = {
            totalValue: 0,
            totalCost: 0,
            unrealizedPnL: 0,
            holdings: []  // 個別持股損益
        };
        
        if (!dateForValue) {
            return result;
        }
        
        // 取得截至該日期的持倉狀態（關鍵修正！）
        const holdingsAsOfDate = this.getHoldingsAsOfDate(dateForValue);
        
        if (Object.keys(holdingsAsOfDate).length === 0) {
            return result;
        }
        
        for (const [ticker, holding] of Object.entries(holdingsAsOfDate)) {
            try {
                const response = await fetch(`/api/stock-price/${ticker}?date=${dateForValue}`);
                const priceData = await response.json();
                
                if (!priceData.error && priceData.close) {
                    // 使用收盤價計算市值
                    const price = priceData.close;
                    const valueTWD = holding.country === 'US'
                        ? price * holding.quantity * this.exchangeRate
                        : price * holding.quantity;
                    
                    const cost = holding.totalCost;
                    const pnl = valueTWD - cost;
                    const pnlPercent = cost > 0 ? (pnl / cost * 100) : 0;
                    
                    result.totalValue += valueTWD;
                    result.totalCost += cost;
                    result.unrealizedPnL += pnl;
                    
                    result.holdings.push({
                        ticker,
                        quantity: holding.quantity,
                        country: holding.country,
                        cost,
                        value: valueTWD,
                        pnl,
                        pnlPercent
                    });
                }
            } catch (error) {
                console.error(`計算 ${ticker} 市值失敗:`, error);
            }
        }
        
        // 按損益排序（賺最多的在前）
        result.holdings.sort((a, b) => b.pnl - a.pnl);
        
        return result;
    }
    
    calculateRealizedPnL() {
        // 這個方法計算所有交易的已實現損益（不限日期）
        // 用於交易模擬器的「當前狀態」顯示
        let realizedPnL = 0;
        
        // 追蹤每檔股票的買入成本
        const costBasis = {};
        
        for (const trade of this.trades) {
            if (trade.action === 'buy') {
                // 記錄買入成本
                if (!costBasis[trade.ticker]) {
                    costBasis[trade.ticker] = { totalQty: 0, totalCost: 0 };
                }
                costBasis[trade.ticker].totalQty += trade.quantity;
                costBasis[trade.ticker].totalCost += trade.amountTWD;
            } else {
                // 賣出：計算已實現損益
                if (costBasis[trade.ticker] && costBasis[trade.ticker].totalQty > 0) {
                    const avgCost = costBasis[trade.ticker].totalCost / costBasis[trade.ticker].totalQty;
                    const costOfSold = avgCost * trade.quantity;
                    const proceeds = trade.amountTWD;
                    realizedPnL += proceeds - costOfSold;
                    
                    // 更新成本基礎
                    costBasis[trade.ticker].totalQty -= trade.quantity;
                    costBasis[trade.ticker].totalCost -= costOfSold;
                }
            }
        }
        
        return realizedPnL;
    }
    
    async updateDisplay() {
        // 使用 displayDate 來計算「時間旅行」後的狀態
        const dateForValue = this.displayDate || this.selectedDate;
        
        // 計算截至該日期的現金餘額（時間旅行！）
        const cashAsOfDate = dateForValue ? this.getCashAsOfDate(dateForValue) : this.cash;
        document.getElementById('cash-balance').textContent = `$${cashAsOfDate.toLocaleString('zh-TW', { maximumFractionDigits: 0 })}`;
        
        // 計算持倉市值和損益（使用時間旅行後的持倉）
        const holdingsData = await this.calculateHoldingsValueWithPnL();
        const holdingsValue = holdingsData.totalValue;
        document.getElementById('holdings-value').textContent = `$${holdingsValue.toLocaleString('zh-TW', { maximumFractionDigits: 0 })}`;
        
        // 計算總資產（使用時間旅行後的現金）
        const totalAssets = cashAsOfDate + holdingsValue;
        document.getElementById('total-assets').textContent = `$${totalAssets.toLocaleString('zh-TW', { maximumFractionDigits: 0 })}`;
        
        // 計算總損益
        const profitLoss = totalAssets - this.initialCapital;
        const profitLossPercent = (profitLoss / this.initialCapital * 100).toFixed(2);
        const profitLossEl = document.getElementById('profit-loss');
        profitLossEl.textContent = `$${profitLoss.toLocaleString('zh-TW', { maximumFractionDigits: 0 })} (${profitLossPercent}%)`;
        
        // 設定顏色
        profitLossEl.classList.remove('positive', 'negative');
        if (profitLoss > 0) {
            profitLossEl.classList.add('positive');
        } else if (profitLoss < 0) {
            profitLossEl.classList.add('negative');
        }
        
        // 計算截至該日期的已實現損益（時間旅行！）
        const realizedPnL = dateForValue ? this.getRealizedPnLAsOfDate(dateForValue) : this.calculateRealizedPnL();
        const unrealizedPnL = holdingsData.unrealizedPnL;
        
        // 更新已實現損益
        const realizedEl = document.getElementById('realized-pnl');
        realizedEl.textContent = `$${realizedPnL.toLocaleString('zh-TW', { maximumFractionDigits: 0 })}`;
        realizedEl.classList.remove('positive', 'negative');
        if (realizedPnL > 0) realizedEl.classList.add('positive');
        else if (realizedPnL < 0) realizedEl.classList.add('negative');
        
        // 更新未實現損益
        const unrealizedEl = document.getElementById('unrealized-pnl');
        unrealizedEl.textContent = `$${unrealizedPnL.toLocaleString('zh-TW', { maximumFractionDigits: 0 })}`;
        unrealizedEl.classList.remove('positive', 'negative');
        if (unrealizedPnL > 0) unrealizedEl.classList.add('positive');
        else if (unrealizedPnL < 0) unrealizedEl.classList.add('negative');
        
        // 更新個別持股損益
        this.updateHoldingsPnL(holdingsData.holdings);
        
        // 更新交易紀錄
        this.updateTradeHistory();
    }
    
    updateHoldingsPnL(holdings) {
        const container = document.getElementById('holdings-pnl');
        
        if (holdings.length === 0) {
            container.innerHTML = '<div class="holdings-pnl-empty">尚無持倉</div>';
            return;
        }
        
        container.innerHTML = holdings.map(h => {
            const qtyStr = h.quantity.toFixed(4).replace(/\.?0+$/, '');
            const pnlStr = h.pnl.toLocaleString('zh-TW', { maximumFractionDigits: 0 });
            const pctStr = h.pnlPercent.toFixed(2);
            const pnlClass = h.pnl >= 0 ? 'positive' : 'negative';
            const sign = h.pnl >= 0 ? '+' : '';
            
            return `
                <div class="holding-pnl-item">
                    <div class="holding-info">
                        <span class="holding-ticker">${h.ticker}</span>
                        <span class="holding-qty">${qtyStr} 股</span>
                    </div>
                    <div class="holding-pnl-values">
                        <span class="holding-unrealized ${pnlClass}">${sign}$${pnlStr}</span>
                        <span class="holding-pct">${sign}${pctStr}%</span>
                    </div>
                </div>
            `;
        }).join('');
    }
    
    updateTradeHistory() {
        const container = document.getElementById('trade-history');
        
        if (this.trades.length === 0) {
            container.innerHTML = '<div class="trade-history-empty">尚無交易紀錄</div>';
            return;
        }
        
        // 倒序顯示（最新的在上面）
        const reversedTrades = [...this.trades].reverse();
        
        container.innerHTML = reversedTrades.map(trade => {
            // 格式化股數（小數點後4位，去除尾部0）
            const qtyStr = trade.quantity.toFixed(4).replace(/\.?0+$/, '');
            const amtStr = trade.amountTWD.toLocaleString('zh-TW', { maximumFractionDigits: 0 });
            
            return `
                <div class="trade-record ${trade.action}">
                    <div class="trade-record-info">
                        <div class="trade-record-main">
                            ${trade.action === 'buy' ? '🟢' : '🔴'} 
                            ${trade.ticker} × ${qtyStr}
                        </div>
                        <div class="trade-record-detail">
                            ${trade.date} | $${amtStr} TWD
                        </div>
                    </div>
                    <button class="trade-btn danger" onclick="window.tradeSimulator.cancelTrade(${trade.id})">取消</button>
                </div>
            `;
        }).join('');
    }
    
    resetCapital() {
        const newCapital = parseFloat(document.getElementById('initial-capital').value) || 1000000;
        
        if (this.trades.length > 0) {
            if (!confirm('重設本金將清除所有交易紀錄，確定要繼續嗎？')) {
                return;
            }
        }
        
        this.initialCapital = newCapital;
        this.cash = newCapital;
        this.holdings = {};
        this.trades = [];
        
        this.updateDisplay();
    }
    
    setExchangeRate(rate) {
        this.exchangeRate = rate;
        this.updateDisplay();
    }
}
