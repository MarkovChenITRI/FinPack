/**
 * app.js - 前端應用入口點
 * 
 * 職責：
 *   - 初始化所有模組
 *   - 綁定全域事件
 *   - 協調模組間通訊
 * 
 * 資料流：
 *   DOMContentLoaded → FinPackApp.init()
 *     → 載入 K 線數據 (MarketChart)
 *     → 載入 Sharpe/Slope 矩陣 (IndustryDataCache)
 *     → 初始化柱狀圖 (IndustryBarChart)
 *     → 初始化交易模擬器/回測引擎
 */

// API 層
import { fetchMarketData, fetchExchangeRate } from './api/market.js';

// 工具層
import { industryDataCache } from './utils/cache.js';

// 元件層
import { MarketChart } from './components/MarketChart.js';
import { IndustryBarChart } from './components/IndustryChart.js';
import { TradeSimulator } from './components/TradeSimulator.js';
import { BacktestEngine } from './components/BacktestEngine.js';

class FinPackApp {
    constructor() {
        this.charts = {};
        this.sharpeChart = null;
        this.slopeChart = null;
        this.currentMarket = 'global';
        this.currentPeriod = '1y';
        this.currentCategory = 'value';
        this.exchangeRate = 32.0;
        this.tradeSimulator = null;
        this.backtestEngine = null;
    }

    async init() {
        this.showLoading(true);

        try {
            // 獲取匯率
            await this.fetchExchangeRate();

            // 暫時讓所有圖表可見，以便正確初始化
            document.querySelectorAll('.chart').forEach(chart => {
                chart.classList.add('active');
            });

            // 初始化 K 線圖表
            this.charts.global = new MarketChart('chart-global', 'global', '國際加權指數');
            this.charts.nasdaq = new MarketChart('chart-nasdaq', 'nasdaq', '美股');
            this.charts.twii = new MarketChart('chart-twii', 'twii', '台灣加權指數');
            this.charts.gold = new MarketChart('chart-gold', 'gold', '黃金');
            this.charts.btc = new MarketChart('chart-btc', 'btc', '比特幣');
            this.charts.bonds = new MarketChart('chart-bonds', 'bonds', '美國公債');

            this.charts.global.init();
            this.charts.nasdaq.init();
            this.charts.twii.init();
            this.charts.gold.init();
            this.charts.btc.init();
            this.charts.bonds.init();

            // 初始化 Sharpe Top 圖表
            this.sharpeChart = new IndustryBarChart(
                'industry-bar-chart', 
                'industry-legend',
                'sharpe',
                'Sharpe'
            );
            this.sharpeChart.init();

            // 初始化 Slope Top 圖表
            this.slopeChart = new IndustryBarChart(
                'slope-bar-chart',
                'slope-legend',
                'slope',
                'Slope'
            );
            this.slopeChart.init();

            // 載入數據
            await this.loadMarketData();
            
            // 預載入產業分析資料
            await industryDataCache.load();
            
            // 初始顯示
            this.sharpeChart.loadData('global');
            this.slopeChart.loadData('global');

            // 恢復只顯示第一個圖表
            document.querySelectorAll('.chart').forEach(chart => {
                chart.classList.remove('active');
            });
            document.getElementById('chart-global').classList.add('active');

            // 初始化交易模擬器
            this.tradeSimulator = new TradeSimulator(this.exchangeRate);
            await this.tradeSimulator.init();
            window.tradeSimulator = this.tradeSimulator;
            
            // 初始化回測引擎
            this.backtestEngine = new BacktestEngine();
            this.backtestEngine.init();
            window.backtestEngine = this.backtestEngine;

            // 綁定事件
            this.bindEvents();

            // 更新最後更新時間
            this.updateLastUpdate();

        } catch (error) {
            console.error('初始化失敗:', error);
            alert('載入市場數據失敗，請重試');
        } finally {
            this.showLoading(false);
        }
    }

    async fetchExchangeRate() {
        try {
            const data = await fetchExchangeRate();
            this.exchangeRate = data.rate;
            document.getElementById('exchange-rate').textContent = `USD/TWD: ${this.exchangeRate}`;
        } catch (error) {
            console.error('獲取匯率失敗:', error);
        }
    }

    async loadMarketData() {
        try {
            const data = await fetchMarketData(this.currentPeriod);

            if (data.global?.length > 0) this.charts.global.setData(data.global);
            if (data.nasdaq?.length > 0) this.charts.nasdaq.setData(data.nasdaq);
            if (data.twii?.length > 0) this.charts.twii.setData(data.twii);
            if (data.gold?.length > 0) this.charts.gold.setData(data.gold);
            if (data.btc?.length > 0) this.charts.btc.setData(data.btc);
            if (data.bonds?.length > 0) this.charts.bonds.setData(data.bonds);

        } catch (error) {
            console.error('載入市場數據失敗:', error);
            throw error;
        }
    }

