/**
 * ContractPanel.js — SMC 合約回測設定面板
 *
 * 職責：
 * - 從 /api/backtest/config 取得後端唯一 config（DEFAULT_SMC_CONFIG），
 *   並用它初始化所有表單欄位（無前端硬編碼預設值）
 * - 收集使用者輸入並呼叫 /api/backtest/run（後端引擎執行）
 * - 渲染回測結果（指標、交易明細表）
 * - 觸發 SmcChart 顯示權益曲線
 */
import { runBacktest, fetchBacktestConfig } from '../api/backtest.js';
import { signClass } from '../utils/formatter.js';

export class ContractPanel {
    /**
     * @param {SmcChart} chart — 用於顯示權益曲線
     */
    constructor(chart) {
        this.chart = chart;
        this._cfg  = {};   // 後端 DEFAULT_SMC_CONFIG，在 init() 載入
    }

    async init() {
        this._bindForm();
        this._bindCheckboxes();

        // 唯一 config 來源：後端 /api/backtest/config
        try {
            const response = await fetchBacktestConfig();
            this._cfg = response.defaults || {};
            this._applyDefaults(this._cfg);
        } catch (e) {
            console.warn('[ContractPanel] 載入後端設定失敗:', e);
        }
    }

    // =========================================================================
    // 表單綁定
    // =========================================================================

