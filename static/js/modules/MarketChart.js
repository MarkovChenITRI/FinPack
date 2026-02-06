/**
 * MarketChart - K線圖互動模組
 * 使用 Lightweight Charts (TradingView)
 */
export class MarketChart {
    constructor(containerId, market, title) {
        this.containerId = containerId;
        this.market = market;
        this.title = title;
        this.chart = null;
        this.candleSeries = null;
        this.volumeSeries = null;
        this.data = [];
        
        // 日期變更事件相關
        this.lastEmittedDate = null;
        this.dateChangeTimeout = null;
        
        // 鎖定日期相關
        this.lockedDate = null;
        this.lockedData = null;
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

        // 監聯十字線移動
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
        // 防護性檢查
        if (!data || !Array.isArray(data) || data.length === 0) {
            console.warn(`⚠️ ${this.title}: 無資料可顯示`);
            this.data = [];
            return;
        }
        
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
        
        // 預設鎖定最後一天
        this.lockDate(lastData);
    }

    handleClick(param) {
        if (!param.time) return;

        // param.time 可能是字串 "2024-01-01" 或物件 {year, month, day}
        const clickedTime = this.normalizeTime(param.time);
        const clickedData = this.data.find(d => d.time === clickedTime);
        if (!clickedData) {
            console.warn('找不到點擊日期的數據:', clickedTime);
            return;
        }

        // 鎖定該日期（添加標記）
        this.lockDate(clickedData);

        // 顯示點擊提示（發送事件給交易模擬器）
        this.showClickFeedback(clickedData);
    }

    handleCrosshairMove(param) {
        if (!param.time) return;

        const hoveredTime = this.normalizeTime(param.time);
        const hoveredData = this.data.find(d => d.time === hoveredTime);
        if (hoveredData) {
            // 滑動時更新資訊面板（顯示 hover 的數據）
            this.updateInfoPanel(hoveredData);
            
            // 發送日期變更事件（用於更新柱狀圖）
            this.emitDateChange(hoveredData);
        }
    }
    
    /**
     * 鎖定日期：在 K 線圖上添加標記
     */
    lockDate(data) {
        this.lockedDate = data.time;
        this.lockedData = data;
        
        // 使用 markers 在該日期添加標記
        this.candleSeries.setMarkers([
            {
                time: data.time,
                position: 'belowBar',
                color: '#58a6ff',
                shape: 'arrowUp',
                text: '🔒',
            }
        ]);
        
        // 更新鎖定日期顯示（如果有的話）
        this.updateLockedDateDisplay(data);
        
        console.log(`🔒 鎖定日期: ${data.time}`);
    }
    
    /**
     * 更新鎖定日期顯示
     */
    updateLockedDateDisplay(data) {
        // 發送鎖定日期事件給交易模擬器
        window.dispatchEvent(new CustomEvent('kline-date-locked', {
            detail: {
                market: this.market,
                date: data.time,
                data: data
            }
        }));
    }
    
    /**
     * 標準化時間格式為 "YYYY-MM-DD" 字串
     */
    normalizeTime(time) {
        if (typeof time === 'string') {
            return time;
        }
        if (typeof time === 'object' && time.year) {
            // Lightweight Charts 有時返回 {year, month, day} 物件
            const y = time.year;
            const m = String(time.month).padStart(2, '0');
            const d = String(time.day).padStart(2, '0');
            return `${y}-${m}-${d}`;
        }
        // 如果是 Unix timestamp (秒)
        if (typeof time === 'number') {
            const date = new Date(time * 1000);
            const y = date.getFullYear();
            const m = String(date.getMonth() + 1).padStart(2, '0');
            const d = String(date.getDate()).padStart(2, '0');
            return `${y}-${m}-${d}`;
        }
        return String(time);
    }
    
    /**
     * 發送日期變更事件（即時同步，無需 debounce，因為使用前端快取計算）
     */
    emitDateChange(data) {
        // 如果日期沒變，不重複發送
        if (this.lastEmittedDate === data.time) return;
        this.lastEmittedDate = data.time;
        
        // 使用 requestAnimationFrame 確保在下一幀渲染，避免阻塞滑鼠移動
        if (this.dateChangeRAF) {
            cancelAnimationFrame(this.dateChangeRAF);
        }
        
        this.dateChangeRAF = requestAnimationFrame(() => {
            window.dispatchEvent(new CustomEvent('kline-date-change', {
                detail: {
                    market: this.market,
                    date: data.time
                }
            }));
        });
    }

    updateInfoPanel(data) {
        // OHLC panel has been removed - no longer displayed
        // Keep this method for compatibility, but do nothing
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
