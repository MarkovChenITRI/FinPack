/**
 * BacktestEngine - 交易回測前端控制器
 *
 * 標準資料流：
 *   1. init() → 鎖定 UI → loadBackendConfig() → 解鎖 UI
 *   2. loadBackendConfig() → this.config = deepCopy(DEFAULT_CONFIG) → applyConfigToDOM()
 *   3. 使用者調整任一欄位 → _bindLiveUpdates() 即時更新 this.config
 *   4. runBacktest() → 直接送出 this.config → 顯示結果
 *
 * 核心計算由後端執行：POST /api/backtest/run
 */

export class BacktestEngine {
    constructor() {
        this.config = null;          // 唯一資料真相來源，結構與後端 DEFAULT_CONFIG 完全一致
        this.serverDefaults = null;  // 後端 DEFAULT_CONFIG 的鏡像，永不修改
        this.results = null;
        this.equityChart = null;
        this.equityCurveData = null;
        this.selectedEquityIndex = -1;
        this.isRunning = false;
    }

    // =========================================================================
    // 初始化
    // =========================================================================

    async init() {
        // F1 fix：在取得 config 前鎖定 UI
        this._setLoading(true);
        this.bindEvents();
        await this.loadBackendConfig();
        this._setLoading(false);
    }

    _setLoading(loading) {
        const runBtn = document.getElementById('bt-run-btn');
        if (runBtn) {
            runBtn.disabled = loading;
            runBtn.textContent = loading ? '⏳ 載入配置中...' : '🚀 開始回測';
        }
    }

    // =========================================================================
    // 後端 config 載入（F2 fix：單一 config 物件）
    // =========================================================================

    async loadBackendConfig() {
        console.log('🔄 正在從後端取得 DEFAULT_CONFIG... (GET /api/backtest/config)');
        try {
            const response = await fetch('/api/backtest/config');
            if (!response.ok) {
                throw new Error(`HTTP ${response.status} ${response.statusText}`);
            }
            const data = await response.json();
            if (!data.defaults) {
                throw new Error('後端回應缺少 defaults 欄位');
            }

            this.serverDefaults = data.defaults;
            this.config = this._deepCopy(data.defaults);

            // 先 log，再套用 DOM，確保 log 一定看得到
            const d = data.defaults;
            console.group('✅ 後端 DEFAULT_CONFIG 載入成功');
            console.log('基礎參數:', {
                initial_capital: d.initial_capital,
                amount_per_stock: d.amount_per_stock,
                max_positions: d.max_positions,
                market: d.market,
                start_date: d.start_date,
                end_date: d.end_date,
                rebalance_freq: d.rebalance_freq
            });
            console.log('買入條件:', d.buy_conditions);
            console.log('賣出條件:', d.sell_conditions);
            console.log('再平衡策略:', d.rebalance_strategy);
            console.groupEnd();

            this.applyConfigToDOM(this.config);
        } catch (e) {
            console.error('❌ 無法載入後端配置:', e);
            const runBtn = document.getElementById('bt-run-btn');
            if (runBtn) {
                runBtn.textContent = '⚠️ 配置載入失敗，請重整頁面';
                runBtn.disabled = true;
            }
        }
    }

    _deepCopy(obj) {
        return JSON.parse(JSON.stringify(obj));
    }

    // =========================================================================
    // DOM ↔ config 同步
    // =========================================================================

