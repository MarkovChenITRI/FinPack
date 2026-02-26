/**
 * BacktestEngine - 交易回測前端控制器
 * 
 * 職責：
 *   - collectSettings()    收集使用者設定
 *   - runBacktest()        呼叫後端 API 執行回測
 *   - displayResults()     渲染回測結果
 * 
 * 核心計算由後端執行：
 *   - POST /api/backtest/run
 * 
 * 數據來源：
 *   - 回測結果：POST /api/backtest/run
 */

export class BacktestEngine {
    constructor() {
        // 從 UI 收集的設定（語意化鍵值）
        this.settings = {
            initial_capital: 1000000,
            start_date: null,
            end_date: null,
            rebalance_freq: 'weekly',
            market: 'us',
            amount_per_stock: 100000,
            max_positions: 10,
            buy_conditions: [],    // 語意化鍵值: sharpe_rank, growth_streak, etc.
            sell_conditions: [],   // 語意化鍵值: sell_sharpe_fail, sell_drawdown, etc.
            rebalance: null,       // 語意化鍵值: rebal_batch, rebal_immediate, etc.
            // 條件參數
            params: {}
        };
        
        // 後端回傳的結果
        this.results = null;
        
        // Chart.js 實例
        this.equityChart = null;
        
        // 狀態
        this.isRunning = false;
    }
    
    init() {
        this.bindEvents();
        this.setDefaultDates();
    }
    
    setDefaultDates() {
        const endDateInput = document.getElementById('bt-end-date');
        const startDateInput = document.getElementById('bt-start-date');
        
        const today = new Date();
        const endDate = today.toISOString().split('T')[0];
        
        // 預設起始日期: 2025-09-08
        const defaultStartDate = '2025-09-08';
        
        if (endDateInput) endDateInput.value = endDate;
        if (startDateInput) startDateInput.value = defaultStartDate;
    }
    
    bindEvents() {
        // 開始回測按鈕
        const runBtn = document.getElementById('bt-run-btn');
        if (runBtn) {
            runBtn.addEventListener('click', () => this.runBacktest());
        }
        
        // 重置按鈕
        const resetBtn = document.getElementById('bt-reset-btn');
        if (resetBtn) {
            resetBtn.addEventListener('click', () => this.reset());
        }
        
        // A 類買入條件變更時更新風險提示
        const filterAInputs = document.querySelectorAll('input[name="bt-filter-a"]');
        filterAInputs.forEach(input => {
            input.addEventListener('change', () => this.updateRiskIndicator());
        });
        
        // B 類：單選邏輯
        const growthRuleInputs = document.querySelectorAll('input[name="bt-growth-rule"]');
        growthRuleInputs.forEach(input => {
            input.addEventListener('change', (e) => {
                if (e.target.checked) {
                    growthRuleInputs.forEach(other => {
                        if (other !== e.target) other.checked = false;
                    });
                }
                this.updateRiskIndicator();
            });
        });
        
        // C 類：單選邏輯
        const pickRuleInputs = document.querySelectorAll('input[name="bt-pick-rule"]');
        pickRuleInputs.forEach(input => {
            input.addEventListener('change', (e) => {
                if (e.target.checked) {
                    pickRuleInputs.forEach(other => {
                        if (other !== e.target) other.checked = false;
                    });
                }
                this.updateRiskIndicator();
            });
        });
        
        // 賣出條件變更時更新風險評估
        const sellRuleInputs = document.querySelectorAll('input[name="bt-sell-rule"]');
        sellRuleInputs.forEach(input => {
            input.addEventListener('change', () => this.updateRiskIndicator());
        });
        
        // 再平衡條件變更時更新風險評估
        const investRuleInputs = document.querySelectorAll('input[name="bt-invest-rule"]');
        investRuleInputs.forEach(input => {
            input.addEventListener('change', () => this.updateRiskIndicator());
        });
        
        // 初始化風險提示
        this.updateRiskIndicator();
    }
    
