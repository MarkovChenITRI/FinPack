/**
 * app.js — BTC SMC 前端應用入口
 *
 * 初始化序列：
 * 1. 取得市場狀態（最新 BTC 價格）
 * 2. 載入 K 線資料 → SmcChart 渲染
 * 3. 載入 SMC 信號 → SmcChart 疊加
 * 4. 初始化 ContractPanel（表單 + 回測）
 * 5. 綁定信號切換 checkbox 事件
 * 6. 綁定 Timeframe 切換事件
 */

import { fetchKline, fetchSignals, fetchMarketStatus } from './api/btc.js';
import { SmcChart }      from './components/SmcChart.js';
import { ContractPanel } from './components/ContractPanel.js';
import { UI }            from './config.js';

class BtcSmcApp {
    constructor() {
        this.chart         = new SmcChart('chart-container');
        this.contractPanel = null;
        this.currentTf     = UI.TIMEFRAME;
        this.currentPeriod = UI.PERIOD;
    }

    async init() {
        // 初始化圖表
        this.chart.init();

        // 初始化面板（等圖表準備好後）
        this.contractPanel = new ContractPanel(this.chart);
        await this.contractPanel.init();

        // 綁定 UI 事件
        this._bindTimeframeButtons();
        this._bindSignalToggles();

        // 載入初始資料
        await this._loadAll(this.currentTf, this.currentPeriod);

        // 更新市場狀態列
        this._refreshMarketStatus();
        // 每 60 秒刷新價格
        setInterval(() => this._refreshMarketStatus(), 60_000);
    }

    // =========================================================================
    // 資料載入
    // =========================================================================

    async _loadAll(timeframe, period) {
        this._setLoading(true);
        try {
            const [klineRes, signalsRes] = await Promise.all([
                fetchKline(timeframe, period),
                fetchSignals(timeframe),
            ]);

            if (klineRes.data && klineRes.data.length > 0) {
                this.chart.setKlineData(klineRes.data);
            }

            this.chart.applySignals(signalsRes);

        } catch (e) {
            console.error('資料載入失敗:', e);
            this._showChartError('資料載入失敗：' + e.message);
        } finally {
            this._setLoading(false);
        }
    }

    async _refreshMarketStatus() {
        try {
            const status = await fetchMarketStatus();
            const el = document.getElementById('btc-price');
            if (el) el.textContent = `$${Number(status.latest_close).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
        } catch {}
    }

    // =========================================================================
    // UI 事件綁定
    // =========================================================================

    _bindTimeframeButtons() {
        document.querySelectorAll('[data-timeframe]').forEach(btn => {
            btn.addEventListener('click', async () => {
                const tf = btn.dataset.timeframe;
                if (tf === this.currentTf) return;
                this.currentTf = tf;

                document.querySelectorAll('[data-timeframe]').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');

                // 時間框架變更時也更新回測面板的 timeframe select
                const tfSelect = document.getElementById('timeframe');
                if (tfSelect) tfSelect.value = tf;

                await this._loadAll(tf, this.currentPeriod);
            });
        });
    }

    _bindSignalToggles() {
        const toggles = {
            'toggle-bos':   'bos',
            'toggle-choch': 'choch',
            'toggle-fvg':   'fvg',
            'toggle-ob':    'ob',
            'toggle-lp':    'lp',
        };

        Object.entries(toggles).forEach(([id, type]) => {
            const el = document.getElementById(id);
            if (!el) return;
            el.addEventListener('change', () => {
                this.chart.setVisibility(type, el.checked);
            });
        });
    }

    // =========================================================================
    // UI 狀態
    // =========================================================================

    _setLoading(loading) {
        const overlay = document.getElementById('chart-loading');
        if (overlay) overlay.style.display = loading ? 'flex' : 'none';
    }

    _showChartError(msg) {
        const overlay = document.getElementById('chart-loading');
        if (overlay) {
            overlay.innerHTML = `<span class="error-msg">${msg}</span>`;
            overlay.style.display = 'flex';
        }
    }
}

// 啟動
document.addEventListener('DOMContentLoaded', () => {
    const app = new BtcSmcApp();
    app.init().catch(err => console.error('App 初始化失敗:', err));
});
