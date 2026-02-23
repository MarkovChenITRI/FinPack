/**
 * BacktestPanel - 回測 UI 面板
 * 
 * 負責：
 *   - 表單綁定與驗證
 *   - 與 BacktestEngine 互動
 *   - 結果顯示
 */

import { BacktestEngine } from './Engine.js';
import { getBuyConditionsByCategory } from './buying/index.js';
import { getAllSellConditions } from './selling/index.js';
import { getAllRebalanceStrategies } from './rebalance/index.js';

export class BacktestPanel {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        this.engine = null;
        this.data = null;  // 回測數據
        this.chart = null; // 權益曲線圖表
    }
    
    /**
     * 初始化面板
     */
    async init() {
        if (!this.container) {
            console.error('Backtest panel container not found');
            return;
        }
        
        this._render();
        this._bindEvents();
        await this._loadData();
    }
    
    /**
     * 渲染面板 HTML
     */
    _render() {
        this.container.innerHTML = `
            <div class="backtest-panel">
                <!-- 設定區 -->
                <div class="bt-settings">
                    <h3>回測設定</h3>
                    
                    <!-- 基本設定 -->
                    <div class="bt-section">
                        <h4>基本參數</h4>
                        <div class="bt-row">
                            <label>初始資金</label>
                            <input type="number" id="bt-capital" value="1000000" step="100000">
                        </div>
                        <div class="bt-row">
                            <label>每檔投入</label>
                            <input type="number" id="bt-amount" value="100000" step="10000">
                        </div>
                        <div class="bt-row">
                            <label>最大持倉</label>
                            <input type="number" id="bt-max-positions" value="10" min="1" max="30">
                        </div>
                        <div class="bt-row">
                            <label>市場</label>
                            <select id="bt-market">
                                <option value="global">全球</option>
                                <option value="us">美股</option>
                                <option value="tw">台股</option>
                            </select>
                        </div>
                    </div>
                    
                    <!-- 時間範圍 -->
                    <div class="bt-section">
                        <h4>時間範圍</h4>
                        <div class="bt-row">
                            <label>開始日期</label>
                            <input type="date" id="bt-start-date">
                        </div>
                        <div class="bt-row">
                            <label>結束日期</label>
                            <input type="date" id="bt-end-date">
                        </div>
                    </div>
                    
                    <!-- 買入條件 -->
                    <div class="bt-section">
                        <h4>買入條件</h4>
                        <div id="bt-buy-conditions"></div>
                    </div>
                    
                    <!-- 賣出條件 -->
                    <div class="bt-section">
                        <h4>賣出條件</h4>
                        <div id="bt-sell-conditions"></div>
                    </div>
                    
                    <!-- 再平衡策略 -->
                    <div class="bt-section">
                        <h4>再平衡策略</h4>
                        <div id="bt-rebalance-strategy"></div>
                    </div>
                    
                    <!-- 控制按鈕 -->
                    <div class="bt-controls">
                        <button id="bt-run" class="btn-primary">開始回測</button>
                        <button id="bt-reset" class="btn-secondary">重置</button>
                    </div>
                </div>
                
                <!-- 結果區 -->
                <div class="bt-results">
                    <h3>回測結果</h3>
                    
                    <!-- 進度 -->
                    <div id="bt-progress" class="bt-progress hidden">
                        <div class="progress-bar">
                            <div class="progress-fill" id="bt-progress-fill"></div>
                        </div>
                        <span id="bt-progress-text">0%</span>
                    </div>
                    
                    <!-- 績效摘要 -->
                    <div id="bt-summary" class="bt-summary"></div>
                    
                    <!-- 權益曲線 -->
                    <div id="bt-chart-container" class="bt-chart"></div>
                    
                    <!-- 交易紀錄 -->
                    <div id="bt-trades" class="bt-trades"></div>
                </div>
            </div>
        `;
        
        this._renderConditions();
    }
    
    /**
     * 渲染條件選項
     */
    _renderConditions() {
        // 買入條件
        const buyContainer = document.getElementById('bt-buy-conditions');
        const buyConditions = getBuyConditionsByCategory();
        
        let buyHtml = '';
        for (const [category, conditions] of Object.entries(buyConditions)) {
            buyHtml += `<div class="condition-category">
                <h5>類別 ${category}</h5>`;
            
            for (const cond of conditions) {
                buyHtml += `
                    <label class="condition-item">
                        <input type="checkbox" name="buy-${cond.id}" data-id="${cond.id}">
                        <span>${cond.name}</span>
                        <small>${cond.description}</small>
                    </label>`;
            }
            buyHtml += '</div>';
        }
        buyContainer.innerHTML = buyHtml;
        
        // 賣出條件
        const sellContainer = document.getElementById('bt-sell-conditions');
        const sellConditions = getAllSellConditions();
        
        let sellHtml = '';
        for (const cond of sellConditions) {
            sellHtml += `
                <label class="condition-item">
                    <input type="checkbox" name="sell-${cond.id}" data-id="${cond.id}">
                    <span>${cond.name}</span>
                    <small>${cond.description}</small>
                </label>`;
        }
        sellContainer.innerHTML = sellHtml;
        
        // 再平衡策略
        const rebalanceContainer = document.getElementById('bt-rebalance-strategy');
        const rebalanceStrategies = getAllRebalanceStrategies();
        
        let rebalanceHtml = '';
        for (const strategy of rebalanceStrategies) {
            rebalanceHtml += `
                <label class="strategy-item">
                    <input type="radio" name="rebalance" value="${strategy.id}" 
                           ${strategy.id === 'batch' ? 'checked' : ''}>
                    <span>${strategy.name}</span>
                    <small>${strategy.description}</small>
                </label>`;
        }
        rebalanceContainer.innerHTML = rebalanceHtml;
    }
    
    /**
     * 綁定事件
     */
    _bindEvents() {
        const runBtn = document.getElementById('bt-run');
        const resetBtn = document.getElementById('bt-reset');
        
        if (runBtn) {
            runBtn.addEventListener('click', () => this.runBacktest());
        }
        
        if (resetBtn) {
            resetBtn.addEventListener('click', () => this.reset());
        }
    }
    
    /**
     * 載入回測數據
     */
    async _loadData() {
        try {
            // 從 API 載入數據
            const [industryData, pricesData] = await Promise.all([
                fetch('/api/industry/data?period=2y').then(r => r.json()),
                fetch('/api/backtest/prices?period=2y').then(r => r.json())
            ]);
            
            this.data = {
                dates: industryData.dates,
                stockInfo: industryData.stockInfo,
                sharpeRank: industryData.sharpeRank,
                growthRank: industryData.growthRank,
                prices: pricesData.prices,
                sharpeValues: this._matrixToDateMap(industryData.sharpe, industryData.dates, industryData.tickers),
                growthValues: this._matrixToDateMap(industryData.growth, industryData.dates, industryData.tickers)
            };
            
            // 設定預設日期
            this._setDefaultDates();
            
            console.log('✅ 回測數據載入完成');
        } catch (error) {
            console.error('❌ 載入回測數據失敗:', error);
        }
    }
    
    /**
     * 將矩陣格式轉換為 {date: {ticker: value}}
     */
    _matrixToDateMap(matrix, dates, tickers) {
        const result = {};
        if (!matrix || !dates || !tickers) return result;
        
        for (let i = 0; i < dates.length; i++) {
            result[dates[i]] = {};
            for (let j = 0; j < tickers.length; j++) {
                if (matrix[i]?.[j] !== undefined) {
                    result[dates[i]][tickers[j]] = matrix[i][j];
                }
            }
        }
        return result;
    }
    
    /**
     * 設定預設日期
     */
    _setDefaultDates() {
        const endDateInput = document.getElementById('bt-end-date');
        const startDateInput = document.getElementById('bt-start-date');
        
        const today = new Date();
        const endDate = today.toISOString().split('T')[0];
        
        const startDate = new Date(today);
        startDate.setMonth(startDate.getMonth() - 6);
        
        if (endDateInput) endDateInput.value = endDate;
        if (startDateInput) startDateInput.value = startDate.toISOString().split('T')[0];
    }
    
    /**
     * 收集表單設定
     */
    _collectSettings() {
        const settings = {
            initialCapital: parseInt(document.getElementById('bt-capital')?.value) || 1000000,
            amountPerStock: parseInt(document.getElementById('bt-amount')?.value) || 100000,
            maxPositions: parseInt(document.getElementById('bt-max-positions')?.value) || 10,
            market: document.getElementById('bt-market')?.value || 'global',
            startDate: document.getElementById('bt-start-date')?.value,
            endDate: document.getElementById('bt-end-date')?.value,
            buyConditions: {},
            sellConditions: {},
            rebalanceStrategy: document.querySelector('input[name="rebalance"]:checked')?.value || 'batch'
        };
        
        // 收集買入條件
        document.querySelectorAll('#bt-buy-conditions input[type="checkbox"]:checked').forEach(input => {
            settings.buyConditions[input.dataset.id] = { enabled: true };
        });
        
        // 收集賣出條件
        document.querySelectorAll('#bt-sell-conditions input[type="checkbox"]:checked').forEach(input => {
            settings.sellConditions[input.dataset.id] = { enabled: true };
        });
        
        return settings;
    }
    
    /**
     * 執行回測
     */
    async runBacktest() {
        if (!this.data) {
            alert('數據尚未載入完成');
            return;
        }
        
        const settings = this._collectSettings();
        
        // 驗證
        if (Object.keys(settings.buyConditions).length === 0) {
            alert('請至少選擇一個買入條件');
            return;
        }
        
        // 建立引擎
        this.engine = new BacktestEngine({
            initialCapital: settings.initialCapital,
            amountPerStock: settings.amountPerStock,
            maxPositions: settings.maxPositions,
            market: settings.market
        });
        
        this.engine.setBuyConditions(settings.buyConditions);
        this.engine.setSellConditions(settings.sellConditions);
        this.engine.setRebalanceStrategy(settings.rebalanceStrategy);
        
        // 顯示進度
        this._showProgress(true);
        
        // 執行回測
        const result = await this.engine.run(this.data, {
            startDate: settings.startDate,
            endDate: settings.endDate,
            onProgress: (progress) => this._updateProgress(progress)
        });
        
        // 隱藏進度
        this._showProgress(false);
        
        // 顯示結果
        if (result.success) {
            this._displayResults(result);
        } else {
            alert('回測失敗: ' + result.error);
        }
    }
    
    /**
     * 顯示/隱藏進度條
     */
    _showProgress(show) {
        const progress = document.getElementById('bt-progress');
        if (progress) {
            progress.classList.toggle('hidden', !show);
        }
    }
    
    /**
     * 更新進度
     */
    _updateProgress(progress) {
        const fill = document.getElementById('bt-progress-fill');
        const text = document.getElementById('bt-progress-text');
        
        const pct = Math.round((progress.current / progress.total) * 100);
        
        if (fill) fill.style.width = `${pct}%`;
        if (text) text.textContent = `${pct}% - ${progress.date}`;
    }
    
    /**
     * 顯示回測結果
     */
    _displayResults(result) {
        this._displaySummary(result.metrics);
        this._displayEquityCurve(result.equityCurve);
        this._displayTrades(result.trades);
    }
    
    /**
     * 顯示績效摘要
     */
    _displaySummary(metrics) {
        const container = document.getElementById('bt-summary');
        if (!container) return;
        
        container.innerHTML = `
            <div class="metrics-grid">
                <div class="metric">
                    <label>總報酬</label>
                    <value class="${metrics.totalReturnPct >= 0 ? 'positive' : 'negative'}">
                        ${metrics.totalReturnPct.toFixed(2)}%
                    </value>
                </div>
                <div class="metric">
                    <label>年化報酬</label>
                    <value>${metrics.annualizedReturn.toFixed(2)}%</value>
                </div>
                <div class="metric">
                    <label>最大回撤</label>
                    <value class="negative">${metrics.maxDrawdown.value.toFixed(2)}%</value>
                </div>
                <div class="metric">
                    <label>Sharpe Ratio</label>
                    <value>${metrics.sharpeRatio.toFixed(2)}</value>
                </div>
                <div class="metric">
                    <label>勝率</label>
                    <value>${metrics.tradeStats.winRate.toFixed(1)}%</value>
                </div>
                <div class="metric">
                    <label>總交易</label>
                    <value>${metrics.tradeStats.totalTrades}</value>
                </div>
            </div>
        `;
    }
    
    /**
     * 顯示權益曲線
     */
    _displayEquityCurve(equityCurve) {
        const container = document.getElementById('bt-chart-container');
        if (!container || !equityCurve?.length) return;
        
        // 如果有 Chart.js，繪製圖表
        // 否則用簡單方式顯示
        if (typeof Chart !== 'undefined') {
            if (this.chart) this.chart.destroy();
            
            const canvas = document.createElement('canvas');
            container.innerHTML = '';
            container.appendChild(canvas);
            
            this.chart = new Chart(canvas, {
                type: 'line',
                data: {
                    labels: equityCurve.map(e => e.date),
                    datasets: [{
                        label: '投資組合價值',
                        data: equityCurve.map(e => e.value),
                        borderColor: '#4CAF50',
                        fill: false
                    }]
                },
                options: {
                    responsive: true,
                    plugins: {
                        legend: { display: false }
                    }
                }
            });
        } else {
            // 簡單顯示
            const startValue = equityCurve[0]?.value || 0;
            const endValue = equityCurve[equityCurve.length - 1]?.value || 0;
            container.innerHTML = `
                <div class="simple-chart">
                    <p>起始: ${startValue.toLocaleString()}</p>
                    <p>結束: ${endValue.toLocaleString()}</p>
                </div>
            `;
        }
    }
    
    /**
     * 顯示交易紀錄
     */
    _displayTrades(trades) {
        const container = document.getElementById('bt-trades');
        if (!container) return;
        
        if (!trades?.length) {
            container.innerHTML = '<p>無交易紀錄</p>';
            return;
        }
        
        let html = '<table class="trades-table"><thead><tr>' +
            '<th>日期</th><th>動作</th><th>股票</th><th>股數</th><th>價格</th><th>金額</th><th>損益</th>' +
            '</tr></thead><tbody>';
        
        for (const trade of trades.slice(-50)) {  // 最近 50 筆
            const profitClass = trade.profit > 0 ? 'positive' : (trade.profit < 0 ? 'negative' : '');
            html += `<tr>
                <td>${trade.date}</td>
                <td class="${trade.action === 'BUY' ? 'buy' : 'sell'}">${trade.action}</td>
                <td>${trade.ticker}</td>
                <td>${trade.shares}</td>
                <td>${trade.price?.toFixed(2)}</td>
                <td>${trade.amount?.toLocaleString()}</td>
                <td class="${profitClass}">${trade.profit ? trade.profit.toFixed(0) : '-'}</td>
            </tr>`;
        }
        
        html += '</tbody></table>';
        container.innerHTML = html;
    }
    
    /**
     * 重置面板
     */
    reset() {
        if (this.engine) {
            this.engine.reset();
        }
        
        document.getElementById('bt-summary').innerHTML = '';
        document.getElementById('bt-chart-container').innerHTML = '';
        document.getElementById('bt-trades').innerHTML = '';
        
        if (this.chart) {
            this.chart.destroy();
            this.chart = null;
        }
    }
}
