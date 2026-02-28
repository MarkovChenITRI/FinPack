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

            this.charts.global.init();
            this.charts.nasdaq.init();
            this.charts.twii.init();

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
            await this.backtestEngine.init();
            window.backtestEngine = this.backtestEngine;

            // 綁定事件
            this.bindEvents();

            // 更新最後更新時間
            this.updateLastUpdate();
            
            // 啟動市場狀態檢測
            this.updateMarketStatus();
            setInterval(() => this.updateMarketStatus(), 60000); // 每分鐘更新

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
            if (e.detail.market === this.currentMarket) {
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
        // 目前僅支援價值投資模式
        this.currentCategory = 'value';
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

        document.getElementById('tabs-value').querySelectorAll('.tab-btn').forEach(btn => {
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

        if (['global', 'nasdaq', 'twii'].includes(market)) {
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
    
    /**
     * 更新市場狀態顯示
     * 
     * 判斷邏輯：用指數最新資料日期與今天比較
     * - 差異 <= 1 天：市場正常（可能開盤或剛收盤）
     * - 差異 > 1 天：市場休市（假日）
     */
    async updateMarketStatus() {
        const statusEl = document.getElementById('market-status');
        if (!statusEl) return;
        
        try {
            const response = await fetch('/api/market-status');
            const data = await response.json();
            
            const today = new Date(data.today);
            const usLatest = data.us_latest_date ? new Date(data.us_latest_date) : null;
            const twLatest = data.tw_latest_date ? new Date(data.tw_latest_date) : null;
            
            // 計算天數差異
            const dayMs = 24 * 60 * 60 * 1000;
            const usDiff = usLatest ? Math.floor((today - usLatest) / dayMs) : 999;
            const twDiff = twLatest ? Math.floor((today - twLatest) / dayMs) : 999;
            
            // 差異 <= 1 天視為正常（考慮時區和收盤後更新）
            const usNormal = usDiff <= 1;
            const twNormal = twDiff <= 1;
            
            // 更新顯示
            statusEl.classList.remove('all-open', 'partial-open', 'all-closed');
            
            if (usNormal && twNormal) {
                statusEl.textContent = '🟢 資料最新';
                statusEl.classList.add('all-open');
                statusEl.title = `美股: ${data.us_latest_date}\n台股: ${data.tw_latest_date}`;
            } else if (twNormal) {
                statusEl.textContent = `🟡 美股休市 (${usDiff}天)`;
                statusEl.classList.add('partial-open');
                statusEl.title = `美股最新: ${data.us_latest_date}\n台股最新: ${data.tw_latest_date}`;
            } else if (usNormal) {
                statusEl.textContent = `🟡 台股休市 (${twDiff}天)`;
                statusEl.classList.add('partial-open');
                statusEl.title = `美股最新: ${data.us_latest_date}\n台股最新: ${data.tw_latest_date}`;
            } else {
                const maxDiff = Math.max(usDiff, twDiff);
                statusEl.textContent = `🔴 市場休市 (${maxDiff}天)`;
                statusEl.classList.add('all-closed');
                statusEl.title = `美股最新: ${data.us_latest_date}\n台股最新: ${data.tw_latest_date}`;
            }
        } catch (error) {
            console.error('取得市場狀態失敗:', error);
            statusEl.textContent = '⚪ 狀態未知';
        }
    }
}

// 初始化應用程式
document.addEventListener('DOMContentLoaded', () => {
    window.finPackApp = new FinPackApp();
    window.finPackApp.init();
});