    /**
     * 更新綜合風險評估
     */
    updateRiskIndicator() {
        // 計算買入風險
        const buyRisk = this.assessBuyRisk();
        // 計算賣出風險
        const sellRisk = this.assessSellRisk();
        // 計算再平衡風險
        const rebalRisk = this.assessRebalanceRisk();
        
        // 計算綜合分數 (低=1, 平衡=2, 高=3)
        const riskScores = { low: 1, balanced: 2, high: 3 };
        const totalScore = riskScores[buyRisk] + riskScores[sellRisk] + riskScores[rebalRisk];
        
        // 決定綜合評級
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
        
        // 更新 UI
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
        if (riskDescription) {
            riskDescription.textContent = description;
        }
        
        // 更新三維度風險指示
        const riskEmoji = { low: '🟢', balanced: '⚖️', high: '🔴' };
        if (buyRiskEl) {
            buyRiskEl.className = `risk-item-value ${buyRisk}`;
            buyRiskEl.textContent = riskEmoji[buyRisk];
        }
        if (sellRiskEl) {
            sellRiskEl.className = `risk-item-value ${sellRisk}`;
            sellRiskEl.textContent = riskEmoji[sellRisk];
        }
        if (rebalRiskEl) {
            rebalRiskEl.className = `risk-item-value ${rebalRisk}`;
            rebalRiskEl.textContent = riskEmoji[rebalRisk];
        }
    }
    
    /**
     * 評估買入條件風險
     */
    assessBuyRisk() {
        const filters = Array.from(document.querySelectorAll('input[name="bt-filter-a"]:checked')).map(el => el.value);
        const growthRule = document.querySelector('input[name="bt-growth-rule"]:checked')?.value || null;
        const pickRule = document.querySelector('input[name="bt-pick-rule"]:checked')?.value || null;
        
        // 檢查是否有強過濾
        const hasStrongFilter = filters.includes('sharpe_threshold') || filters.includes('sharpe_streak');
        // 檢查是否追漲集中
        const isAggressive = growthRule === 'growth_rank' && pickRule === 'sort_sharpe';
        
        if (hasStrongFilter) return 'low';
        if (isAggressive) return 'high';
        return 'balanced';
    }
    
    /**
     * 評估賣出條件風險
     */
    assessSellRisk() {
        const sellRules = Array.from(document.querySelectorAll('input[name="bt-sell-rule"]:checked')).map(el => el.value);
        
        if (sellRules.length === 0) return 'high';
        if (sellRules.length === 1) return 'balanced';
        return 'low';  // 2 個以上賣出條件
    }
    
    /**
     * 評估再平衡條件風險
     */
    assessRebalanceRisk() {
        const investRule = document.querySelector('input[name="bt-invest-rule"]:checked')?.value || 'rebal_batch';
        
        if (investRule === 'rebal_immediate' || investRule === 'rebal_concentrated') {
            return 'high';
        }
        if (investRule === 'rebal_delayed' || investRule === 'rebal_none') {
            return 'low';
        }
        return 'balanced';  // rebal_batch
    }
    
