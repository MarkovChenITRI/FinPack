/**
 * SimulatorPanel - 模擬交易 UI 面板
 * 
 * 負責：
 *   - 股票搜尋與選擇
 *   - 買賣操作介面
 *   - 持倉與績效顯示
 */

import { SimulatorSession } from './Session.js';

export class SimulatorPanel {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        this.session = null;
        this.stockList = [];
        this.selectedStock = null;
        this.currentPrices = {};
    }
    
    /**
     * 初始化面板
     */
    async init() {
        if (!this.container) {
            console.error('Simulator panel container not found');
            return;
        }
        
        this.session = new SimulatorSession({ sessionId: 'main' });
        
        this._render();
        this._bindEvents();
        await this._loadStockList();
        this._updateDisplay();
    }
    
    /**
     * 渲染面板
     */
    _render() {
        this.container.innerHTML = `
            <div class="simulator-panel">
                <!-- 帳戶摘要 -->
                <div class="sim-summary">
                    <h3>帳戶概覽</h3>
                    <div class="summary-grid" id="sim-account-summary"></div>
                </div>
                
                <!-- 交易區 -->
                <div class="sim-trade">
                    <h3>交易</h3>
                    
                    <!-- 股票搜尋 -->
                    <div class="stock-search">
                        <input type="text" id="sim-stock-search" placeholder="搜尋股票代碼...">
                        <div id="sim-search-results" class="search-results hidden"></div>
                    </div>
                    
                    <!-- 選中股票資訊 -->
                    <div id="sim-selected-stock" class="selected-stock hidden">
                        <div class="stock-info">
                            <span id="sim-stock-ticker" class="ticker"></span>
                            <span id="sim-stock-price" class="price"></span>
                        </div>
                        
                        <!-- 買入表單 -->
                        <div class="trade-form">
                            <div class="form-row">
                                <label>動作</label>
                                <select id="sim-trade-action">
                                    <option value="buy">買入</option>
                                    <option value="sell">賣出</option>
                                </select>
                            </div>
                            <div class="form-row">
                                <label>股數</label>
                                <input type="number" id="sim-shares" value="100" min="1">
                            </div>
                            <div class="form-row">
                                <label>價格</label>
                                <input type="number" id="sim-price" step="0.01">
                            </div>
                            <div class="form-row estimate-row">
                                <span id="sim-estimate"></span>
                            </div>
                            <button id="sim-execute-trade" class="btn-primary">執行交易</button>
                        </div>
                    </div>
                </div>
                
                <!-- 持倉列表 -->
                <div class="sim-positions">
                    <h3>持倉 <button id="sim-refresh-prices" class="btn-small">更新價格</button></h3>
                    <div id="sim-positions-table"></div>
                </div>
                
                <!-- 交易歷史 -->
                <div class="sim-history">
                    <h3>交易歷史</h3>
                    <div id="sim-trade-history"></div>
                </div>
                
                <!-- 控制 -->
                <div class="sim-controls">
                    <button id="sim-export" class="btn-secondary">匯出</button>
                    <button id="sim-reset" class="btn-danger">重置帳戶</button>
                </div>
            </div>
        `;
    }
    
    /**
     * 綁定事件
     */
    _bindEvents() {
        // 股票搜尋
        const searchInput = document.getElementById('sim-stock-search');
        if (searchInput) {
            searchInput.addEventListener('input', (e) => this._handleSearch(e.target.value));
            searchInput.addEventListener('focus', () => this._showSearchResults());
        }
        
        // 點擊其他地方關閉搜尋結果
        document.addEventListener('click', (e) => {
            if (!e.target.closest('.stock-search')) {
                this._hideSearchResults();
            }
        });
        
        // 交易動作切換
        const actionSelect = document.getElementById('sim-trade-action');
        if (actionSelect) {
            actionSelect.addEventListener('change', () => this._updateEstimate());
        }
        
        // 股數/價格變更
        const sharesInput = document.getElementById('sim-shares');
        const priceInput = document.getElementById('sim-price');
        if (sharesInput) sharesInput.addEventListener('input', () => this._updateEstimate());
        if (priceInput) priceInput.addEventListener('input', () => this._updateEstimate());
        
        // 執行交易
        const executeBtn = document.getElementById('sim-execute-trade');
        if (executeBtn) {
            executeBtn.addEventListener('click', () => this._executeTrade());
        }
        
        // 更新價格
        const refreshBtn = document.getElementById('sim-refresh-prices');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => this._refreshPrices());
        }
        
        // 匯出
        const exportBtn = document.getElementById('sim-export');
        if (exportBtn) {
            exportBtn.addEventListener('click', () => this._exportData());
        }
        
        // 重置
        const resetBtn = document.getElementById('sim-reset');
        if (resetBtn) {
            resetBtn.addEventListener('click', () => this._resetAccount());
        }
    }
    
    /**
     * 載入股票列表
     */
    async _loadStockList() {
        try {
            const response = await fetch('/api/stocks');
            const data = await response.json();
            this.stockList = data.stocks || [];
        } catch (error) {
            console.error('載入股票列表失敗:', error);
        }
    }
    
    /**
     * 處理搜尋
     */
    _handleSearch(query) {
        if (!query || query.length < 1) {
            this._hideSearchResults();
            return;
        }
        
        const upperQuery = query.toUpperCase();
        const matches = this.stockList
            .filter(s => s.ticker.toUpperCase().includes(upperQuery))
            .slice(0, 10);
        
        this._displaySearchResults(matches);
    }
    
    /**
     * 顯示搜尋結果
     */
    _displaySearchResults(stocks) {
        const container = document.getElementById('sim-search-results');
        if (!container) return;
        
        if (stocks.length === 0) {
            container.innerHTML = '<div class="no-results">無符合結果</div>';
        } else {
            container.innerHTML = stocks.map(s => `
                <div class="search-result-item" data-ticker="${s.ticker}" data-country="${s.country}">
                    <span class="ticker">${s.ticker}</span>
                    <span class="country">${s.country}</span>
                    <span class="industry">${s.industry || ''}</span>
                </div>
            `).join('');
            
            // 綁定點擊事件
            container.querySelectorAll('.search-result-item').forEach(item => {
                item.addEventListener('click', () => {
                    this._selectStock(item.dataset.ticker, item.dataset.country);
                });
            });
        }
        
        this._showSearchResults();
    }
    
    _showSearchResults() {
        const container = document.getElementById('sim-search-results');
        if (container) container.classList.remove('hidden');
    }
    
    _hideSearchResults() {
        const container = document.getElementById('sim-search-results');
        if (container) container.classList.add('hidden');
    }
    
    /**
     * 選擇股票
     */
    async _selectStock(ticker, country) {
        this._hideSearchResults();
        
        // 清空搜尋框
        const searchInput = document.getElementById('sim-stock-search');
        if (searchInput) searchInput.value = '';
        
        this.selectedStock = { ticker, country };
        
        // 取得當前價格
        try {
            const response = await fetch(`/api/stock-price/${ticker}?date=${new Date().toISOString().split('T')[0]}`);
            const data = await response.json();
            
            if (data.price) {
                this.currentPrices[ticker] = data.price;
            }
        } catch (e) {
            console.warn('無法取得價格:', e);
        }
        
        // 顯示選中股票
        const selectedDiv = document.getElementById('sim-selected-stock');
        const tickerSpan = document.getElementById('sim-stock-ticker');
        const priceSpan = document.getElementById('sim-stock-price');
        const priceInput = document.getElementById('sim-price');
        
        if (selectedDiv) selectedDiv.classList.remove('hidden');
        if (tickerSpan) tickerSpan.textContent = ticker;
        if (priceSpan) priceSpan.textContent = `$${this.currentPrices[ticker]?.toFixed(2) || '--'}`;
        if (priceInput) priceInput.value = this.currentPrices[ticker]?.toFixed(2) || '';
        
        // 如果已持有，預設為賣出
        const position = this.session.getPositions().find(p => p.ticker === ticker);
        const actionSelect = document.getElementById('sim-trade-action');
        if (actionSelect && position) {
            actionSelect.value = 'sell';
        }
        
        this._updateEstimate();
    }
    
    /**
     * 更新估算
     */
    _updateEstimate() {
        const estimateSpan = document.getElementById('sim-estimate');
        if (!estimateSpan || !this.selectedStock) return;
        
        const action = document.getElementById('sim-trade-action')?.value;
        const shares = parseInt(document.getElementById('sim-shares')?.value) || 0;
        const price = parseFloat(document.getElementById('sim-price')?.value) || 0;
        
        if (!shares || !price) {
            estimateSpan.textContent = '';
            return;
        }
        
        const { ticker, country } = this.selectedStock;
        
        if (action === 'buy') {
            const estimate = this.session.estimateBuy(ticker, shares * price, price, country);
            estimateSpan.textContent = `預估：${estimate.shares} 股，總計 $${estimate.total.toLocaleString()}`;
        } else {
            const estimate = this.session.estimateSell(ticker, price);
            if (estimate) {
                estimateSpan.textContent = `持有 ${estimate.shares} 股，估損益 $${estimate.profit.toFixed(0)}`;
            } else {
                estimateSpan.textContent = '未持有此股票';
            }
        }
    }
    
    /**
     * 執行交易
     */
    _executeTrade() {
        if (!this.selectedStock) {
            alert('請先選擇股票');
            return;
        }
        
        const action = document.getElementById('sim-trade-action')?.value;
        const shares = parseInt(document.getElementById('sim-shares')?.value) || 0;
        const price = parseFloat(document.getElementById('sim-price')?.value) || 0;
        
        if (!shares || !price) {
            alert('請輸入股數和價格');
            return;
        }
        
        const { ticker, country } = this.selectedStock;
        let result;
        
        if (action === 'buy') {
            result = this.session.buy(ticker, shares, price, country);
        } else {
            result = this.session.sell(ticker, shares, price);
        }
        
        if (result.success) {
            alert(`${action === 'buy' ? '買入' : '賣出'}成功！`);
            this._updateDisplay();
            
            // 清空選擇
            const selectedDiv = document.getElementById('sim-selected-stock');
            if (selectedDiv) selectedDiv.classList.add('hidden');
            this.selectedStock = null;
        } else {
            alert(`交易失敗: ${result.reason}`);
        }
    }
    
    /**
     * 更新所有顯示
     */
    _updateDisplay() {
        this._updateAccountSummary();
        this._updatePositions();
        this._updateTradeHistory();
    }
    
    /**
     * 更新帳戶摘要
     */
    _updateAccountSummary() {
        const container = document.getElementById('sim-account-summary');
        if (!container) return;
        
        const summary = this.session.getSummary(this.currentPrices);
        
        container.innerHTML = `
            <div class="summary-item">
                <label>總資產</label>
                <value>$${summary.totalValue.toLocaleString()}</value>
            </div>
            <div class="summary-item">
                <label>現金</label>
                <value>$${summary.cash.toLocaleString()}</value>
            </div>
            <div class="summary-item">
                <label>持倉價值</label>
                <value>$${summary.positionValue.toLocaleString()}</value>
            </div>
            <div class="summary-item">
                <label>報酬率</label>
                <value class="${summary.returnPct >= 0 ? 'positive' : 'negative'}">
                    ${summary.returnPct.toFixed(2)}%
                </value>
            </div>
        `;
    }
    
    /**
     * 更新持倉列表
     */
    _updatePositions() {
        const container = document.getElementById('sim-positions-table');
        if (!container) return;
        
        const positions = this.session.getPositionsWithPL(this.currentPrices);
        
        if (positions.length === 0) {
            container.innerHTML = '<p class="no-data">無持倉</p>';
            return;
        }
        
        let html = '<table class="positions-table"><thead><tr>' +
            '<th>股票</th><th>股數</th><th>成本</th><th>現價</th><th>市值</th><th>損益</th><th>操作</th>' +
            '</tr></thead><tbody>';
        
        for (const pos of positions) {
            const plClass = pos.unrealizedPL > 0 ? 'positive' : (pos.unrealizedPL < 0 ? 'negative' : '');
            html += `<tr>
                <td>${pos.ticker}</td>
                <td>${pos.shares}</td>
                <td>$${pos.avgCost.toFixed(2)}</td>
                <td>${pos.currentPrice ? '$' + pos.currentPrice.toFixed(2) : '--'}</td>
                <td>${pos.marketValue ? '$' + pos.marketValue.toLocaleString() : '--'}</td>
                <td class="${plClass}">${pos.unrealizedPL ? '$' + pos.unrealizedPL.toFixed(0) : '--'}</td>
                <td>
                    <button class="btn-small sell-btn" data-ticker="${pos.ticker}">賣出</button>
                </td>
            </tr>`;
        }
        
        html += '</tbody></table>';
        container.innerHTML = html;
        
        // 綁定賣出按鈕
        container.querySelectorAll('.sell-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const ticker = btn.dataset.ticker;
                const pos = positions.find(p => p.ticker === ticker);
                if (pos) {
                    this._selectStock(ticker, pos.country);
                    document.getElementById('sim-trade-action').value = 'sell';
                    document.getElementById('sim-shares').value = pos.shares;
                }
            });
        });
    }
    
    /**
     * 更新交易歷史
     */
    _updateTradeHistory() {
        const container = document.getElementById('sim-trade-history');
        if (!container) return;
        
        const trades = this.session.getTradeHistory();
        
        if (trades.length === 0) {
            container.innerHTML = '<p class="no-data">無交易紀錄</p>';
            return;
        }
        
        let html = '<table class="history-table"><thead><tr>' +
            '<th>日期</th><th>動作</th><th>股票</th><th>股數</th><th>價格</th><th>損益</th>' +
            '</tr></thead><tbody>';
        
        for (const trade of trades.slice().reverse().slice(0, 20)) {
            const plClass = trade.profit > 0 ? 'positive' : (trade.profit < 0 ? 'negative' : '');
            html += `<tr>
                <td>${trade.date}</td>
                <td class="${trade.action === 'BUY' ? 'buy' : 'sell'}">${trade.action}</td>
                <td>${trade.ticker}</td>
                <td>${trade.shares}</td>
                <td>$${trade.price.toFixed(2)}</td>
                <td class="${plClass}">${trade.profit ? '$' + trade.profit.toFixed(0) : '-'}</td>
            </tr>`;
        }
        
        html += '</tbody></table>';
        container.innerHTML = html;
    }
    
    /**
     * 更新價格
     */
    async _refreshPrices() {
        const positions = this.session.getPositions();
        
        for (const pos of positions) {
            try {
                const response = await fetch(`/api/stock-price/${pos.ticker}?date=${new Date().toISOString().split('T')[0]}`);
                const data = await response.json();
                if (data.price) {
                    this.currentPrices[pos.ticker] = data.price;
                }
            } catch (e) {
                console.warn(`無法取得 ${pos.ticker} 價格`);
            }
        }
        
        this._updateDisplay();
    }
    
    /**
     * 匯出數據
     */
    _exportData() {
        const data = this.session.export();
        const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        
        const a = document.createElement('a');
        a.href = url;
        a.download = `finpack_simulator_${new Date().toISOString().split('T')[0]}.json`;
        a.click();
        
        URL.revokeObjectURL(url);
    }
    
    /**
     * 重置帳戶
     */
    _resetAccount() {
        if (confirm('確定要重置帳戶嗎？所有持倉和交易紀錄將被清除。')) {
            this.session.reset();
            this._updateDisplay();
        }
    }
}