    _bindForm() {
        const form = document.getElementById('backtest-form');
        if (!form) return;

        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            await this._runBacktest();
        });

        // 槓桿變動時更新強平提示
        const leverageInput = document.getElementById('leverage');
        if (leverageInput) {
            leverageInput.addEventListener('input', () => this._updateLiqHint());
        }
    }

    _bindCheckboxes() {
        document.querySelectorAll('[name="direction"]').forEach(el => {
            el.addEventListener('change', () => this._updateDirectionUI());
        });
    }

    /**
     * 將後端 DEFAULT_SMC_CONFIG 填入所有表單欄位。
     * 這是唯一設定表單初始值的地方，無任何前端硬編碼預設值。
     *
     * @param {Object} d — 後端 DEFAULT_SMC_CONFIG
     */
    _applyDefaults(d) {
        // 資金設定
        this._setVal('initial-capital', d.initial_capital ?? '');
        this._setVal('leverage',        d.leverage        ?? 1);
        if (d.risk_per_trade != null) {
            this._setVal('risk-per-trade', (d.risk_per_trade * 100).toFixed(1));
        }
        this._setVal('start-date', d.start_date ?? '');
        this._setVal('end-date',   d.end_date   ?? '');
        this._setVal('timeframe',  d.timeframe  ?? '1d');

        // 交易方向（依 allow_long / allow_short 對應 radio）
        const dir = (d.allow_long && d.allow_short) ? 'both'
                  : d.allow_short                   ? 'short'
                  :                                   'long';
        const dirEl = document.querySelector(`[name="direction"][value="${dir}"]`);
        if (dirEl) dirEl.checked = true;

        // 進場條件 checkboxes
        const ec = d.entry_conditions || {};
        this._setChecked('cond-bias',     ec.require_bias?.enabled     ?? true);
        this._setChecked('cond-discount', ec.require_discount?.enabled ?? true);
        this._setChecked('cond-ob',       ec.require_ob?.enabled       ?? true);
        this._setChecked('cond-fvg',      ec.require_fvg?.enabled      ?? true);

        // 出場條件 checkboxes + 數值
        const xc = d.exit_conditions || {};
        this._setChecked('exit-sl',        xc.stop_loss_pct?.enabled         ?? true);
        this._setChecked('exit-tp-lp',     xc.take_profit_liquidity?.enabled ?? true);
        this._setChecked('exit-structure', xc.structure_exit?.enabled        ?? true);
        this._setChecked('exit-max-bars',  xc.max_holding_bars?.enabled      ?? true);

        if (xc.stop_loss_pct?.pct != null) {
            this._setVal('stop-loss-pct', (xc.stop_loss_pct.pct * 100).toFixed(1));
        }
        if (xc.max_holding_bars?.bars != null) {
            this._setVal('max-holding-bars', xc.max_holding_bars.bars);
        }

        // 更新強平提示
        this._updateLiqHint();
    }

    // =========================================================================
    // 執行回測
    // =========================================================================

    async _runBacktest() {
        const btn = document.getElementById('run-backtest-btn');
        const resultSection = document.getElementById('backtest-result');

        btn.disabled = true;
        btn.textContent = '回測中...';
        this._showLoading(resultSection);
        this.chart.clearEquityCurve();

        try {
            const params = this._collectParams();
            const res    = await runBacktest(params);

            if (!res.success) {
                this._showError(resultSection, res.error || '回測失敗');
                return;
            }

            this._renderResult(resultSection, res.result);
            this.chart.setEquityCurveOverlay(res.result.equity_curve);

        } catch (e) {
            this._showError(resultSection, e.message || '網路錯誤');
        } finally {
            btn.disabled    = false;
            btn.textContent = '執行回測';
        }
    }

    /**
     * 收集表單值並組成後端 API 請求 body。
     * fallback 使用 this._cfg（後端 config），不使用任何前端硬編碼值。
     */
    _collectParams() {
        const d   = this._cfg;
        const xc  = d.exit_conditions || {};
        const direction = this._getChecked('direction') || 'long';

        return {
            initial_capital: parseFloat(this._getVal('initial-capital')) || d.initial_capital,
            leverage:        parseFloat(this._getVal('leverage'))         || d.leverage || 1,
            risk_per_trade:  (parseFloat(this._getVal('risk-per-trade')) / 100) || d.risk_per_trade,
            timeframe:       this._getVal('timeframe') || d.timeframe || '1d',
            start_date:      this._getVal('start-date') || d.start_date,
            end_date:        this._getVal('end-date') || null,
            allow_long:      direction === 'long'  || direction === 'both',
            allow_short:     direction === 'short' || direction === 'both',
            entry_conditions: {
                require_bias:     { enabled: this._isChecked('cond-bias') },
                require_discount: { enabled: this._isChecked('cond-discount') },
                require_fvg:      { enabled: this._isChecked('cond-fvg') },
                require_ob:       { enabled: this._isChecked('cond-ob') },
            },
            exit_conditions: {
                stop_loss_pct: {
                    enabled: this._isChecked('exit-sl'),
                    pct:     (parseFloat(this._getVal('stop-loss-pct')) / 100) || xc.stop_loss_pct?.pct,
                },
                take_profit_liquidity: { enabled: this._isChecked('exit-tp-lp') },
                structure_exit:        { enabled: this._isChecked('exit-structure') },
                max_holding_bars: {
                    enabled: this._isChecked('exit-max-bars'),
                    bars:    parseInt(this._getVal('max-holding-bars')) || xc.max_holding_bars?.bars,
                },
            },
        };
    }

    // =========================================================================
    // 渲染結果
    // =========================================================================

    _renderResult(container, result) {
        const m = result.metrics;
        const totalRetRaw = m.total_return_raw ?? 0;
        const bh = parseFloat(m.benchmark_return) / 100;

        container.innerHTML = `
            <div class="result-metrics">
                <div class="metric-grid">
                    <div class="metric-card">
                        <div class="metric-label">總報酬</div>
                        <div class="metric-value ${signClass(totalRetRaw)}">${m.total_return}</div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-label">年化報酬</div>
                        <div class="metric-value ${signClass(m.annualized_return)}">${m.annualized_return}</div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-label">勝率</div>
                        <div class="metric-value">${m.win_rate}</div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-label">最大回撤</div>
                        <div class="metric-value negative">${m.max_drawdown}</div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-label">Sharpe Ratio</div>
                        <div class="metric-value">${m.sharpe_ratio}</div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-label">平均風報比</div>
                        <div class="metric-value">${m.avg_rr}</div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-label">總交易次數</div>
                        <div class="metric-value">${m.total_trades}</div>
                    </div>
                    <div class="metric-card">
                        <div class="metric-label">槓桿</div>
                        <div class="metric-value">${m.leverage}x</div>
                    </div>
                </div>

                <div class="benchmark-bar">
                    <span>BTC Buy &amp; Hold: <strong class="${signClass(bh)}">${m.benchmark_return}</strong></span>
                    <span>Alpha: <strong class="${signClass(m.alpha)}">${m.alpha}</strong></span>
                    <span>最終資金: <strong>${m.final_equity}</strong></span>
                </div>
            </div>

            <div class="trades-section">
                <h4>交易明細 (${result.trades.length} 筆)</h4>
                ${this._renderTradesTable(result.trades)}
            </div>
        `;
    }

    _renderTradesTable(trades) {
        if (!trades.length) return '<p class="no-data">無交易紀錄</p>';

        const fmt = (v) => v != null
            ? '$' + Number(v).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
            : '-';

        const rows = trades.map(t => {
            const dirClass = t.direction === 'long' ? 'positive' : 'negative';
            const pnlClass = t.pnl >= 0 ? 'positive' : 'negative';
            const pnlSign  = t.pnl >= 0 ? '+' : '';
            const rrText   = t.rr != null ? `1 : ${t.rr}` : '-';
            const rrClass  = t.rr != null && t.rr >= 1 ? 'positive' : (t.rr != null ? 'negative' : '');

            return `
            <tr>
                <td>${t.entry_date}</td>
                <td>${t.exit_date}</td>
                <td class="${dirClass}">${t.direction === 'long' ? 'Long' : 'Short'}</td>
                <td>${fmt(t.entry_price)}</td>
                <td class="negative">${fmt(t.stop_loss)}</td>
                <td class="tp-col">${fmt(t.take_profit)}</td>
                <td class="${rrClass}">${rrText}</td>
                <td>${fmt(t.exit_price)}</td>
                <td class="muted">${t.liq_price ? fmt(t.liq_price) : '-'}</td>
                <td>${t.leverage}x</td>
                <td class="${pnlClass}">$${pnlSign}${t.pnl.toFixed(2)}</td>
                <td class="${pnlClass}">${t.pnl_pct}</td>
                <td class="reason">${t.reason}</td>
            </tr>`;
        }).join('');

        return `
            <div class="table-wrapper">
                <table class="trades-table">
                    <thead>
                        <tr>
                            <th>進場日</th><th>出場日</th><th>方向</th>
                            <th>進場價</th><th>止損價</th><th>止盈目標</th><th>風報比</th>
                            <th>出場價</th><th>強平價</th><th>槓桿</th>
                            <th>PnL (USD)</th><th>報酬率</th><th>原因</th>
                        </tr>
                    </thead>
                    <tbody>${rows}</tbody>
                </table>
            </div>
        `;
    }

    // =========================================================================
    // UI 輔助
    // =========================================================================

    _updateLiqHint() {
        const lev = parseFloat(this._getVal('leverage')) || 1;
        const hint = document.getElementById('liq-hint');
        if (!hint) return;
        if (lev <= 1) {
            hint.textContent = '現貨模式（無強平風險）';
        } else {
            const longLiq  = (1 - 1/lev) * 100;
            const shortLiq = (1 + 1/lev) * 100;
            hint.textContent = `Long 強平於入場 -${longLiq.toFixed(1)}%，Short 強平於 +${shortLiq.toFixed(1)}%`;
        }
    }

    _updateDirectionUI() {
        const dir = this._getChecked('direction');
        const shortConds = document.getElementById('short-cond-note');
        if (shortConds) {
            shortConds.style.display = (dir === 'short' || dir === 'both') ? 'block' : 'none';
        }
    }

    _showLoading(container) {
        container.innerHTML = '<div class="loading">回測計算中...</div>';
    }

    _showError(container, msg) {
        container.innerHTML = `<div class="error-msg">錯誤：${msg}</div>`;
    }

    // =========================================================================
    // DOM 工具
    // =========================================================================

    _getVal(id) {
        const el = document.getElementById(id);
        return el ? el.value : '';
    }

    _setVal(id, value) {
        const el = document.getElementById(id);
        if (el) el.value = value;
    }

    _isChecked(id) {
        const el = document.getElementById(id);
        return el ? el.checked : false;
    }

    _setChecked(id, value) {
        const el = document.getElementById(id);
        if (el) el.checked = Boolean(value);
    }

    _getChecked(name) {
        const el = document.querySelector(`[name="${name}"]:checked`);
        return el ? el.value : null;
    }
}