    /**
     * 將 config 物件的值套用至所有表單元素
     * 同時處理「新增的隱藏參數輸入框」（F5/F6 fix）
     */
    applyConfigToDOM(cfg) {
        if (!cfg) return;

        const setVal = (id, val) => {
            const el = document.getElementById(id);
            if (el && val !== undefined && val !== null) el.value = val;
        };
        const setCheck = (name, value, checked) => {
            const el = document.querySelector(`input[name="${name}"][value="${value}"]`);
            if (el) el.checked = !!checked;
        };
        const setRadio = (name, value) => {
            const el = document.querySelector(`input[name="${name}"][value="${value}"]`);
            if (el) el.checked = true;
        };

        // ===== 基礎參數 =====
        setVal('bt-initial-capital', cfg.initial_capital);
        setVal('bt-amount-per-stock', cfg.amount_per_stock);
        setVal('bt-max-positions', cfg.max_positions);
        setRadio('bt-market', cfg.market);
        setRadio('bt-rebalance-freq', cfg.rebalance_freq);
        // DT4 fix：直接設定固定日期（不換算月數）
        // config 為唯一真相：null → 明確清空（確保 reset 後 DOM 與 config 一致）
        setVal('bt-start-date', cfg.start_date);
        const endDateEl = document.getElementById('bt-end-date');
        if (endDateEl) endDateEl.value = cfg.end_date ?? '';

        // ===== 買入條件 =====
        const bc = cfg.buy_conditions || {};

        setCheck('bt-filter-a', 'sharpe_rank', bc.sharpe_rank?.enabled);
        setVal('bt-sharpe-top-n', bc.sharpe_rank?.top_n);

        setCheck('bt-filter-a', 'sharpe_threshold', bc.sharpe_threshold?.enabled);
        setVal('bt-sharpe-threshold', bc.sharpe_threshold?.threshold);

        setCheck('bt-filter-a', 'sharpe_streak', bc.sharpe_streak?.enabled);
        setVal('bt-sharpe-consecutive-days', bc.sharpe_streak?.days);
        setVal('bt-sharpe-streak-top-n', bc.sharpe_streak?.top_n);           // F5 fix

        // B 類 (growth)：radio，含 none 選項（F9 fix）
        const growthVal = bc.growth_streak?.enabled ? 'growth_streak'
                        : (bc.growth_rank?.enabled ? 'growth_rank' : 'none');
        setRadio('bt-growth-rule', growthVal);
        setVal('bt-growth-consecutive-days', bc.growth_streak?.days);
        setVal('bt-growth-streak-percentile', bc.growth_streak?.percentile);
        setVal('bt-growth-top-k', bc.growth_rank?.top_n);

        // C 類 (sort)：radio，含 none 選項（F9 fix）
        const sortVal = bc.sort_sharpe?.enabled ? 'sort_sharpe'
                      : (bc.sort_industry?.enabled ? 'sort_industry' : 'none');
        setRadio('bt-pick-rule', sortVal);
        setVal('bt-sort-industry-per-industry', bc.sort_industry?.per_industry);

        // ===== 賣出條件 =====
        const sc = cfg.sell_conditions || {};

        setCheck('bt-sell-rule', 'sell_sharpe_fail', sc.sharpe_fail?.enabled);
        setVal('bt-sharpe-disqualify-periods', sc.sharpe_fail?.periods);
        setVal('bt-sharpe-disqualify-n', sc.sharpe_fail?.top_n);

        setCheck('bt-sell-rule', 'sell_growth_fail', sc.growth_fail?.enabled);
        setVal('bt-growth-disqualify-days', sc.growth_fail?.days);
        setVal('bt-growth-fail-threshold', sc.growth_fail?.threshold);        // F6 fix

        setCheck('bt-sell-rule', 'sell_not_selected', sc.not_selected?.enabled);
        setVal('bt-buy-not-selected-periods', sc.not_selected?.periods);

        setCheck('bt-sell-rule', 'sell_drawdown', sc.drawdown?.enabled);
        if (sc.drawdown?.threshold !== undefined) {
            setVal('bt-price-breakdown-pct', Math.round(sc.drawdown.threshold * 100));
        }

        setCheck('bt-sell-rule', 'sell_weakness', sc.weakness?.enabled);
        setVal('bt-relative-weakness-k', sc.weakness?.rank_k);
        setVal('bt-relative-weakness-periods', sc.weakness?.periods);

        // ===== 再平衡策略 =====
        const rs = cfg.rebalance_strategy || {};
        if (rs.type) setRadio('bt-invest-rule', `rebal_${rs.type}`);
        if (rs.batch_ratio !== undefined) setVal('bt-batch-ratio', Math.round(rs.batch_ratio * 100));
        setVal('bt-concentrate-top-k', rs.concentrate_top_k);
        setVal('bt-delayed-top-n', rs.top_n);                                 // F6 fix
        setVal('bt-delayed-sharpe-threshold', rs.sharpe_threshold);           // F6 fix
        if (rs.lead_margin !== undefined) {
            setVal('bt-lead-margin-pct', Math.round(rs.lead_margin * 100));   // F6 fix
        }

        // ===== 手續費 =====  // DA3 fix
        const fees = cfg.fees || {};
        if (fees.us?.rate !== undefined) setVal('bt-us-fee-rate', parseFloat((fees.us.rate * 100).toFixed(4)));
        if (fees.us?.min_fee !== undefined) setVal('bt-us-min-fee', fees.us.min_fee);
        if (fees.tw?.rate !== undefined) setVal('bt-tw-fee-rate', parseFloat((fees.tw.rate * 100).toFixed(4)));

        this.updateRiskIndicator();
    }

    // DT4 fix：直接解析日期字串，空值 = null（後端解釋為今日）
    _parseDateInput(id) {
        const val = document.getElementById(id)?.value;
        return val || null;
    }

    // =========================================================================
    // 事件綁定（F3 fix：live binding）
    // =========================================================================

    bindEvents() {
        const runBtn = document.getElementById('bt-run-btn');
        if (runBtn) runBtn.addEventListener('click', () => this.runBacktest());

        const resetBtn = document.getElementById('bt-reset-btn');
        if (resetBtn) resetBtn.addEventListener('click', () => this.reset());

        this._bindLiveUpdates();
    }

