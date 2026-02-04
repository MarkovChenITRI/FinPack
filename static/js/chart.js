/**
 * FinPack K線圖互動模組
 * 使用 Lightweight Charts (TradingView)
 */

class MarketChart {
    constructor(containerId, market, title) {
        this.containerId = containerId;
        this.market = market;
        this.title = title;
        this.chart = null;
        this.candleSeries = null;
        this.volumeSeries = null;
        this.data = [];
    }

    init() {
        const container = document.getElementById(this.containerId);
        
        // 建立圖表
        this.chart = LightweightCharts.createChart(container, {
            width: container.clientWidth,
            height: container.clientHeight,
            layout: {
                background: { type: 'solid', color: '#161b22' },
                textColor: '#8b949e',
            },
            grid: {
                vertLines: { color: '#21262d' },
                horzLines: { color: '#21262d' },
            },
            crosshair: {
                mode: LightweightCharts.CrosshairMode.Normal,
                vertLine: {
                    color: '#58a6ff',
                    width: 1,
                    style: LightweightCharts.LineStyle.Dashed,
                    labelBackgroundColor: '#58a6ff',
                },
                horzLine: {
                    color: '#58a6ff',
                    width: 1,
                    style: LightweightCharts.LineStyle.Dashed,
                    labelBackgroundColor: '#58a6ff',
                },
            },
            rightPriceScale: {
                borderColor: '#30363d',
            },
            timeScale: {
                borderColor: '#30363d',
                timeVisible: true,
                secondsVisible: false,
            },
        });

        // 建立K線圖
        this.candleSeries = this.chart.addCandlestickSeries({
            upColor: '#3fb950',
            downColor: '#f85149',
            borderUpColor: '#3fb950',
            borderDownColor: '#f85149',
            wickUpColor: '#3fb950',
            wickDownColor: '#f85149',
        });

        // 建立成交量圖
        this.volumeSeries = this.chart.addHistogramSeries({
            color: '#58a6ff',
            priceFormat: {
                type: 'volume',
            },
            priceScaleId: '',
            scaleMargins: {
                top: 0.85,
                bottom: 0,
            },
        });

        // 監聽點擊事件
        this.chart.subscribeClick((param) => {
            this.handleClick(param);
        });

        // 監聽十字線移動
        this.chart.subscribeCrosshairMove((param) => {
            this.handleCrosshairMove(param);
        });

        // 監聽視窗大小變化
        window.addEventListener('resize', () => {
            this.chart.applyOptions({
                width: container.clientWidth,
            });
        });
    }

    setData(data) {
        this.data = data;

        // 轉換 K 線數據
        const candleData = data.map(d => ({
            time: d.time,
            open: d.open,
            high: d.high,
            low: d.low,
            close: d.close,
        }));

        // 轉換成交量數據
        const volumeData = data.map(d => ({
            time: d.time,
            value: d.volume,
            color: d.close >= d.open ? 'rgba(63, 185, 80, 0.5)' : 'rgba(248, 81, 73, 0.5)',
        }));

        this.candleSeries.setData(candleData);
        this.volumeSeries.setData(volumeData);

        // 自動調整時間軸
        this.chart.timeScale().fitContent();
        
        // 預設選中最後一天
        if (data.length > 0) {
            this.selectLastDay();
        }
    }
    
    selectLastDay() {
        if (this.data.length === 0) return;
        
        const lastData = this.data[this.data.length - 1];
        this.updateInfoPanel(lastData);
    }

    handleClick(param) {
        if (!param.time) return;

        const clickedData = this.data.find(d => d.time === param.time);
        if (!clickedData) return;

        // 更新資訊面板
        this.updateInfoPanel(clickedData);

        // 顯示點擊提示
        this.showClickFeedback(clickedData);
    }

    handleCrosshairMove(param) {
        if (!param.time) return;

        const hoveredData = this.data.find(d => d.time === param.time);
        if (hoveredData) {
            this.updateInfoPanel(hoveredData);
        }
    }

    updateInfoPanel(data) {
        document.getElementById('selected-date').textContent = data.time;
        document.getElementById('price-open').textContent = data.open.toLocaleString();
        document.getElementById('price-high').textContent = data.high.toLocaleString();
        document.getElementById('price-low').textContent = data.low.toLocaleString();
        document.getElementById('price-close').textContent = data.close.toLocaleString();

        // 根據漲跌設置顏色
        const closeElement = document.getElementById('price-close');
        if (data.close >= data.open) {
            closeElement.style.color = '#3fb950';
        } else {
            closeElement.style.color = '#f85149';
        }
    }

    showClickFeedback(data) {
        // 發送自訂事件，供其他模組使用
        window.dispatchEvent(new CustomEvent('kline-clicked', {
            detail: {
                market: this.market,
                title: this.title,
                date: data.time,
                data: data
            }
        }));

        console.log(`📅 選擇日期: ${data.time}`);
        console.log(`📊 ${this.title}`);
        console.log(`   開盤: ${data.open} | 最高: ${data.high} | 最低: ${data.low} | 收盤: ${data.close}`);
    }

    destroy() {
        if (this.chart) {
            this.chart.remove();
            this.chart = null;
        }
    }
}


/**
 * 主應用程式
 */
class FinPackApp {
    constructor() {
        this.charts = {};
        this.currentMarket = 'global';
        this.currentPeriod = '1y';
        this.currentCategory = 'value';  // 價值投資 / 資本輪動
        this.exchangeRate = 32.0;
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

            // 初始化圖表
            this.charts.global = new MarketChart('chart-global', 'global', '國際加權指數');
            this.charts.nasdaq = new MarketChart('chart-nasdaq', 'nasdaq', 'NASDAQ');
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

            // 載入數據
            await this.loadMarketData();

            // 恢復只顯示第一個圖表
            document.querySelectorAll('.chart').forEach(chart => {
                chart.classList.remove('active');
            });
            document.getElementById('chart-global').classList.add('active');

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
        document.querySelectorAll('.category-btn').forEach(btn => {
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

        // 監聽 K 線點擊事件
        window.addEventListener('kline-clicked', (e) => {
            console.log('K線被點擊:', e.detail);
        });
    }

    switchCategory(category) {
        this.currentCategory = category;

        // 更新分類按鈕樣式
        document.querySelectorAll('.category-btn').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.category === category);
        });

        // 切換子標籤顯示
        document.getElementById('tabs-value').classList.toggle('hidden', category !== 'value');
        document.getElementById('tabs-rotation').classList.toggle('hidden', category !== 'rotation');

        // 切換到該分類的第一個圖表
        const defaultMarket = category === 'value' ? 'global' : 'gold';
        this.switchMarket(defaultMarket);

        // 更新該分類內的 tab active 狀態
        const tabsContainer = document.getElementById(`tabs-${category}`);
        tabsContainer.querySelectorAll('.tab-btn').forEach((btn, index) => {
            btn.classList.toggle('active', index === 0);
        });
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
        document.getElementById('selected-date').textContent = '點擊K線查看';
        document.getElementById('price-open').textContent = '-';
        document.getElementById('price-high').textContent = '-';
        document.getElementById('price-low').textContent = '-';
        document.getElementById('price-close').textContent = '-';
        document.getElementById('price-close').style.color = '';
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
    const app = new FinPackApp();
    app.init();
});