    /**
     * 收集 UI 設定（轉換為語意化鍵值給後端）
     */
    collectSettings() {
        // 基礎設定
        this.settings.initial_capital = parseFloat(document.getElementById('bt-initial-capital')?.value) || 1000000;
        this.settings.start_date = document.getElementById('bt-start-date')?.value;
        this.settings.end_date = document.getElementById('bt-end-date')?.value;
        this.settings.rebalance_freq = document.querySelector('input[name="bt-rebalance-freq"]:checked')?.value || 'weekly';
        this.settings.market = document.querySelector('input[name="bt-market"]:checked')?.value || 'us';
        this.settings.amount_per_stock = parseFloat(document.getElementById('bt-amount-per-stock')?.value) || 100000;
        this.settings.max_positions = parseInt(document.getElementById('bt-max-positions')?.value) || 10;
        
        // 交易成本
        this.settings.us_fee_rate = (parseFloat(document.getElementById('bt-us-fee-rate')?.value) || 0.3) / 100;
        this.settings.us_min_fee = parseFloat(document.getElementById('bt-us-min-fee')?.value) || 15;
        this.settings.tw_fee_rate = (parseFloat(document.getElementById('bt-tw-fee-rate')?.value) || 0.6) / 100;
        
        // 收集買入條件（語意化鍵值）
        const buyConditions = [];
        const params = {};
        
        // A 類：買入範圍（複選）
        const filterA = document.querySelectorAll('input[name="bt-filter-a"]:checked');
        filterA.forEach(input => {
            const key = input.value;  // sharpe_rank, sharpe_threshold, sharpe_streak
            buyConditions.push(key);
            
            // 收集對應參數
            if (key === 'sharpe_rank') {
                params.sharpe_top_n = parseInt(document.getElementById('bt-sharpe-top-n')?.value) || 15;
            } else if (key === 'sharpe_threshold') {
                params.sharpe_threshold = parseFloat(document.getElementById('bt-sharpe-threshold')?.value) || 1;
            } else if (key === 'sharpe_streak') {
                params.sharpe_consecutive_days = parseInt(document.getElementById('bt-sharpe-consecutive-days')?.value) || 3;
            }
        });
        
        // B 類：成長動能（單選）
        const growthRule = document.querySelector('input[name="bt-growth-rule"]:checked');
        if (growthRule) {
            const key = growthRule.value;  // growth_rank, growth_streak
            buyConditions.push(key);
            
            if (key === 'growth_rank') {
                params.growth_top_k = parseInt(document.getElementById('bt-growth-top-k')?.value) || 7;
            } else if (key === 'growth_streak') {
                params.growth_consecutive_days = parseInt(document.getElementById('bt-growth-consecutive-days')?.value) || 2;
            }
        }
        
        // C 類：選股方式（單選）- 只做排序，買入數量由 Engine 的 maxPositions 和資金決定
        const pickRule = document.querySelector('input[name="bt-pick-rule"]:checked');
        if (pickRule) {
            buyConditions.push(pickRule.value);  // sort_sharpe, sort_industry
        }
        
        this.settings.buy_conditions = buyConditions;
        
        // 收集賣出條件（語意化鍵值）
        const sellConditions = [];
        const sellInputs = document.querySelectorAll('input[name="bt-sell-rule"]:checked');
        sellInputs.forEach(input => {
            const key = input.value;  // sell_sharpe_fail, sell_drawdown, etc.
            sellConditions.push(key);
            
            // 收集對應參數
            if (key === 'sell_sharpe_fail') {
                params.sharpe_disqualify_periods = parseInt(document.getElementById('bt-sharpe-disqualify-periods')?.value) || 3;
                params.sharpe_disqualify_n = parseInt(document.getElementById('bt-sharpe-disqualify-n')?.value) || 15;
            } else if (key === 'sell_growth_fail') {
                params.growth_disqualify_days = parseInt(document.getElementById('bt-growth-disqualify-days')?.value) || 5;
            } else if (key === 'sell_not_selected') {
                params.buy_not_selected_periods = parseInt(document.getElementById('bt-buy-not-selected-periods')?.value) || 3;
            } else if (key === 'sell_drawdown') {
                params.price_breakdown_pct = parseFloat(document.getElementById('bt-price-breakdown-pct')?.value) || 40;
            } else if (key === 'sell_weakness') {
                params.relative_weakness_k = parseInt(document.getElementById('bt-relative-weakness-k')?.value) || 20;
                params.relative_weakness_periods = parseInt(document.getElementById('bt-relative-weakness-periods')?.value) || 3;
            }
        });
        
        this.settings.sell_conditions = sellConditions;
        
        // 收集投入方式（R 類，單選）
        const investRule = document.querySelector('input[name="bt-invest-rule"]:checked');
        if (investRule) {
            this.settings.rebalance = investRule.value;  // rebal_immediate, rebal_batch, etc.
            
            if (investRule.value === 'rebal_batch') {
                // 使用 investRatio 與 batch.js 一致
                params.investRatio = (parseInt(document.getElementById('bt-batch-ratio')?.value) || 20) / 100;
            } else if (investRule.value === 'rebal_concentrated') {
                params.concentrate_top_k = parseInt(document.getElementById('bt-concentrate-top-k')?.value) || 3;
            }
        }
        
        this.settings.params = params;
    }
    