    /**
     * 所有表單輸入 → 即時更新 this.config
     * F3 fix：使用者每次修改任一欄位，config 立即同步
     */
    _bindLiveUpdates() {
        // 工具函式
        const onInput = (id, updater) => {
            const el = document.getElementById(id);
            if (el) el.addEventListener('input', (e) => updater(e.target.value));
        };
        const onChange = (id, updater) => {
            const el = document.getElementById(id);
            if (el) el.addEventListener('change', (e) => updater(e.target.value));
        };
        const onCheckChange = (name, value, updater) => {
            const el = document.querySelector(`input[name="${name}"][value="${value}"]`);
            if (el) el.addEventListener('change', (e) => updater(e.target.checked));
        };
        const onRadioChange = (name, updater) => {
            document.querySelectorAll(`input[name="${name}"]`).forEach(el =>
                el.addEventListener('change', (e) => { if (e.target.checked) updater(e.target.value); })
            );
        };
        const sd = () => this.serverDefaults || {};  // safe fallback ref

        // ── 基礎參數 ──────────────────────────────────────────────────────────
        onInput('bt-initial-capital', v => {
            if (this.config) this.config.initial_capital = parseInt(v) || sd().initial_capital || 1000000;
        });
        onInput('bt-amount-per-stock', v => {
            if (this.config) this.config.amount_per_stock = parseInt(v) || sd().amount_per_stock || 100000;
        });
        onInput('bt-max-positions', v => {
            if (this.config) this.config.max_positions = parseInt(v) || sd().max_positions || 10;
        });
        onRadioChange('bt-market', v => { if (this.config) this.config.market = v; });
        onRadioChange('bt-rebalance-freq', v => { if (this.config) this.config.rebalance_freq = v; });

        // 日期輸入 → 直接同步 start_date / end_date（DT4 fix）
        onChange('bt-start-date', v => {
            if (this.config) this.config.start_date = v || null;
        });
        onChange('bt-end-date', v => {
            if (this.config) this.config.end_date = v || null;
        });

        // ── 買入條件：enabled 狀態 ─────────────────────────────────────────────
        onCheckChange('bt-filter-a', 'sharpe_rank', v => {
            if (this.config) { this.config.buy_conditions.sharpe_rank.enabled = v; this.updateRiskIndicator(); }
        });
        onCheckChange('bt-filter-a', 'sharpe_threshold', v => {
            if (this.config) { this.config.buy_conditions.sharpe_threshold.enabled = v; this.updateRiskIndicator(); }
        });
        onCheckChange('bt-filter-a', 'sharpe_streak', v => {
            if (this.config) { this.config.buy_conditions.sharpe_streak.enabled = v; this.updateRiskIndicator(); }
        });
        // B 類 (growth)：真正的 radio，含 none 選項（F9 fix）
        onRadioChange('bt-growth-rule', v => {
            if (!this.config) return;
            this.config.buy_conditions.growth_streak.enabled = (v === 'growth_streak');
            this.config.buy_conditions.growth_rank.enabled = (v === 'growth_rank');
            this.updateRiskIndicator();
        });
        // C 類 (sort)：真正的 radio，含 none 選項（F9 fix）
        onRadioChange('bt-pick-rule', v => {
            if (!this.config) return;
            this.config.buy_conditions.sort_sharpe.enabled = (v === 'sort_sharpe');
            this.config.buy_conditions.sort_industry.enabled = (v === 'sort_industry');
            this.updateRiskIndicator();
        });

        // ── 買入條件：params ───────────────────────────────────────────────────
        onInput('bt-sharpe-top-n', v => {
            if (this.config) this.config.buy_conditions.sharpe_rank.top_n =
                parseInt(v) || sd().buy_conditions?.sharpe_rank?.top_n || 15;
        });
        onInput('bt-sharpe-threshold', v => {
            if (this.config) { const p = parseFloat(v);
                this.config.buy_conditions.sharpe_threshold.threshold =
                    Number.isFinite(p) ? p : (sd().buy_conditions?.sharpe_threshold?.threshold ?? 1.0); }
        });
        onInput('bt-sharpe-consecutive-days', v => {
            if (this.config) this.config.buy_conditions.sharpe_streak.days =
                parseInt(v) || sd().buy_conditions?.sharpe_streak?.days || 3;
        });
        onInput('bt-sharpe-streak-top-n', v => {                              // F5 fix
            if (this.config) this.config.buy_conditions.sharpe_streak.top_n =
                parseInt(v) || sd().buy_conditions?.sharpe_streak?.top_n || 10;
        });
        onInput('bt-growth-consecutive-days', v => {
            if (this.config) this.config.buy_conditions.growth_streak.days =
                parseInt(v) || sd().buy_conditions?.growth_streak?.days || 2;
        });
        onInput('bt-growth-streak-percentile', v => {                         // F6 fix
            if (this.config) this.config.buy_conditions.growth_streak.percentile =
                parseInt(v) || sd().buy_conditions?.growth_streak?.percentile || 30;
        });
        onInput('bt-growth-top-k', v => {
            if (this.config) this.config.buy_conditions.growth_rank.top_n =
                parseInt(v) || sd().buy_conditions?.growth_rank?.top_n || 7;
        });
        onInput('bt-sort-industry-per-industry', v => {                       // F6 fix
            if (this.config) this.config.buy_conditions.sort_industry.per_industry =
                parseInt(v) || sd().buy_conditions?.sort_industry?.per_industry || 2;
        });

        // ── 賣出條件：enabled 狀態 ─────────────────────────────────────────────
        onCheckChange('bt-sell-rule', 'sell_sharpe_fail', v => {
            if (this.config) { this.config.sell_conditions.sharpe_fail.enabled = v; this.updateRiskIndicator(); }
        });
        onCheckChange('bt-sell-rule', 'sell_growth_fail', v => {
            if (this.config) { this.config.sell_conditions.growth_fail.enabled = v; this.updateRiskIndicator(); }
        });
        onCheckChange('bt-sell-rule', 'sell_not_selected', v => {
            if (this.config) { this.config.sell_conditions.not_selected.enabled = v; this.updateRiskIndicator(); }
        });
        onCheckChange('bt-sell-rule', 'sell_drawdown', v => {
            if (this.config) { this.config.sell_conditions.drawdown.enabled = v; this.updateRiskIndicator(); }
        });
        onCheckChange('bt-sell-rule', 'sell_weakness', v => {
            if (this.config) { this.config.sell_conditions.weakness.enabled = v; this.updateRiskIndicator(); }
        });

        // ── 賣出條件：params ───────────────────────────────────────────────────
        onInput('bt-sharpe-disqualify-periods', v => {
            if (this.config) this.config.sell_conditions.sharpe_fail.periods =
                parseInt(v) || sd().sell_conditions?.sharpe_fail?.periods || 2;
        });
        onInput('bt-sharpe-disqualify-n', v => {
            if (this.config) this.config.sell_conditions.sharpe_fail.top_n =
                parseInt(v) || sd().sell_conditions?.sharpe_fail?.top_n || 15;
        });
        onInput('bt-growth-disqualify-days', v => {
            if (this.config) this.config.sell_conditions.growth_fail.days =
                parseInt(v) || sd().sell_conditions?.growth_fail?.days || 5;
        });
        onInput('bt-growth-fail-threshold', v => {                            // F6 fix
            if (this.config) { const p = parseFloat(v);
                this.config.sell_conditions.growth_fail.threshold =
                    Number.isFinite(p) ? p : (sd().sell_conditions?.growth_fail?.threshold ?? 0); }
        });
        onInput('bt-buy-not-selected-periods', v => {
            if (this.config) this.config.sell_conditions.not_selected.periods =
                parseInt(v) || sd().sell_conditions?.not_selected?.periods || 3;
        });
        onInput('bt-price-breakdown-pct', v => {
            if (this.config) this.config.sell_conditions.drawdown.threshold =
                (parseInt(v) || Math.round((sd().sell_conditions?.drawdown?.threshold || 0.40) * 100)) / 100;
        });
        onInput('bt-relative-weakness-k', v => {
            if (this.config) this.config.sell_conditions.weakness.rank_k =
                parseInt(v) || sd().sell_conditions?.weakness?.rank_k || 20;
        });
        onInput('bt-relative-weakness-periods', v => {
            if (this.config) this.config.sell_conditions.weakness.periods =
                parseInt(v) || sd().sell_conditions?.weakness?.periods || 3;
        });

        // ── 再平衡策略 ─────────────────────────────────────────────────────────
        onRadioChange('bt-invest-rule', v => {
            if (this.config) {
                this.config.rebalance_strategy.type = v.replace(/^rebal_/, '');
                this.updateRiskIndicator();
            }
        });
        onInput('bt-batch-ratio', v => {
            if (this.config) this.config.rebalance_strategy.batch_ratio =
                (parseInt(v) || Math.round((sd().rebalance_strategy?.batch_ratio || 0.20) * 100)) / 100;
        });
        onInput('bt-concentrate-top-k', v => {
            if (this.config) this.config.rebalance_strategy.concentrate_top_k =
                parseInt(v) || sd().rebalance_strategy?.concentrate_top_k || 3;
        });
        onInput('bt-delayed-top-n', v => {                                    // F6 fix
            if (this.config) this.config.rebalance_strategy.top_n =
                parseInt(v) || sd().rebalance_strategy?.top_n || 5;
        });
        onInput('bt-delayed-sharpe-threshold', v => {                         // F6 fix
            if (this.config) { const p = parseFloat(v);
                this.config.rebalance_strategy.sharpe_threshold =
                    Number.isFinite(p) ? p : (sd().rebalance_strategy?.sharpe_threshold ?? 0); }
        });
        onInput('bt-lead-margin-pct', v => {                                  // F6 fix
            if (this.config) this.config.rebalance_strategy.lead_margin =
                (parseInt(v) || Math.round((sd().rebalance_strategy?.lead_margin || 0.30) * 100)) / 100;
        });

        // ── 手續費 ─────────────────────────────────────────────────────────────  // DA3 fix
        onInput('bt-us-fee-rate', v => {
            if (this.config) {
                if (!this.config.fees) this.config.fees = {};
                if (!this.config.fees.us) this.config.fees.us = {};
                this.config.fees.us.rate =
                    (parseFloat(v) || (sd().fees?.us?.rate || 0.003) * 100) / 100;
            }
        });
        onInput('bt-us-min-fee', v => {
            if (this.config) {
                if (!this.config.fees) this.config.fees = {};
                if (!this.config.fees.us) this.config.fees.us = {};
                const p = parseFloat(v);
                this.config.fees.us.min_fee =
                    Number.isFinite(p) ? p : (sd().fees?.us?.min_fee ?? 15);
            }
        });
        onInput('bt-tw-fee-rate', v => {
            if (this.config) {
                if (!this.config.fees) this.config.fees = {};
                if (!this.config.fees.tw) this.config.fees.tw = {};
                this.config.fees.tw.rate =
                    (parseFloat(v) || (sd().fees?.tw?.rate || 0.006) * 100) / 100;
            }
        });

        // 初始化風險提示
        this.updateRiskIndicator();
    }

