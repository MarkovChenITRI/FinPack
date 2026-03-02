/**
 * SmcChart.js — BTC K 線圖 + SMC 信號 Overlay
 *
 * 使用 Lightweight Charts (TradingView) 渲染：
 * - BTC-USD K 線
 * - BOS / CHOCH markers
 * - FVG 色帶（price line pairs）
 * - Order Block 色帶
 * - Liquidity Pool 水平虛線
 *
 * 依賴：window.LightweightCharts（CDN 引入）
 */
import { SIGNAL_COLORS } from '../config.js';

export class SmcChart {
    /**
     * @param {string} containerId — DOM 容器 ID
     */
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        this.chart     = null;
        this.candleSeries = null;
        this.volumeSeries = null;

        // 信號 overlay 參照（供切換顯示用）
        this._markers    = [];
        this._fvgLines   = [];   // [{top, bottom}]
        this._obLines    = [];
        this._lpLines    = [];

        // 信號可見性狀態
        this.visibility = {
            bos:    true,
            choch:  true,
            fvg:    true,
            ob:     true,
            lp:     true,
        };
    }

    // =========================================================================
    // 初始化
    // =========================================================================

    init() {
        if (!window.LightweightCharts) {
            console.error('LightweightCharts 未載入');
            return;
        }

        this.chart = LightweightCharts.createChart(this.container, {
            layout: {
                background: { color: '#0d1117' },
                textColor:  '#c9d1d9',
            },
            grid: {
                vertLines: { color: '#21262d' },
                horzLines:  { color: '#21262d' },
            },
            crosshair: {
                mode: LightweightCharts.CrosshairMode.Normal,
            },
            rightPriceScale: {
                borderColor: '#30363d',
            },
            timeScale: {
                borderColor:     '#30363d',
                timeVisible:     true,
                secondsVisible:  false,
            },
        });

        this.candleSeries = this.chart.addCandlestickSeries({
            upColor:          '#26a69a',
            downColor:        '#ef5350',
            borderUpColor:    '#26a69a',
            borderDownColor:  '#ef5350',
            wickUpColor:      '#26a69a',
            wickDownColor:    '#ef5350',
        });

        this.volumeSeries = this.chart.addHistogramSeries({
            color:    '#26a69a',
            priceFormat: { type: 'volume' },
            priceScaleId: 'volume',
        });
        this.chart.priceScale('volume').applyOptions({
            scaleMargins: { top: 0.85, bottom: 0 },
        });

        // 自動適應容器尺寸
        new ResizeObserver(() => {
            this.chart.applyOptions({
                width:  this.container.clientWidth,
                height: this.container.clientHeight,
            });
        }).observe(this.container);
    }

    // =========================================================================
    // 資料載入
    // =========================================================================

    /** 設定 K 線資料 */
    setKlineData(data) {
        if (!this.candleSeries) return;

        const candles = data.map(d => ({
            time:  d.time,
            open:  d.open,
            high:  d.high,
            low:   d.low,
            close: d.close,
        }));

        const volumes = data.map(d => ({
            time:  d.time,
            value: d.volume || 0,
            color: d.close >= d.open ? 'rgba(38,166,154,0.4)' : 'rgba(239,83,80,0.4)',
        }));

        this.candleSeries.setData(candles);
        this.volumeSeries.setData(volumes);
        this.chart.timeScale().fitContent();
    }

    // =========================================================================
    // 信號 Overlay
    // =========================================================================

    /** 套用全部 SMC 信號 */
    applySignals(signals) {
        this._clearOverlays();

        this._buildBosChochMarkers(signals.bos || [], signals.choch || []);
        this._buildFvgBands(signals.fvgs || []);
        this._buildObBands(signals.order_blocks || []);
        this._buildLpLines(signals.liquidity_pools || []);

        this._applyVisibility();
    }

    /** 切換特定信號類型的可見性 */
    setVisibility(type, visible) {
        this.visibility[type] = visible;
        this._applyVisibility();
    }

    // =========================================================================
    // 內部：建立 Markers（BOS / CHOCH）
    // =========================================================================

    _buildBosChochMarkers(bosList, chochList) {
        const markers = [];

        for (const b of bosList) {
            markers.push({
                time:     b.time,
                position: b.direction === 'bullish' ? 'belowBar' : 'aboveBar',
                color:    b.direction === 'bullish' ? SIGNAL_COLORS.BOS_BULL : SIGNAL_COLORS.BOS_BEAR,
                shape:    b.direction === 'bullish' ? 'arrowUp' : 'arrowDown',
                text:     'BOS',
                size:     1,
                _type:    'bos',
            });
        }

        for (const c of chochList) {
            markers.push({
                time:     c.time,
                position: c.direction === 'bullish' ? 'belowBar' : 'aboveBar',
                color:    c.direction === 'bullish' ? SIGNAL_COLORS.CHOCH_BULL : SIGNAL_COLORS.CHOCH_BEAR,
                shape:    c.direction === 'bullish' ? 'arrowUp' : 'arrowDown',
                text:     'ChOCH',
                size:     1,
                _type:    'choch',
            });
        }

        // 按時間排序（Lightweight Charts 要求）
        markers.sort((a, b) => {
            if (a.time < b.time) return -1;
            if (a.time > b.time) return 1;
            return 0;
        });

        this._markers = markers;
    }

    _buildFvgBands(fvgs) {
        this._fvgLines = fvgs.map(fvg => {
            const color = fvg.type === 'bullish'
                ? SIGNAL_COLORS.FVG_BULL
                : SIGNAL_COLORS.FVG_BEAR;

            const topLine = this.candleSeries.createPriceLine({
                price:     fvg.top,
                color:     color.replace('0.15', '0.5'),
                lineWidth: 1,
                lineStyle: LightweightCharts.LineStyle.Dashed,
                axisLabelVisible: false,
                title:     fvg.filled ? `FVG✓` : `FVG`,
            });
            const botLine = this.candleSeries.createPriceLine({
                price:     fvg.bottom,
                color:     color.replace('0.15', '0.5'),
                lineWidth: 1,
                lineStyle: LightweightCharts.LineStyle.Dashed,
                axisLabelVisible: false,
                title:     '',
            });

            return { topLine, botLine, filled: fvg.filled };
        });
    }

    _buildObBands(obs) {
        this._obLines = obs.map(ob => {
            const color = ob.type === 'bullish'
                ? SIGNAL_COLORS.OB_BULL
                : SIGNAL_COLORS.OB_BEAR;
            const borderColor = ob.type === 'bullish'
                ? SIGNAL_COLORS.BOS_BULL
                : SIGNAL_COLORS.BOS_BEAR;

            const topLine = this.candleSeries.createPriceLine({
                price:     ob.top,
                color:     borderColor,
                lineWidth: ob.valid ? 2 : 1,
                lineStyle: ob.valid
                    ? LightweightCharts.LineStyle.Solid
                    : LightweightCharts.LineStyle.Dotted,
                axisLabelVisible: ob.valid,
                title:     ob.valid ? (ob.type === 'bullish' ? 'Bull OB' : 'Bear OB') : '',
            });
            const botLine = this.candleSeries.createPriceLine({
                price:     ob.bottom,
                color:     borderColor,
                lineWidth: ob.valid ? 1 : 1,
                lineStyle: LightweightCharts.LineStyle.Dashed,
                axisLabelVisible: false,
                title:     '',
            });

            return { topLine, botLine, valid: ob.valid };
        });
    }

    _buildLpLines(lps) {
        this._lpLines = lps.map(lp => {
            const isBuy = lp.type === 'buy_side';
            const color = isBuy ? SIGNAL_COLORS.LP_BUY : SIGNAL_COLORS.LP_SELL;
            const line = this.candleSeries.createPriceLine({
                price:     lp.price,
                color:     color,
                lineWidth: 1,
                lineStyle: LightweightCharts.LineStyle.LargeDashed,
                axisLabelVisible: true,
                title:     isBuy ? `BSL×${lp.touch_count}` : `SSL×${lp.touch_count}`,
            });
            return { line };
        });
    }

    // =========================================================================
    // 內部：可見性控制
    // =========================================================================

    _applyVisibility() {
        if (!this.candleSeries) return;

        // Markers（BOS + CHOCH 合併，分別過濾）
        const visibleMarkers = this._markers.filter(m => {
            if (m._type === 'bos'   && !this.visibility.bos)   return false;
            if (m._type === 'choch' && !this.visibility.choch) return false;
            return true;
        });
        this.candleSeries.setMarkers(visibleMarkers);

        // FVG lines
        this._fvgLines.forEach(({ topLine, botLine }) => {
            const opacity = this.visibility.fvg ? '0.5' : '0.0';
            topLine.applyOptions({ color: topLine.options().color.replace(/[\d.]+\)$/, `${opacity})`) });
            botLine.applyOptions({ color: botLine.options().color.replace(/[\d.]+\)$/, `${opacity})`) });
        });

        // OB lines
        this._obLines.forEach(({ topLine, botLine }) => {
            const lw = this.visibility.ob ? (topLine.options().lineWidth || 1) : 0;
            topLine.applyOptions({ lineWidth: this.visibility.ob ? 2 : 0 });
            botLine.applyOptions({ lineWidth: this.visibility.ob ? 1 : 0 });
        });

        // LP lines
        this._lpLines.forEach(({ line }) => {
            line.applyOptions({ lineWidth: this.visibility.lp ? 1 : 0 });
        });
    }

    _clearOverlays() {
        // 移除現有 price lines
        [...this._fvgLines, ...this._obLines].forEach(({ topLine, botLine }) => {
            try { this.candleSeries.removePriceLine(topLine); } catch {}
            try { this.candleSeries.removePriceLine(botLine); } catch {}
        });
        this._lpLines.forEach(({ line }) => {
            try { this.candleSeries.removePriceLine(line); } catch {}
        });
        this.candleSeries.setMarkers([]);

        this._markers  = [];
        this._fvgLines = [];
        this._obLines  = [];
        this._lpLines  = [];
    }

    // =========================================================================
    // 公用
    // =========================================================================

    /** 設定權益曲線（用於回測結果覆蓋顯示） */
    setEquityCurveOverlay(equityCurve) {
        if (this._equitySeries) {
            this.chart.removeSeries(this._equitySeries);
            this._equitySeries = null;
        }
        if (!equityCurve || equityCurve.length === 0) return;

        this._equitySeries = this.chart.addLineSeries({
            color:      '#f39c12',
            lineWidth:  2,
            priceScaleId: 'equity',
        });
        this.chart.priceScale('equity').applyOptions({
            scaleMargins: { top: 0.1, bottom: 0.4 },
        });

        this._equitySeries.setData(
            equityCurve.map(p => ({ time: p.time, value: p.equity }))
        );
    }

    clearEquityCurve() {
        if (this._equitySeries) {
            this.chart.removeSeries(this._equitySeries);
            this._equitySeries = null;
        }
    }
}
