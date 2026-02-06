/**
 * FinPackApp - 主應用程式
 */
import { MarketChart } from './MarketChart.js';
import { IndustryBarChart } from './IndustryBarChart.js';
import { industryDataCache } from './IndustryDataCache.js';
import { TradeSimulator } from './TradeSimulator.js';
import { BacktestEngine } from './BacktestEngine.js';

export class FinPackApp {
    constructor() {
        this.charts = {};
        this.sharpeChart = null;   // Sharpe Top 圖表
        this.slopeChart = null;    // Sharpe Slope Top 圖表
        this.currentMarket = 'global';
        this.currentPeriod = '1y';
        this.currentCategory = 'value';  // 價值投資 / 資本輪動
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

            // 初始化 Sharpe Top 圖表（使用前端快取）
            this.sharpeChart = new IndustryBarChart(
                'industry-bar-chart', 
                'industry-legend',
                'sharpe',  // dataType
                'Sharpe'
            );
            this.sharpeChart.init();

            // 初始化 Sharpe Slope Top 圖表（增長率）
            this.slopeChart = new IndustryBarChart(
                'slope-bar-chart',
                'slope-legend',
                'slope',  // dataType
                'Slope'
            );
            this.slopeChart.init();

            // 載入數據
            await this.loadMarketData();
            
            // 預載入產業分析資料（一次性載入，之後即時計算）
            await industryDataCache.load();
            
            // 初始顯示（預設 global，最新日期）
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
            
            // 將 tradeSimulator 暴露到全域（供按鈕 onclick 使用）
            window.tradeSimulator = this.tradeSimulator;
            
            // 初始化回測引擎
            this.backtestEngine = new BacktestEngine();
            this.backtestEngine.init();
            
            // 將 backtestEngine 暴露到全域
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
            const response = await fetch('/api/exchange-rate');
            const data = await response.json();
            this.exchangeRate = data.rate;
            document.getElementById('exchange-rate').textContent = `USD/TWD: ${this.exchangeRate}`;
        } catch (error) {
            console.error('獲取匯率失敗:', error);
        }
    }

    async loadMarketData() {
        try {
            const response = await fetch(`/api/market-data?period=${this.currentPeriod}`);
            const data = await response.json();

            if (data.global && data.global.length > 0) {
                this.charts.global.setData(data.global);
            }

            if (data.nasdaq && data.nasdaq.length > 0) {
                this.charts.nasdaq.setData(data.nasdaq);
            }

            if (data.twii && data.twii.length > 0) {
                this.charts.twii.setData(data.twii);
            }

            if (data.gold && data.gold.length > 0) {
                this.charts.gold.setData(data.gold);
            }

            if (data.btc && data.btc.length > 0) {
                this.charts.btc.setData(data.btc);
            }

            if (data.bonds && data.bonds.length > 0) {
                this.charts.bonds.setData(data.bonds);
            }

        } catch (error) {
            console.error('載入市場數據失敗:', error);
            throw error;
        }
    }

    bindEvents() {
        // 分類切換 (價值投資/資本輪動)
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

        // 監聽 K 線日期變更事件（滑鼠移動或點擊）
        window.addEventListener('kline-date-change', (e) => {
            // 只有在價值投資類別且市場一致時才更新
            if (this.currentCategory === 'value' && e.detail.market === this.currentMarket) {
                const date = e.detail.date;
                this.updateIndustryCharts(this.currentMarket, date);
            }
        });
        
        // 監聽 K 線點擊事件（用於 console log）
        window.addEventListener('kline-clicked', (e) => {
            console.log('K線被點擊:', e.detail);
        });
    }
    
    /**
     * 更新產業分析圖表（從前端快取即時計算，無網路延遲）
     */
    updateIndustryCharts(market, date) {
        if (!this.sharpeChart || !this.slopeChart) return;
        
        // 同步更新，無需 await
        this.sharpeChart.loadData(market, date);
        this.slopeChart.loadData(market, date);
    }

    switchCategory(category) {
        this.currentCategory = category;

        // 更新分類按鈕樣式
        document.querySelectorAll('.nav-item').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.category === category);
        });

        // 切換子標籤顯示
        document.getElementById('tabs-value').classList.toggle('hidden', category !== 'value');
        document.getElementById('tabs-rotation').classList.toggle('hidden', category !== 'rotation');

        // 切換布局容器顯示
        document.getElementById('value-layout').classList.toggle('hidden', category !== 'value');
        document.getElementById('rotation-charts').classList.toggle('hidden', category !== 'rotation');

        // 切換到該分類的第一個圖表
        const defaultMarket = category === 'value' ? 'global' : 'gold';
        this.switchMarket(defaultMarket);

        // 更新該分類內的 tab active 狀態
        const tabsContainer = document.getElementById(`tabs-${category}`);
        tabsContainer.querySelectorAll('.tab-btn').forEach((btn, index) => {
            btn.classList.toggle('active', index === 0);
        });

        // 價值投資類別：載入兩個產業分析圖表（使用當前選中日期）
        if (category === 'value') {
            const selectedDate = this.getSelectedDate('global');
            this.sharpeChart.loadData('global', selectedDate);
            this.slopeChart.loadData('global', selectedDate);
        }
    }
    
    /**
     * 取得指定市場當前選中的日期
     */
    getSelectedDate(market) {
        // Get the locked date from the chart instance
        if (this.charts[market] && this.charts[market].lockedDate) {
            return this.charts[market].lockedDate;
        }
        return null;
    }

    switchMarket(market) {
        this.currentMarket = market;

        // 更新當前分類內的標籤樣式
        const activeTabsId = this.currentCategory === 'rotation' ? 'tabs-rotation' : 'tabs-value';
        document.getElementById(activeTabsId).querySelectorAll('.tab-btn').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.market === market);
        });

        // 切換圖表顯示
        document.querySelectorAll('.chart').forEach(chart => {
            chart.classList.remove('active');
        });
        document.getElementById(`chart-${market}`).classList.add('active');

        // 調整當前圖表尺寸
        if (this.charts[market] && this.charts[market].chart) {
            const container = document.getElementById(`chart-${market}`);
            this.charts[market].chart.applyOptions({
                width: container.clientWidth,
                height: container.clientHeight
            });
            this.charts[market].chart.timeScale().fitContent();
            
            // 顯示該圖表的最後一天數據
            this.charts[market].selectLastDay();
        }

        // 更新兩個產業分析圖表（僅價值投資類別，使用當前選中日期）
        if (this.currentCategory === 'value' && ['global', 'nasdaq', 'twii'].includes(market)) {
            const selectedDate = this.getSelectedDate(market);
            this.sharpeChart.loadData(market, selectedDate);
            this.slopeChart.loadData(market, selectedDate);
        }
    }

    async switchPeriod(period) {
        this.currentPeriod = period;

        // 更新按鈕樣式
        document.querySelectorAll('.period-btn').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.period === period);
        });

        // 重新載入數據
        this.showLoading(true);
        try {
            await this.loadMarketData();
            this.updateLastUpdate();
        } finally {
            this.showLoading(false);
        }
    }

    resetInfoPanel() {
        // OHLC panel has been removed - no longer displayed
        // Keep this method for compatibility, but do nothing
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