    // =========================================================================
    // 風險評估（從 this.config 讀取，不再查詢 DOM）
    // =========================================================================

    updateRiskIndicator() {
        const buyRisk = this.assessBuyRisk();
        const sellRisk = this.assessSellRisk();
        const rebalRisk = this.assessRebalanceRisk();

        const riskScores = { low: 1, balanced: 2, high: 3 };
        const totalScore = riskScores[buyRisk] + riskScores[sellRisk] + riskScores[rebalRisk];

        let overallRisk, description;
        if (totalScore <= 4) {
            overallRisk = 'low';
            description = '防禦型配置：熊市自動減少曝險，牛市報酬相對受限';
        } else if (totalScore <= 6) {
            overallRisk = 'balanced';
            description = '全天候配置：牛市能抓強者，熊市有適度保護';
        } else {
            overallRisk = 'high';
            description = '進取型配置：牛市報酬最大化，熊市需注意風險控制';
        }

        const riskLevel = document.getElementById('bt-risk-level');
        const riskDescription = document.getElementById('bt-risk-description');
        const buyRiskEl = document.getElementById('bt-buy-risk');
        const sellRiskEl = document.getElementById('bt-sell-risk');
        const rebalRiskEl = document.getElementById('bt-rebal-risk');

        if (riskLevel) {
            riskLevel.className = `risk-level ${overallRisk}`;
            riskLevel.textContent = overallRisk === 'high' ? '🔴 高風險' :
                                   (overallRisk === 'low' ? '🟢 低風險' : '⚖️ 平衡');
        }
        if (riskDescription) riskDescription.textContent = description;

        const riskEmoji = { low: '🟢', balanced: '⚖️', high: '🔴' };
        if (buyRiskEl) { buyRiskEl.className = `risk-item-value ${buyRisk}`; buyRiskEl.textContent = riskEmoji[buyRisk]; }
        if (sellRiskEl) { sellRiskEl.className = `risk-item-value ${sellRisk}`; sellRiskEl.textContent = riskEmoji[sellRisk]; }
        if (rebalRiskEl) { rebalRiskEl.className = `risk-item-value ${rebalRisk}`; rebalRiskEl.textContent = riskEmoji[rebalRisk]; }
    }