    /**
     * 執行回測（調用後端 API）
     */
    async runBacktest() {
        if (this.isRunning) return;
        
        this.isRunning = true;
        const runBtn = document.getElementById('bt-run-btn');
        if (runBtn) {
            runBtn.textContent = '⏳ 回測中...';
            runBtn.disabled = true;
        }
        
        this.clearPreviousResults();
        
        try {
            // 收集設定
            this.collectSettings();
            
            // 驗證設定
            if (!this.settings.start_date || !this.settings.end_date) {
                alert('請選擇回測日期範圍');
                return;
            }
            
            // 驗證日期順序
            if (this.settings.start_date > this.settings.end_date) {
                alert('起始日期不能晚於結束日期');
                return;
            }
            
            if (this.settings.buy_conditions.length === 0) {
                alert('請至少選擇一個買入範圍條件（A 類）');
                return;
            }
            
            console.log('📊 準備呼叫後端回測 API...', this.settings);
            
            // ===== 呼叫後端 API 執行回測 =====
            // 轉換前端設定為後端 API 格式
            const buyConditions = {};
            this.settings.buy_conditions.forEach(key => {
                buyConditions[key] = { enabled: true };
                // 加入對應參數
                if (key === 'sharpe_rank') buyConditions[key].top_n = this.settings.params.sharpe_top_n || 15;
                if (key === 'sharpe_threshold') buyConditions[key].threshold = this.settings.params.sharpe_threshold || 1;
                if (key === 'sharpe_streak') {
                    buyConditions[key].days = this.settings.params.sharpe_consecutive_days || 3;
                    buyConditions[key].top_n = 10;
                }
                if (key === 'growth_rank') buyConditions[key].top_n = this.settings.params.growth_top_k || 7;
                if (key === 'growth_streak') {
                    buyConditions[key].days = this.settings.params.growth_consecutive_days || 2;
                    buyConditions[key].percentile = 30;
                }
            });
            
            const sellConditions = {};
            this.settings.sell_conditions.forEach(key => {
                const condKey = key.replace(/^sell_/, '');
                sellConditions[condKey] = { enabled: true };
                if (condKey === 'sharpe_fail') {
                    sellConditions[condKey].periods = this.settings.params.sharpe_disqualify_periods || 2;
                    sellConditions[condKey].top_n = this.settings.params.sharpe_disqualify_n || 15;
                }
                if (condKey === 'growth_fail') {
                    sellConditions[condKey].days = this.settings.params.growth_disqualify_days || 5;
                    sellConditions[condKey].threshold = 0;
                }
                if (condKey === 'not_selected') {
                    sellConditions[condKey].periods = this.settings.params.buy_not_selected_periods || 3;
                }
                if (condKey === 'drawdown') {
                    sellConditions[condKey].threshold = (this.settings.params.price_breakdown_pct || 40) / 100;
                }
                if (condKey === 'weakness') {
                    sellConditions[condKey].rank_k = this.settings.params.relative_weakness_k || 20;
                    sellConditions[condKey].periods = this.settings.params.relative_weakness_periods || 3;
                }
            });
            
            const rebalanceStrategy = {
                type: (this.settings.rebalance || 'rebal_delayed').replace(/^rebal_/, ''),
                batch_ratio: this.settings.params.investRatio || 0.20,
                top_n: 5,
                sharpe_threshold: 0,
                concentrate_top_k: this.settings.params.concentrate_top_k || 3,
                lead_margin: 0.30
            };
            
            const apiPayload = {
                initial_capital: this.settings.initial_capital,
                amount_per_stock: this.settings.amount_per_stock,
                max_positions: this.settings.max_positions,
                market: this.settings.market,
                start_date: this.settings.start_date,
                end_date: this.settings.end_date,
                rebalance_freq: this.settings.rebalance_freq,
                buy_conditions: buyConditions,
                sell_conditions: sellConditions,
                rebalance_strategy: rebalanceStrategy
            };
            
            console.log('📤 API 請求:', apiPayload);
            
            const response = await fetch('/api/backtest/run', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(apiPayload)
            });
            
            const apiResult = await response.json();
            
            if (!apiResult.success) {
                throw new Error(apiResult.error || '回測失敗');
            }
            
            console.log('📥 後端回測結果:', apiResult);
            
            // 轉換後端結果為前端格式
            const backendResult = apiResult.result;
            
            // 轉換 trades 格式（後端返回的 price 可能是字串如 "$123.45 USD"）
            const convertedTrades = (backendResult.trades || []).map(t => {
                // 解析 price（可能是 "$123.45 USD" 或數字）
                let priceValue = t.price;
                if (typeof priceValue === 'string') {
                    // 移除 $ 和幣別符號，只保留數字
                    priceValue = parseFloat(priceValue.replace(/[^0-9.-]/g, '')) || 0;
                }
                
                // 解析 profit（可能是 "$1,234.56 USD" 或數字）
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
            
            // 紀錄日期範圍
            if (backendResult.date_range) {
                const dateMetadata = {
                    actualStart: backendResult.date_range.start,
                    actualEnd: backendResult.date_range.end,
                    configuredStart: this.settings.start_date,
                    configuredEnd: this.settings.end_date,
                    startMismatch: backendResult.date_range.start !== this.settings.start_date,
                    endMismatch: backendResult.date_range.end !== this.settings.end_date
                };
                this.dateMetadata = dateMetadata;
                
                if (dateMetadata.startMismatch || dateMetadata.endMismatch) {
                    this.showDateAdjustmentNotice(dateMetadata);
                }
            }
            
            // 轉換結果格式（匹配 old 版本 displayResults 期望的格式）
            const metrics = result.metrics;
            const equityCurve = result.equityCurve || [];
            const lastPoint = equityCurve.length > 0 ? equityCurve[equityCurve.length - 1] : null;
            
            // 直接使用後端計算的指標
            const maxDrawdown = backendResult.metrics.max_drawdown;
            const strategySharpe = backendResult.metrics.sharpe_ratio;
            
            // 暫時使用策略 sharpe（後續可加入 benchmark 比較）
            const sharpeVsBenchmark = strategySharpe;
            
            console.log('📊 風險指標:', {
                maxDrawdown,
                strategySharpe,
                sharpeVsBenchmark
            });
            
            // 轉換 trades 格式 (後端使用 symbol/type，前端使用 ticker/action)
            // price 已在前面 convertedTrades 轉換為數字
            const trades = (result.trades || []).map(t => ({
                date: t.date,
                action: (t.type || t.action || 'buy').toLowerCase(),
                ticker: t.symbol || t.ticker,
                price: typeof t.price === 'number' ? t.price : parseFloat(String(t.price).replace(/[^0-9.-]/g, '')) || 0,
                shares: t.shares,
                pnl: typeof t.pnl === 'number' ? t.pnl : parseFloat(String(t.pnl).replace(/[^0-9.-]/g, '')) || 0,
                buyDate: t.buyDate || t.entry_date || t.entryDate || null
            }));
            
            // 使用後端返回的當前持倉 (後端使用 symbol，前端使用 ticker)
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
            
            // 取得後端計算的 benchmark 曲線
            const benchmarkCurve = (backendResult.benchmark_curve || []).map(p => ({
                date: p.date,
                equity: p.equity
            }));
            // fallback: 與前端 K 線圖一致
            const benchmarkMarketName = backendResult.benchmark_name || 
                (this.settings.market === 'tw' ? '台灣加權指數' : 
                 this.settings.market === 'us' ? 'NASDAQ' : '國際加權指數');
            
            this.results = {
                totalReturn: metrics.totalReturnPct || 0,
                annualReturn: metrics.annualizedReturn || 0,
                maxDrawdown: maxDrawdown,
                sharpeVsBenchmark: sharpeVsBenchmark,
                winRate: metrics.tradeStats?.winRate || 0,
                tradeCount: metrics.tradeStats?.totalTrades || 0,
                equityCurve,
                benchmarkCurve,
                benchmarkMarketName,
                trades,
                holdings
            };
            
            // 保存 equityCurve 供點擊查看每日持有
            this.equityCurveData = equityCurve;
            
            console.log('📊 轉換後的結果:', this.results);
            
            // 顯示結果
            this.displayResults();
            
            console.log('✅ 回測完成');
            
        } catch (error) {
            console.error('回測失敗:', error);
            alert('回測失敗: ' + error.message);
        } finally {
            this.isRunning = false;
            if (runBtn) {
                runBtn.textContent = '🚀 開始回測';
                runBtn.disabled = false;
            }
        }
    }
    
    /**
     * 清除上次回測結果
     */
    clearPreviousResults() {
        // 清除日期調整通知
        this.hideDateAdjustmentNotice();
        
        // 重置績效指標
        ['bt-total-return', 'bt-annual-return', 'bt-max-drawdown', 'bt-sharpe-ratio', 'bt-win-rate', 'bt-trade-count'].forEach(id => {
            const el = document.getElementById(id);
            if (el) {
                el.textContent = '-';
                el.classList.remove('positive', 'negative');
            }
        });
        
        // 清除權益曲線
        if (this.equityChart) {
            this.equityChart.destroy();
            this.equityChart = null;
        }
        
        const placeholder = document.getElementById('bt-equity-placeholder');
        if (placeholder) placeholder.style.display = 'block';
        
        // 清除交易記錄
        const tradeLog = document.getElementById('bt-trade-log');
        if (tradeLog) {
            tradeLog.innerHTML = '<div class="trade-log-empty">回測中...</div>';
        }
        
        // 清除持有資訊
        const holdings = document.getElementById('bt-holdings');
        if (holdings) {
            holdings.innerHTML = '<div class="holdings-empty">回測中...</div>';
        }
    }
    
    /**
     * 顯示日期調整通知
     */
    showDateAdjustmentNotice(dateMetadata) {
        // 移除已有的通知
        this.hideDateAdjustmentNotice();
        
        // 建立通知元素
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
        
        // 插入到績效指標區域上方
        const metricsSection = document.querySelector('.backtest-metrics');
        if (metricsSection) {
            metricsSection.parentNode.insertBefore(notice, metricsSection);
        }
    }
    
    /**
     * 隱藏日期調整通知
     */
    hideDateAdjustmentNotice() {
        const existingNotice = document.getElementById('bt-date-notice');
        if (existingNotice) {
            existingNotice.remove();
        }
    }
    
    /**
     * 顯示回測結果
     */
    displayResults() {
        if (!this.results) return;
        
        const { totalReturn, annualReturn, maxDrawdown, sharpeVsBenchmark, winRate, tradeCount, equityCurve, benchmarkCurve, benchmarkMarketName, trades, holdings } = this.results;
        
        // 更新績效指標
        this.updateMetric('bt-total-return', `${totalReturn.toFixed(2)}%`, totalReturn >= 0);
        this.updateMetric('bt-annual-return', `${annualReturn.toFixed(2)}%`, annualReturn >= 0);
        this.updateMetric('bt-max-drawdown', `-${maxDrawdown.toFixed(2)}%`, false);
        // 夏普比率改為相對 benchmark 的比值：>1 優於市場，<1 不如市場
        this.updateMetric('bt-sharpe-ratio', `${sharpeVsBenchmark.toFixed(2)}x`, sharpeVsBenchmark >= 1);
        this.updateMetric('bt-win-rate', `${winRate.toFixed(1)}%`, winRate >= 50);
        this.updateMetric('bt-trade-count', tradeCount.toString(), true);
        
        // 繪製權益曲線（含 benchmark）- 會設置 equityCurveData 供點擊使用
        this.drawEquityCurve(equityCurve, benchmarkCurve, benchmarkMarketName);
        
        // 顯示交易記錄
        this.displayTradeLog(trades);
        
        // 顯示最新持有資訊（預設顯示最後一天），包含現金和總資產
        const lastPoint = equityCurve.length > 0 ? equityCurve[equityCurve.length - 1] : null;
        const lastDate = lastPoint?.date || null;
        const lastCash = lastPoint?.cash || 0;
        const lastEquity = lastPoint?.equity || 0;
        this.displayHoldings(holdings, lastDate, lastCash, lastEquity);
    }
    
    updateMetric(id, value, isPositive = null) {
        const el = document.getElementById(id);
        if (el) {
            el.textContent = value;
            el.classList.remove('positive', 'negative');
            if (isPositive !== null) {
                el.classList.add(isPositive ? 'positive' : 'negative');
            }
        }
    }
    
    /**
     * 繪製權益曲線
     */
    drawEquityCurve(equityCurve, benchmarkCurve = [], benchmarkMarketName = '國際加權指數') {
        const canvas = document.getElementById('bt-equity-chart');
        const placeholder = document.getElementById('bt-equity-placeholder');
        
        if (!canvas) return;
        
        // 保存 equityCurve 以供點擊時查詢每日持有狀況
        this.equityCurveData = equityCurve;
        
        // 隱藏 placeholder
        if (placeholder) placeholder.style.display = 'none';
        
        // 銷毀舊圖表
        if (this.equityChart) {
            this.equityChart.destroy();
        }
        
        const ctx = canvas.getContext('2d');
        
        // 準備資料
        const labels = equityCurve.map(p => p.date);
        const cashData = equityCurve.map(p => p.cash || 0);
        const holdingsData = equityCurve.map(p => p.holdingsValue || 0);
        const totalData = equityCurve.map(p => p.equity);
        
        // 判斷是否獲利
        const isProfit = totalData.length > 0 && totalData[totalData.length - 1] >= this.settings.initial_capital;
        
        // 準備 benchmark 資料（對齊日期）
        const benchmarkMap = {};
        benchmarkCurve.forEach(p => { benchmarkMap[p.date] = p.equity; });
        const benchmarkData = labels.map(date => benchmarkMap[date] || null);
        
        // 記錄選中的日期索引（預設為最後一天）
        this.selectedEquityIndex = equityCurve.length - 1;
        
        // 建立 datasets - 使用堆疊面積圖區分現金和持股
        const datasets = [
            {
                label: '現金',
                data: cashData,
                borderColor: '#7d8590',
                backgroundColor: 'rgba(125, 133, 144, 0.3)',
                fill: true,
                tension: 0.1,
                pointRadius: 0,
                pointHoverRadius: 4,
                borderWidth: 1,
                stack: 'equity'
            },
            {
                label: '持股',
                data: holdingsData,
                borderColor: isProfit ? '#22c55e' : '#f85149',
                backgroundColor: isProfit ? 'rgba(34, 197, 94, 0.4)' : 'rgba(248, 81, 73, 0.4)',
                fill: true,
                tension: 0.1,
                pointRadius: 0,
                pointHoverRadius: 6,
                borderWidth: 2,
                stack: 'equity'
            }
        ];
        
        // 如果有 benchmark 資料，加入第二條線（不堆疊）
        if (benchmarkCurve.length > 0) {
            datasets.push({
                label: benchmarkMarketName,
                data: benchmarkData,
                borderColor: '#58a6ff',
                backgroundColor: 'transparent',
                fill: false,
                tension: 0.1,
                pointRadius: 0,
                pointHoverRadius: 4,
                borderWidth: 2,
                borderDash: [5, 5],
                stack: 'benchmark',  // 獨立 stack，不與現金/持股堆疊
                yAxisID: 'y'  // 使用相同 Y 軸但不堆疊
            });
        }
        
        // 保存 this 引用供事件處理器使用
        const self = this;
        
        this.equityChart = new Chart(ctx, {
            type: 'line',
            data: { labels, datasets },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: {
                    mode: 'index',
                    intersect: false
                },
                onClick: (event, elements) => {
                    if (elements.length > 0) {
                        const index = elements[0].index;
                        self.selectedEquityIndex = index;
                        self.updateHoldingsForDate(index);
                    }
                },
                plugins: {
                    legend: { 
                        display: true,
                        position: 'top',
                        labels: {
                            color: '#7d8590',
                            font: { size: 11 },
                            boxWidth: 20,
                            padding: 10
                        }
                    },
                    tooltip: {
                        backgroundColor: '#1a1f2a',
                        titleColor: '#e6edf3',
                        bodyColor: '#7d8590',
                        borderColor: '#2d333b',
                        borderWidth: 1,
                        callbacks: {
                            title: (context) => {
                                return `📅 ${context[0].label}（點擊查看持有）`;
                            },
                            label: (context) => {
                                const label = context.dataset.label || '';
                                return `${label}: $${context.raw?.toLocaleString() || '-'}`;
                            },
                            footer: (context) => {
                                // 計算總資產
                                const idx = context[0].dataIndex;
                                const total = (cashData[idx] || 0) + (holdingsData[idx] || 0);
                                return `總資產: $${total.toLocaleString()}`;
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        display: true,
                        grid: { color: '#21262d' },
                        ticks: { 
                            color: '#7d8590',
                            maxTicksLimit: 6,
                            font: { size: 10 }
                        }
                    },
                    y: {
                        display: true,
                        stacked: true,  // 只對 stack: 'equity' 的資料堆疊
                        grid: { color: '#21262d' },
                        ticks: { 
                            color: '#7d8590',
                            font: { size: 10 },
                            callback: (value) => '$' + (value / 1000000).toFixed(1) + 'M'
                        }
                    }
                }
            }
        });
    }
    
    /**
     * 根據選中的日期更新持有狀況顯示
     */
    updateHoldingsForDate(index) {
        if (!this.equityCurveData || index < 0 || index >= this.equityCurveData.length) return;
        
        const point = this.equityCurveData[index];
        const holdingsSnapshot = point.holdings || {};
        
        // 轉換為 displayHoldings 需要的格式
        // 後端欄位: shares, avgCost, currentPrice, marketValue, pnlPct, buyDate, industry, country
        const holdingsArray = Object.entries(holdingsSnapshot).map(([ticker, h]) => ({
            ticker,
            shares: h.shares,
            avgCost: h.avgCost,
            currentPrice: h.currentPrice,
            marketValue: h.marketValue || (h.shares * h.currentPrice),
            profit: h.pnlPct || 0,  // 後端使用 pnlPct
            buyDate: h.buyDate,
            industry: h.industry,
            country: h.country || 'US',
            exchangeRate: 1
        })).sort((a, b) => b.marketValue - a.marketValue);
        
        // 傳遞現金和總資產資訊
        this.displayHoldings(holdingsArray, point.date, point.cash, point.equity);
    }
    
    /**
     * 顯示交易記錄
     */
    displayTradeLog(trades) {
        const container = document.getElementById('bt-trade-log');
        if (!container) return;
        
        if (!trades || trades.length === 0) {
            container.innerHTML = '<div class="trade-log-empty">無交易記錄</div>';
            return;
        }
        
        // 顯示全部交易，按時間倒序（最新在前）
        const sortedTrades = [...trades].reverse();
        
        // 加入交易總筆數資訊
        const header = `<div class="trade-log-header">共 ${trades.length} 筆交易</div>`;
        
        const tradeItems = sortedTrades.map(trade => {
            const isBuy = trade.action === 'buy';
            const pnlClass = trade.pnl > 0 ? 'positive' : (trade.pnl < 0 ? 'negative' : '');
            const pnlStr = trade.action === 'sell' ? 
                (trade.pnl >= 0 ? '+' : '') + '$' + Math.round(trade.pnl).toLocaleString() : '-';
            
            // 賣出時顯示買入日期
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
    
    /**
     * 顯示持有狀況
     */
    displayHoldings(holdings, selectedDate = null, cash = null, totalEquity = null) {
        const container = document.getElementById('bt-holdings');
        if (!container) return;
        
        // 顯示日期標題
        const dateLabel = selectedDate ? `📅 ${selectedDate} 持有狀況` : '最新持有';
        
        if (!holdings || holdings.length === 0) {
            // 即使沒有持股，也要顯示現金
            const cashInfo = cash !== null ? `
                <div class="holdings-summary">
                    <span class="holdings-count">無持股</span>
                    <span class="holdings-total">現金: $${Math.round(cash).toLocaleString()} TWD (100%)</span>
                </div>
            ` : '<div class="holdings-empty">無持有股票（所有部位已平倉）</div>';
            
            container.innerHTML = `
                <div class="holdings-header">${dateLabel}</div>
                ${cashInfo}
            `;
            return;
        }
        
        // 按買進日期降序排列（最新買進的在最上面）
        const sortedHoldings = [...holdings].sort((a, b) => {
            if (!a.buyDate && !b.buyDate) return 0;
            if (!a.buyDate) return 1;
            if (!b.buyDate) return -1;
            return b.buyDate.localeCompare(a.buyDate);
        });
        
        // 計算持股市值
        const holdingsValue = sortedHoldings.reduce((sum, h) => sum + h.marketValue, 0);
        
        // 如果有傳入 cash，使用它；否則從 totalEquity 反推
        const cashAmount = cash !== null ? cash : (totalEquity !== null ? totalEquity - holdingsValue : 0);
        const equity = totalEquity !== null ? totalEquity : (holdingsValue + cashAmount);
        
        // 計算比例
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
                // 計算單檔持股佔總資產比例
                const weight = equity > 0 ? (h.marketValue / equity * 100).toFixed(1) : 0;
                // 幣別標示
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
    
    /**
     * 重置回測（與 index.html 預設 checked 一致）
     */
    reset() {
        this.clearPreviousResults();
        this.results = null;
        this.setDefaultDates();
        
        // 重置表單
        document.getElementById('bt-initial-capital').value = '1000000';
        
        // 重置買入條件 - A類（sharpe_rank, sharpe_threshold 勾選）
        document.querySelectorAll('input[name="bt-filter-a"]').forEach(input => {
            input.checked = ['sharpe_rank', 'sharpe_threshold'].includes(input.value);
        });
        
        // 重置買入條件 - B類（growth_streak 勾選）
        document.querySelectorAll('input[name="bt-growth-rule"]').forEach(input => {
            input.checked = input.value === 'growth_streak';
        });
        
        // 重置買入條件 - C類（sort_sharpe 勾選）
        document.querySelectorAll('input[name="bt-pick-rule"]').forEach(input => {
            input.checked = input.value === 'sort_sharpe';
        });
        
        // 重置賣出條件（sharpe_fail, drawdown 勾選）
        document.querySelectorAll('input[name="bt-sell-rule"]').forEach(input => {
            input.checked = ['sell_sharpe_fail', 'sell_drawdown'].includes(input.value);
        });
        
        // 重置投入方式（delayed 勾選）
        document.querySelectorAll('input[name="bt-invest-rule"]').forEach(input => {
            input.checked = input.value === 'rebal_delayed';
        });
        
        this.updateRiskIndicator();
    }
}