    bindEvents() {
        // 分類切換
        document.querySelectorAll('.nav-item').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const category = e.target.dataset.category;
                this.switchCategory(category);
            });
        });

        // 市場切換
        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const market = e.target.dataset.market;
                this.switchMarket(market);
            });
        });

        // 時間範圍切換
        document.querySelectorAll('.period-btn').forEach(btn => {
            btn.addEventListener('click', async (e) => {
                const period = e.target.dataset.period;
                await this.switchPeriod(period);
            });
        });
        
        // 回測條件 Tab 切換
        document.querySelectorAll('.bt-tab').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const tabId = e.target.dataset.tab;
                this.switchBacktestTab(tabId);
            });
        });

        // 監聽 K 線日期變更事件
        window.addEventListener('kline-date-change', (e) => {
            if (this.currentCategory === 'value' && e.detail.market === this.currentMarket) {
                const date = e.detail.date;
                this.updateIndustryCharts(this.currentMarket, date);
            }
        });
        
        // 監聯 K 線點擊事件
        window.addEventListener('kline-clicked', (e) => {
            console.log('K線被點擊:', e.detail);
        });
    }
    
    updateIndustryCharts(market, date) {
        if (!this.sharpeChart || !this.slopeChart) return;
        this.sharpeChart.loadData(market, date);
        this.slopeChart.loadData(market, date);
    }

    switchCategory(category) {
        this.currentCategory = category;

        document.querySelectorAll('.nav-item').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.category === category);
        });

        document.getElementById('tabs-value').classList.toggle('hidden', category !== 'value');
        document.getElementById('tabs-rotation').classList.toggle('hidden', category !== 'rotation');
        document.getElementById('value-layout').classList.toggle('hidden', category !== 'value');
        document.getElementById('rotation-charts').classList.toggle('hidden', category !== 'rotation');

        const defaultMarket = category === 'value' ? 'global' : 'gold';
        this.switchMarket(defaultMarket);

        const tabsContainer = document.getElementById(`tabs-${category}`);
        tabsContainer.querySelectorAll('.tab-btn').forEach((btn, index) => {
            btn.classList.toggle('active', index === 0);
        });

        if (category === 'value') {
            const selectedDate = this.getSelectedDate('global');
            this.sharpeChart.loadData('global', selectedDate);
            this.slopeChart.loadData('global', selectedDate);
        }
    }
    
    getSelectedDate(market) {
        if (this.charts[market] && this.charts[market].lockedDate) {
            return this.charts[market].lockedDate;
        }
        return null;
    }
    
    /**
     * 切換回測條件 Tab
     * @param {string} tabId - tab ID (buy/sell/rebalance)
     */
    switchBacktestTab(tabId) {
        // 切換 Tab 按鈕狀態
        document.querySelectorAll('.bt-tab').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.tab === tabId);
        });
        
        // 切換 Tab 內容顯示
        document.querySelectorAll('.bt-tab-pane').forEach(pane => {
            pane.classList.toggle('active', pane.id === `bt-tab-${tabId}`);
        });
    }

    switchMarket(market) {
        this.currentMarket = market;

        const activeTabsId = this.currentCategory === 'rotation' ? 'tabs-rotation' : 'tabs-value';
        document.getElementById(activeTabsId).querySelectorAll('.tab-btn').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.market === market);
        });

        document.querySelectorAll('.chart').forEach(chart => {
            chart.classList.remove('active');
        });
        document.getElementById(`chart-${market}`).classList.add('active');

        if (this.charts[market] && this.charts[market].chart) {
            const container = document.getElementById(`chart-${market}`);
            this.charts[market].chart.applyOptions({
                width: container.clientWidth,
                height: container.clientHeight
            });
            this.charts[market].chart.timeScale().fitContent();
            this.charts[market].selectLastDay();
        }

        if (this.currentCategory === 'value' && ['global', 'nasdaq', 'twii'].includes(market)) {
            const selectedDate = this.getSelectedDate(market);
            this.sharpeChart.loadData(market, selectedDate);
            this.slopeChart.loadData(market, selectedDate);
        }
    }

    async switchPeriod(period) {
        this.currentPeriod = period;

        document.querySelectorAll('.period-btn').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.period === period);
        });

        this.showLoading(true);
        try {
            await this.loadMarketData();
            this.updateLastUpdate();
        } finally {
            this.showLoading(false);
        }
    }

    updateLastUpdate() {
        const now = new Date();
        const timeStr = now.toLocaleString('zh-TW', {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit'
        });
        document.getElementById('last-update').textContent = `最後更新: ${timeStr}`;
    }

    showLoading(show) {
        const loading = document.getElementById('loading');
        if (show) {
            loading.classList.remove('hidden');
        } else {
            loading.classList.add('hidden');
        }
    }
}

// 初始化應用程式
document.addEventListener('DOMContentLoaded', () => {
    window.finPackApp = new FinPackApp();
    window.finPackApp.init();
});