    assessBuyRisk() {
        if (!this.config) return 'balanced';
        const bc = this.config.buy_conditions;
        const hasStrongFilter = bc.sharpe_threshold?.enabled || bc.sharpe_streak?.enabled;
        const isAggressive = bc.growth_rank?.enabled && bc.sort_sharpe?.enabled;
        if (hasStrongFilter) return 'low';
        if (isAggressive) return 'high';
        return 'balanced';
    }

    assessSellRisk() {
        if (!this.config) return 'balanced';
        const sc = this.config.sell_conditions;
        const enabledCount = Object.values(sc).filter(c => c.enabled).length;
        if (enabledCount === 0) return 'high';
        if (enabledCount === 1) return 'balanced';
        return 'low';
    }

    assessRebalanceRisk() {
        if (!this.config) return 'balanced';
        const type = this.config.rebalance_strategy?.type || 'delayed';
        if (type === 'immediate' || type === 'concentrated') return 'high';
        if (type === 'delayed' || type === 'none') return 'low';
        return 'balanced';  // batch
    }

    // =========================================================================
    // 執行回測（F2/F3 fix：直接送出 this.config）
    // =========================================================================

    async runBacktest() {
        if (this.isRunning || !this.config) return;

        // 驗證：至少一個 A 類買入條件
        const bc = this.config.buy_conditions;
        const hasAClass = bc.sharpe_rank?.enabled || bc.sharpe_threshold?.enabled || bc.sharpe_streak?.enabled;
        if (!hasAClass) {
            alert('請至少選擇一個買入範圍條件（A 類）');
            return;
        }

        this.isRunning = true;
        const runBtn = document.getElementById('bt-run-btn');
        if (runBtn) { runBtn.textContent = '⏳ 回測中...'; runBtn.disabled = true; }
        this.clearPreviousResults();

        try {
            // 直接送出 this.config（已與後端 DEFAULT_CONFIG 結構一致）
            const apiPayload = this._deepCopy(this.config);
            console.log('📤 API 請求（this.config 快照）:', apiPayload);

            const response = await fetch('/api/backtest/run', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(apiPayload)
            });

            const apiResult = await response.json();
            if (!apiResult.success) throw new Error(apiResult.error || '回測失敗');

            console.log('📥 後端回測結果:', apiResult);

            const backendResult = apiResult.result;

            // 轉換 trades 格式
            const convertedTrades = (backendResult.trades || []).map(t => {
                let priceValue = t.price;
                if (typeof priceValue === 'string') {
                    priceValue = parseFloat(priceValue.replace(/[^0-9.-]/g, '')) || 0;
                }
                let profitValue = t.profit;
                if (typeof profitValue === 'string') {
                    profitValue = parseFloat(profitValue.replace(/[^0-9.-]/g, '')) || 0;
                }
                return {
                    ticker: t.symbol || t.ticker,
                    action: (t.type || t.action || 'buy').toLowerCase(),
                    date: t.date,
                    shares: t.shares,
                    price: priceValue,
                    pnl: profitValue,
                    reason: t.reason || '',
                    buyDate: t.buy_date || null
                };
            });

            const result = {
                success: true,
                metrics: {
                    totalReturnPct: backendResult.metrics.total_return,
                    annualizedReturn: backendResult.metrics.annualized_return,
                    tradeStats: {
                        totalTrades: backendResult.metrics.total_trades,
                        winRate: backendResult.metrics.win_rate
                    }
                },
                equityCurve: backendResult.equity_curve.map(p => ({
                    date: p.date,
                    equity: p.equity,
                    cash: p.cash || 0,
                    holdingsValue: p.holdingsValue || 0,
                    holdings: p.holdings || {}
                })),
                trades: convertedTrades
            };

            // 若後端調整了日期（非交易日對齊），僅顯示通知，不修改使用者設定
            if (backendResult.date_range) {
                const configuredStart = document.getElementById('bt-start-date')?.value || '';
                const configuredEnd = document.getElementById('bt-end-date')?.value || '';
                const actualStart = backendResult.date_range.start;
                const actualEnd = backendResult.date_range.end;
                const startMismatch = configuredStart && configuredStart !== actualStart;
                const endMismatch = configuredEnd && configuredEnd !== actualEnd;
                if (startMismatch || endMismatch) {
                    this.showDateAdjustmentNotice({
                        configuredStart, configuredEnd,
                        actualStart, actualEnd,
                        startMismatch, endMismatch
                    });
                }
            }

            const metrics = result.metrics;
            const equityCurve = result.equityCurve || [];

            const maxDrawdown = backendResult.metrics.max_drawdown;
            const strategySharpe = backendResult.metrics.sharpe_ratio;
            const sharpeVsBenchmark = strategySharpe;

            const trades = (result.trades || []).map(t => ({
                date: t.date,
                action: (t.type || t.action || 'buy').toLowerCase(),
                ticker: t.symbol || t.ticker,
                price: typeof t.price === 'number' ? t.price : parseFloat(String(t.price).replace(/[^0-9.-]/g, '')) || 0,
                shares: t.shares,
                pnl: typeof t.pnl === 'number' ? t.pnl : parseFloat(String(t.pnl).replace(/[^0-9.-]/g, '')) || 0,
                buyDate: t.buyDate || t.entry_date || t.entryDate || null
            }));

            const holdings = (backendResult.current_holdings || []).map(h => ({
                ticker: h.symbol || h.ticker,
                shares: h.shares,
                avgCost: h.avg_cost,
                currentPrice: h.current_price,
                marketValue: h.market_value,
                profit: h.pnl_pct || h.unrealized_pnl || 0,
                buyDate: h.buy_date || null,
                industry: h.industry || '',
                country: h.country || 'US',
                exchangeRate: 1
            })).sort((a, b) => b.marketValue - a.marketValue);

            const benchmarkCurve = (backendResult.benchmark_curve || []).map(p => ({
                date: p.date,
                equity: p.equity
            }));
            const benchmarkMarketName = backendResult.benchmark_name ||
                (this.config.market === 'tw' ? '台灣加權指數' :
                 this.config.market === 'us' ? 'NASDAQ' : '國際加權指數');

            this.results = {
                totalReturn: metrics.totalReturnPct || 0,
                annualReturn: metrics.annualizedReturn || 0,
                maxDrawdown,
                sharpeVsBenchmark,
                winRate: metrics.tradeStats?.winRate || 0,
                tradeCount: metrics.tradeStats?.totalTrades || 0,
                equityCurve,
                benchmarkCurve,
                benchmarkMarketName,
                trades,
                holdings
            };

            this.equityCurveData = equityCurve;
            console.log('📊 轉換後的結果:', this.results);

            this.displayResults();
            console.log('✅ 回測完成');

        } catch (error) {
            console.error('回測失敗:', error);
            alert('回測失敗: ' + error.message);
        } finally {
            this.isRunning = false;
            if (runBtn) { runBtn.textContent = '🚀 開始回測'; runBtn.disabled = false; }
        }
    }

    // =========================================================================
    // 重置
    // =========================================================================

    reset() {
        this.clearPreviousResults();
        this.results = null;
        if (this.serverDefaults) {
            this.config = this._deepCopy(this.serverDefaults);
            this.applyConfigToDOM(this.config);
        }
    }

    // =========================================================================
    // 顯示結果
    // =========================================================================

    clearPreviousResults() {
        this.hideDateAdjustmentNotice();
        ['bt-total-return', 'bt-annual-return', 'bt-max-drawdown', 'bt-sharpe-ratio', 'bt-win-rate', 'bt-trade-count'].forEach(id => {
            const el = document.getElementById(id);
            if (el) { el.textContent = '-'; el.classList.remove('positive', 'negative'); }
        });
        if (this.equityChart) { this.equityChart.destroy(); this.equityChart = null; }
        const placeholder = document.getElementById('bt-equity-placeholder');
        if (placeholder) placeholder.style.display = 'block';
        const tradeLog = document.getElementById('bt-trade-log');
        if (tradeLog) tradeLog.innerHTML = '<div class="trade-log-empty">回測中...</div>';
        const holdings = document.getElementById('bt-holdings');
        if (holdings) holdings.innerHTML = '<div class="holdings-empty">回測中...</div>';
    }

    showDateAdjustmentNotice(dateMetadata) {
        this.hideDateAdjustmentNotice();
        const notice = document.createElement('div');
        notice.id = 'bt-date-notice';
        notice.className = 'bt-date-notice';
        let html = '<div class="notice-icon">📅</div><div class="notice-content">';
        html += '<strong>日期已自動調整</strong><br>';
        if (dateMetadata.startMismatch) {
            html += `起始: <span class="old-date">${dateMetadata.configuredStart}</span> → <span class="new-date">${dateMetadata.actualStart}</span>`;
        }
        if (dateMetadata.endMismatch) {
            if (dateMetadata.startMismatch) html += '　';
            html += `結束: <span class="old-date">${dateMetadata.configuredEnd}</span> → <span class="new-date">${dateMetadata.actualEnd}</span>`;
        }
        html += '<br><small>（配置日期為非交易日，已調整為最近交易日）</small></div>';
        notice.innerHTML = html;
        const metricsSection = document.querySelector('.backtest-metrics');
        if (metricsSection) metricsSection.parentNode.insertBefore(notice, metricsSection);
    }

    hideDateAdjustmentNotice() {
        const existingNotice = document.getElementById('bt-date-notice');
        if (existingNotice) existingNotice.remove();
    }

    displayResults() {
        if (!this.results) return;
        const { totalReturn, annualReturn, maxDrawdown, sharpeVsBenchmark, winRate, tradeCount,
                equityCurve, benchmarkCurve, benchmarkMarketName, trades, holdings } = this.results;

        this.updateMetric('bt-total-return', `${totalReturn.toFixed(2)}%`, totalReturn >= 0);
        this.updateMetric('bt-annual-return', `${annualReturn.toFixed(2)}%`, annualReturn >= 0);
        this.updateMetric('bt-max-drawdown', `-${maxDrawdown.toFixed(2)}%`, false);
        this.updateMetric('bt-sharpe-ratio', `${sharpeVsBenchmark.toFixed(2)}x`, sharpeVsBenchmark >= 1);
        this.updateMetric('bt-win-rate', `${winRate.toFixed(1)}%`, winRate >= 50);
        this.updateMetric('bt-trade-count', tradeCount.toString(), true);

        this.drawEquityCurve(equityCurve, benchmarkCurve, benchmarkMarketName);
        this.displayTradeLog(trades);

        const lastPoint = equityCurve.length > 0 ? equityCurve[equityCurve.length - 1] : null;
        this.displayHoldings(holdings, lastPoint?.date || null, lastPoint?.cash || 0, lastPoint?.equity || 0);
    }

    updateMetric(id, value, isPositive = null) {
        const el = document.getElementById(id);
        if (el) {
            el.textContent = value;
            el.classList.remove('positive', 'negative');
            if (isPositive !== null) el.classList.add(isPositive ? 'positive' : 'negative');
        }
    }

    drawEquityCurve(equityCurve, benchmarkCurve = [], benchmarkMarketName = '國際加權指數') {
        const canvas = document.getElementById('bt-equity-chart');
        const placeholder = document.getElementById('bt-equity-placeholder');
        if (!canvas) return;

        this.equityCurveData = equityCurve;
        if (placeholder) placeholder.style.display = 'none';
        if (this.equityChart) this.equityChart.destroy();

        const ctx = canvas.getContext('2d');
        const labels = equityCurve.map(p => p.date);
        const cashData = equityCurve.map(p => p.cash || 0);
        const holdingsData = equityCurve.map(p => p.holdingsValue || 0);
        const totalData = equityCurve.map(p => p.equity);

        // 使用 this.config.initial_capital 而非舊的 this.settings.initial_capital
        const isProfit = totalData.length > 0 && totalData[totalData.length - 1] >= (this.config?.initial_capital || 0);

        const benchmarkMap = {};
        benchmarkCurve.forEach(p => { benchmarkMap[p.date] = p.equity; });
        const benchmarkData = labels.map(date => benchmarkMap[date] || null);

        this.selectedEquityIndex = equityCurve.length - 1;

        const datasets = [
            {
                label: '現金',
                data: cashData,
                borderColor: '#7d8590',
                backgroundColor: 'rgba(125, 133, 144, 0.3)',
                fill: true, tension: 0.1, pointRadius: 0, pointHoverRadius: 4,
                borderWidth: 1, stack: 'equity'
            },
            {
                label: '持股',
                data: holdingsData,
                borderColor: isProfit ? '#22c55e' : '#f85149',
                backgroundColor: isProfit ? 'rgba(34, 197, 94, 0.4)' : 'rgba(248, 81, 73, 0.4)',
                fill: true, tension: 0.1, pointRadius: 0, pointHoverRadius: 6,
                borderWidth: 2, stack: 'equity'
            }
        ];

        if (benchmarkCurve.length > 0) {
            datasets.push({
                label: benchmarkMarketName,
                data: benchmarkData,
                borderColor: '#58a6ff',
                backgroundColor: 'transparent',
                fill: false, tension: 0.1, pointRadius: 0, pointHoverRadius: 4,
                borderWidth: 2, borderDash: [5, 5],
                stack: 'benchmark', yAxisID: 'y'
            });
        }

        const self = this;
        this.equityChart = new Chart(ctx, {
            type: 'line',
            data: { labels, datasets },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: { mode: 'index', intersect: false },
                onClick: (event, elements) => {
                    if (elements.length > 0) {
                        const index = elements[0].index;
                        self.selectedEquityIndex = index;
                        self.updateHoldingsForDate(index);
                    }
                },
                plugins: {
                    legend: {
                        display: true, position: 'top',
                        labels: { color: '#7d8590', font: { size: 11 }, boxWidth: 20, padding: 10 }
                    },
                    tooltip: {
                        backgroundColor: '#1a1f2a', titleColor: '#e6edf3', bodyColor: '#7d8590',
                        borderColor: '#2d333b', borderWidth: 1,
                        callbacks: {
                            title: (context) => `📅 ${context[0].label}（點擊查看持有）`,
                            label: (context) => `${context.dataset.label || ''}: $${context.raw?.toLocaleString() || '-'}`,
                            footer: (context) => {
                                const idx = context[0].dataIndex;
                                const total = (cashData[idx] || 0) + (holdingsData[idx] || 0);
                                return `總資產: $${total.toLocaleString()}`;
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        display: true, grid: { color: '#21262d' },
                        ticks: { color: '#7d8590', maxTicksLimit: 6, font: { size: 10 } }
                    },
                    y: {
                        display: true, stacked: true, grid: { color: '#21262d' },
                        ticks: { color: '#7d8590', font: { size: 10 },
                                 callback: (value) => '$' + (value / 1000000).toFixed(1) + 'M' }
                    }
                }
            }
        });
    }

    updateHoldingsForDate(index) {
        if (!this.equityCurveData || index < 0 || index >= this.equityCurveData.length) return;
        const point = this.equityCurveData[index];
        const holdingsSnapshot = point.holdings || {};
        const holdingsArray = Object.entries(holdingsSnapshot).map(([ticker, h]) => ({
            ticker,
            shares: h.shares,
            avgCost: h.avgCost,
            currentPrice: h.currentPrice,
            marketValue: h.marketValue || (h.shares * h.currentPrice),
            profit: h.pnlPct || 0,
            buyDate: h.buyDate,
            industry: h.industry,
            country: h.country || 'US',
            exchangeRate: 1
        })).sort((a, b) => b.marketValue - a.marketValue);
        this.displayHoldings(holdingsArray, point.date, point.cash, point.equity);
    }

    displayTradeLog(trades) {
        const container = document.getElementById('bt-trade-log');
        if (!container) return;
        if (!trades || trades.length === 0) {
            container.innerHTML = '<div class="trade-log-empty">無交易記錄</div>';
            return;
        }
        const sortedTrades = [...trades].reverse();
        const header = `<div class="trade-log-header">共 ${trades.length} 筆交易</div>`;
        const tradeItems = sortedTrades.map(trade => {
            const isBuy = trade.action === 'buy';
            const pnlClass = trade.pnl > 0 ? 'positive' : (trade.pnl < 0 ? 'negative' : '');
            const pnlStr = trade.action === 'sell' ?
                (trade.pnl >= 0 ? '+' : '') + '$' + Math.round(trade.pnl).toLocaleString() : '-';
            let buyDateInfo = '';
            if (!isBuy && trade.buyDate) {
                buyDateInfo = `<span class="trade-log-buydate">買入: ${trade.buyDate}</span>`;
            }
            return `
                <div class="trade-log-item ${trade.action}">
                    <span class="trade-log-date">${trade.date}</span>
                    <span class="trade-log-action ${trade.action}">${isBuy ? '買入' : '賣出'}</span>
                    <span class="trade-log-stock">${trade.ticker}</span>
                    ${buyDateInfo}
                    <span class="trade-log-price">$${trade.price.toFixed(2)}</span>
                    <span class="trade-log-amount">${trade.shares} 股</span>
                    <span class="trade-log-pnl ${pnlClass}">${pnlStr}</span>
                </div>
            `;
        }).join('');
        container.innerHTML = header + tradeItems;
    }

    displayHoldings(holdings, selectedDate = null, cash = null, totalEquity = null) {
        const container = document.getElementById('bt-holdings');
        if (!container) return;
        const dateLabel = selectedDate ? `📅 ${selectedDate} 持有狀況` : '最新持有';

        if (!holdings || holdings.length === 0) {
            const cashInfo = cash !== null ? `
                <div class="holdings-summary">
                    <span class="holdings-count">無持股</span>
                    <span class="holdings-total">現金: $${Math.round(cash).toLocaleString()} TWD (100%)</span>
                </div>
            ` : '<div class="holdings-empty">無持有股票（所有部位已平倉）</div>';
            container.innerHTML = `<div class="holdings-header">${dateLabel}</div>${cashInfo}`;
            return;
        }

        const sortedHoldings = [...holdings].sort((a, b) => {
            if (!a.buyDate && !b.buyDate) return 0;
            if (!a.buyDate) return 1;
            if (!b.buyDate) return -1;
            return b.buyDate.localeCompare(a.buyDate);
        });

        const holdingsValue = sortedHoldings.reduce((sum, h) => sum + h.marketValue, 0);
        const cashAmount = cash !== null ? cash : (totalEquity !== null ? totalEquity - holdingsValue : 0);
        const equity = totalEquity !== null ? totalEquity : (holdingsValue + cashAmount);
        const cashPct = equity > 0 ? (cashAmount / equity * 100).toFixed(1) : 0;
        const holdingsPct = equity > 0 ? (holdingsValue / equity * 100).toFixed(1) : 0;

        container.innerHTML = `
            <div class="holdings-header">${dateLabel}</div>
            <div class="holdings-summary">
                <span class="holdings-count">持有 ${sortedHoldings.length} 檔</span>
                <span class="holdings-cash">現金: $${Math.round(cashAmount).toLocaleString()} TWD (${cashPct}%)</span>
                <span class="holdings-stocks-value">持股: $${Math.round(holdingsValue).toLocaleString()} TWD (${holdingsPct}%)</span>
                <span class="holdings-total">總資產: $${Math.round(equity).toLocaleString()} TWD</span>
            </div>
            ${sortedHoldings.map(h => {
                const profitClass = h.profit >= 0 ? 'positive' : 'negative';
                const profitStr = (h.profit >= 0 ? '+' : '') + h.profit.toFixed(1) + '%';
                const weight = equity > 0 ? (h.marketValue / equity * 100).toFixed(1) : 0;
                const currency = (h.country?.toUpperCase() === 'US') ? 'USD' : 'TWD';
                return `
                    <div class="holdings-item">
                        <span class="holdings-ticker">${h.ticker} <span class="holdings-industry">(${h.industry})</span></span>
                        <span class="holdings-weight">${weight}%</span>
                        <span class="holdings-shares">${h.shares.toFixed(2)} 股</span>
                        <span class="holdings-cost">成本: $${h.avgCost.toFixed(2)} ${currency}</span>
                        <span class="holdings-current">現價: $${h.currentPrice.toFixed(2)} ${currency}</span>
                        <span class="holdings-profit ${profitClass}">${profitStr}</span>
                        <span class="holdings-buy-date">買: ${h.buyDate}</span>
                    </div>
                `;
            }).join('')}
        `;
    }
}
