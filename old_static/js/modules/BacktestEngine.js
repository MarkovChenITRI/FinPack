/**
 * BacktestEngine - 交易回測引擎
 * 
 * 職責：
 *   - runBacktest()      執行回測（購賣模擬、計算墠值曲線）
 *   - selectStocksByRanking()  依排名選股
 *   - calculateReturns()       計算報酬率與績效指標
 * 
 * 數據來源：
 *   - 價格: /api/backtest/prices → stock_cache.aligned_data
 *   - 排名: industryDataCache.getFullRanking() → sharpe_matrix/slope_matrix
 */
import { industryDataCache } from './IndustryDataCache.js';

export class BacktestEngine {
    constructor() {
        this.settings = {
            initialCapital: 1000000,
            startDate: null,
            endDate: null,
            rebalanceFreq: 'weekly',  // daily, weekly, monthly
            market: 'global',  // 'global', 'us', 'tw'
            // 買入規則（多選組合）
            buyRules: {
                useSharpe: true,     // 使用 Sharpe 排名
                useGrowth: false,    // 使用 Growth 排名
                useIndustry: false,  // 分散產業輪選
                useRandom: false     // 隨機選取
            },
            topN: 5,
            amountPerStock: 100000,
            maxPositions: 10,
            // 賣出規則（多選組合）
            sellRules: {
                useSharpeDisqualify: true,   // Sharpe 長期失格
                useGrowthDisqualify: false,  // Growth 長期失格
                useBuyNotSelected: false,    // BUY 多期未入選
                usePriceBreakdown: true,     // 價格破底
                useRelativeWeakness: false   // 相對強度停滯
            },
            sellParams: {
                // 賣出參數
                sharpeDisqualifyPeriods: 3,  // 連續 M 期
                sharpeDisqualifyN: 15,       // 掉出 Top-N
                growthDisqualifyDays: 5,     // 最近 X 天
                buyNotSelectedPeriods: 3,    // 連續 M 期
                priceBreakdownPct: 40,       // 回撤百分比
                relativeWeaknessK: 20,       // 排名 > K
                relativeWeaknessPeriods: 3   // 連續 M 期
            },
            // 手續費結構
            fees: {
                us: { rate: 0.003, minFee: 15 },   // 美股複委託：0.3%，最低 15 USD
                tw: { rate: 0.006, minFee: 0 }     // 台股：0.6%（含證交稅），無最低
            }
        };
        
        this.results = null;
        this.priceData = null;
        this.equityChart = null;
        this.equityCurveData = null;
        this.selectedEquityIndex = null;
        this.isRunning = false;
    }
    
    init() {
        this.bindEvents();
        this.setDefaultDates();
    }
    
    setDefaultDates() {
        // 設定預設日期（使用 industryDataCache 的日期範圍）
        const endDateInput = document.getElementById('bt-end-date');
        const startDateInput = document.getElementById('bt-start-date');
        
        // 預設結束日期為今天
        const today = new Date();
        const endDate = today.toISOString().split('T')[0];
        
        // 預設開始日期為 6 個月前
        const startDate = new Date(today);
        startDate.setMonth(startDate.getMonth() - 6);
        
        if (endDateInput) endDateInput.value = endDate;
        if (startDateInput) startDateInput.value = startDate.toISOString().split('T')[0];
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
        
        // B 類：單選邏輯（checkbox 但最多選一個）
        const growthRuleInputs = document.querySelectorAll('input[name="bt-growth-rule"]');
        growthRuleInputs.forEach(input => {
            input.addEventListener('change', (e) => {
                if (e.target.checked) {
                    // 取消同類其他選擇
                    growthRuleInputs.forEach(other => {
                        if (other !== e.target) other.checked = false;
                    });
                }
                this.updateRiskIndicator();
            });
        });
        
        // C 類：單選邏輯（checkbox 但最多選一個）
        const pickRuleInputs = document.querySelectorAll('input[name="bt-pick-rule"]');
        pickRuleInputs.forEach(input => {
            input.addEventListener('change', (e) => {
                if (e.target.checked) {
                    // 取消同類其他選擇
                    pickRuleInputs.forEach(other => {
                        if (other !== e.target) other.checked = false;
                    });
                }
                this.updateRiskIndicator();
            });
        });
        
        // 初始化風險提示
        this.updateRiskIndicator();
    }
    
    /**
     * 更新風險提示
     * 根據 A、B、C 類選擇計算風險等級
     */
    updateRiskIndicator() {
        // 收集當前選擇
        const filterA = Array.from(document.querySelectorAll('input[name="bt-filter-a"]:checked')).map(el => el.value);
        const growthRule = document.querySelector('input[name="bt-growth-rule"]:checked')?.value || null;
        const pickRule = document.querySelector('input[name="bt-pick-rule"]:checked')?.value || null;
        
        const riskLevel = document.getElementById('bt-risk-level');
        const riskDescription = document.getElementById('bt-risk-description');
        
        if (!riskLevel || !riskDescription) return;
        
        // 計算風險等級
        let risk = 'balanced';
        let description = '';
        
        // 檢查是否有強過濾條件 (sharpe_threshold 或 sharpe_streak)
        const hasStrongFilter = filterA.includes('sharpe-threshold') || filterA.includes('sharpe-consecutive');
        
        // 檢查 B 類選擇（可能為空）
        const useGrowthTop = growthRule === 'growth-top';  // growth_rank 風險較高
        const useGrowthConsecutive = growthRule === 'growth-consecutive';  // growth_streak 較安全
        const noGrowthRule = growthRule === null;  // 未選擇 B 類
        
        // 檢查 C 類選擇（可能為空）
        const useIndustryDiversify = pickRule === 'by-industry-sharpe';  // sort_industry 較安全
        const useSharpeOnly = pickRule === 'by-sharpe';  // sort_sharpe
        const noPickRule = pickRule === null;  // 未選擇 C 類
        
        // 風險評估邏輯
        if (filterA.length === 0) {
            // 未選擇任何 A 類條件
            risk = 'high';
            description = '⚠️ 請至少選擇一個買入範圍條件（A 類）';
        } else if (noGrowthRule && noPickRule) {
            // 只有 A 類，無 B/C
            if (hasStrongFilter) {
                risk = 'low';
                description = '🛡️ 僅使用 A 類強過濾：簡單保守策略，熊市自動停買';
            } else {
                risk = 'balanced';
                description = '⚖️ 僅使用 A 類基礎過濾：建議配合 B/C 條件提升策略效果';
            }
        } else if (hasStrongFilter && useGrowthConsecutive && useIndustryDiversify) {
            // 最安全組合：sharpe_threshold/sharpe_streak + growth_streak + sort_industry
            risk = 'low';
            description = '🛡️ 熊市最安全組合：強過濾 + 連續動能驗證 + 產業分散 → 熊市近乎完美停買';
        } else if (!hasStrongFilter && useGrowthTop && useSharpeOnly) {
            // 最高風險組合：sharpe_rank + growth_rank + sort_sharpe
            risk = 'high';
            description = '⚠️ 牛市最佳但熊市高風險：growth_rank 在熊市會追反彈，建議配合強過濾條件';
        } else if (!hasStrongFilter && (useGrowthConsecutive || noGrowthRule) && (useIndustryDiversify || noPickRule)) {
            // 平衡組合
            risk = 'balanced';
            description = '⚖️ 全市場最平衡：牛市能抓長線強者，熊市自動保護，最適合自動化';
        } else if (hasStrongFilter) {
            // 有強過濾的組合
            risk = 'low';
            description = '🛡️ 保守策略：強過濾條件在熊市會自動停買，降低風險';
        } else if (useGrowthConsecutive) {
            // 使用 growth_streak 的組合
            risk = 'balanced';
            description = '⚖️ 穩健策略：連續動能驗證過濾假突破，熊市自動減少買入';
        } else if (useIndustryDiversify) {
            // 使用 sort_industry 的組合
            risk = 'balanced';
            description = '⚖️ 分散策略：產業分散降低單一產業崩盤風險';
        } else if (useGrowthTop) {
            // 使用 growth_rank 的組合
            risk = 'high';
            description = '⚠️ 進取策略：growth_rank 追求短期動能，熊市可能追到假反彈，建議啟用 sharpe_threshold/sharpe_streak';
        } else {
            // 其他組合
            risk = 'balanced';
            description = '⚖️ 中性策略：建議根據市場狀況調整條件組合';
        }
        
        // 更新 UI
        riskLevel.className = `risk-level ${risk}`;
        riskLevel.textContent = risk === 'high' ? '🔴 高風險' : (risk === 'low' ? '🟢 低風險' : '⚖️ 平衡');
        riskDescription.textContent = description;
    }
    
    collectSettings() {
        this.settings.initialCapital = parseFloat(document.getElementById('bt-initial-capital')?.value) || 1000000;
        this.settings.startDate = document.getElementById('bt-start-date')?.value;
        this.settings.endDate = document.getElementById('bt-end-date')?.value;
        
        // 再平衡頻率（單選）
        const rebalanceFreq = document.querySelector('input[name="bt-rebalance-freq"]:checked')?.value || 'weekly';
        this.settings.rebalanceFreq = rebalanceFreq;
        
        // 投入方式 (R 類，單選)
        const investRule = document.querySelector('input[name="bt-invest-rule"]:checked')?.value || 'batch';
        this.settings.investRule = {
            type: investRule,
            batchRatio: (parseInt(document.getElementById('bt-batch-ratio')?.value) || 20) / 100,
            concentrateTopK: parseInt(document.getElementById('bt-concentrate-top-k')?.value) || 3
        };
        
        // 市場選擇（單選）
        const selectedMarket = document.querySelector('input[name="bt-market"]:checked');
        this.settings.market = selectedMarket?.value || 'global';
        
        // ===== 新版買入條件 (A/B/C 類) =====
        
        // A 類：買入範圍 (Universe Filter, 複選)
        const filterA = Array.from(document.querySelectorAll('input[name="bt-filter-a"]:checked')).map(el => el.value);
        this.settings.filterA = {
            useSharpeTop: filterA.includes('sharpe-top'),
            sharpeTopN: parseInt(document.getElementById('bt-sharpe-top-n')?.value) || 15,
            useSharpeThreshold: filterA.includes('sharpe-threshold'),
            sharpeThreshold: parseFloat(document.getElementById('bt-sharpe-threshold')?.value) || 1,
            useSharpeConsecutive: filterA.includes('sharpe-consecutive'),
            sharpeConsecutiveDays: parseInt(document.getElementById('bt-sharpe-consecutive-days')?.value) || 3
        };
        
        // B 類：成長動能 (Growth Ranking, 可選單選)
        const growthRule = document.querySelector('input[name="bt-growth-rule"]:checked')?.value || null;
        this.settings.growthRule = {
            type: growthRule,
            growthTopK: parseInt(document.getElementById('bt-growth-top-k')?.value) || 7,
            growthConsecutiveDays: parseInt(document.getElementById('bt-growth-consecutive-days')?.value) || 2
        };
        
        // C 類：選股方式 (Pick Rule, 可選單選)
        const pickRule = document.querySelector('input[name="bt-pick-rule"]:checked')?.value || null;
        this.settings.pickRule = pickRule;
        
        // 向後相容：轉換為舊的 buyRules 格式
        this.settings.buyRules = {
            useSharpe: this.settings.filterA.useSharpeTop,
            useGrowth: growthRule !== null,  // 有選擇 B 類才用 Growth
            useIndustry: this.settings.pickRule === 'by-industry-sharpe',
            useRandom: false
        };
        
        this.settings.topN = parseInt(document.getElementById('bt-top-n')?.value) || 5;
        this.settings.amountPerStock = parseFloat(document.getElementById('bt-amount-per-stock')?.value) || 100000;
        this.settings.maxPositions = parseInt(document.getElementById('bt-max-positions')?.value) || 10;
        
        // 交易成本設定
        this.settings.fees = {
            us: {
                rate: (parseFloat(document.getElementById('bt-us-fee-rate')?.value) || 0.3) / 100,
                minFee: parseFloat(document.getElementById('bt-us-min-fee')?.value) || 15
            },
            tw: {
                rate: (parseFloat(document.getElementById('bt-tw-fee-rate')?.value) || 0.6) / 100,
                minFee: 0  // 台股無最低手續費
            }
        };
        
        // 賣出規則 (sell_sharpe_fail/sell_drawdown 等，多選組合)
        const checkedSellRules = document.querySelectorAll('input[name="bt-sell-rule"]:checked');
        const sellRuleValues = Array.from(checkedSellRules).map(el => el.value);
        
        this.settings.sellRules = {
            useSharpeDisqualify: sellRuleValues.includes('sharpe-disqualify'),
            useGrowthDisqualify: sellRuleValues.includes('growth-disqualify'),
            useBuyNotSelected: sellRuleValues.includes('buy-not-selected'),
            usePriceBreakdown: sellRuleValues.includes('price-breakdown'),
            useRelativeWeakness: sellRuleValues.includes('relative-weakness')
        };
        
        // 不再設定預設賣出規則，讓用戶完全控制
        // 如果沒有勾選任何賣出規則，系統將執行「永不賣出」模式
        
        // 賣出參數
        this.settings.sellParams = {
            // sell_sharpe_fail 參數
            sharpeDisqualifyPeriods: parseInt(document.getElementById('bt-sharpe-disqualify-periods')?.value) || 3,
            sharpeDisqualifyN: parseInt(document.getElementById('bt-sharpe-disqualify-n')?.value) || 15,
            // sell_growth_fail 參數
            growthDisqualifyDays: parseInt(document.getElementById('bt-growth-disqualify-days')?.value) || 5,
            // sell_not_selected 參數
            buyNotSelectedPeriods: parseInt(document.getElementById('bt-buy-not-selected-periods')?.value) || 3,
            // sell_drawdown 參數
            priceBreakdownPct: parseFloat(document.getElementById('bt-price-breakdown-pct')?.value) || 40,
            // sell_weakness 參數
            relativeWeaknessK: parseInt(document.getElementById('bt-relative-weakness-k')?.value) || 20,
            relativeWeaknessPeriods: parseInt(document.getElementById('bt-relative-weakness-periods')?.value) || 3
        };
    }
    
    async runBacktest() {
        if (this.isRunning) return;
        
        this.isRunning = true;
        const runBtn = document.getElementById('bt-run-btn');
        if (runBtn) {
            runBtn.textContent = '⏳ 回測中...';
            runBtn.disabled = true;
        }
        
        // 在開始新回測前，清空舊的結果
        this.clearPreviousResults();
        
        try {
            // 收集設定
            this.collectSettings();
            
            // 驗證設定
            if (!this.settings.startDate || !this.settings.endDate) {
                alert('請選擇回測日期範圍');
                return;
            }
            
            if (!this.settings.market) {
                alert('請選擇一個市場');
                return;
            }
            
            // 買入規則驗證（新版：A 類至少需要一個）
            if (!this.settings.filterA.useSharpeTop && 
                !this.settings.filterA.useSharpeThreshold && 
                !this.settings.filterA.useSharpeConsecutive) {
                alert('請至少選擇一個買入範圍條件（A 類）');
                return;
            }
            
            // 賣出規則已在 collectSettings 中設定預設值，無需額外驗證
            
            // 載入價格資料
            console.log('📊 載入回測價格資料...');
            await this.loadPriceData();
            
            // 執行回測
            console.log('🚀 開始回測模擬...');
            this.results = this.simulate();
            
            // 顯示結果
            this.displayResults();
            
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
    
    async loadPriceData() {
        const url = `/api/backtest/prices?start_date=${this.settings.startDate}&end_date=${this.settings.endDate}`;
        const response = await fetch(url);
        
        if (!response.ok) {
            throw new Error('無法載入價格資料');
        }
        
        this.priceData = await response.json();
        console.log(`📈 載入 ${this.priceData.dates?.length || 0} 個交易日，${this.priceData.tickers?.length || 0} 檔股票`);
    }
    
    simulate() {
        const { dates, prices, stockInfo, tickers } = this.priceData;
        
        // 初始化
        let cash = this.settings.initialCapital;
        const holdings = {};  // { ticker: { shares, avgCost, buyDate, peakPrice, rankingDropCount } }
        const trades = [];
        const equityCurve = [];
        
        // 排名快取：避免同一天重複計算排名
        const rankingCache = new Map();
        
        // 取得擴展排名（用於判斷是否在 Top N 內）
        const getExtendedRanking = (date, validTickers) => {
            const cacheKey = date;
            if (rankingCache.has(cacheKey)) {
                return rankingCache.get(cacheKey);
            }
            
            const { useSharpe, useGrowth } = this.settings.buyRules;
            let candidates;
            
            if (useSharpe && useGrowth) {
                candidates = this.getCombinedRanking(date, validTickers);
            } else if (useSharpe) {
                candidates = this.getRankingByMetric(date, validTickers, 'sharpe');
            } else if (useGrowth) {
                candidates = this.getRankingByMetric(date, validTickers, 'growth');
            } else {
                candidates = validTickers.map(ticker => ({ ticker }));
            }
            
            // 返回所有候選股票的排名資訊
            const rankingMap = new Map();
            candidates.forEach((item, index) => {
                rankingMap.set(item.ticker, index + 1);
            });
            
            rankingCache.set(cacheKey, rankingMap);
            return rankingMap;
        };
        
        // 過濾符合市場的股票（排除市場指數）
        const validTickers = tickers.filter(ticker => {
            const info = stockInfo[ticker];
            if (!info) return false;
            
            // 排除市場指數（^IXIC, ^TWII, GC=F, BTC-USD, TLT 等）
            if (info.industry === 'Market Index') return false;
            
            const country = info.country;
            const market = this.settings.market;
            
            if (market === 'global') {
                // 國際：包含所有股票（台股 + 美股）
                return country === 'TW' || country === 'US';
            } else if (market === 'us') {
                // 美股：僅美股
                return country === 'US';
            } else if (market === 'tw') {
                // 台股：僅台股
                return country === 'TW';
            }
            
            return false;
        });
        
        console.log(`📋 符合市場條件的股票: ${validTickers.length} 檔`);
        
        // 決定再平衡日期
        const rebalanceDates = this.getRebalanceDates(dates);
        
        // 模擬每一天
        for (let i = 0; i < dates.length; i++) {
            const date = dates[i];
            const isRebalanceDay = rebalanceDates.includes(date);
            
            // 1. 檢查賣出條件 (sell_sharpe_fail/sell_drawdown 等)
            const { useSharpeDisqualify, useGrowthDisqualify, useBuyNotSelected, usePriceBreakdown, useRelativeWeakness } = this.settings.sellRules;
            const { sharpeDisqualifyPeriods, sharpeDisqualifyN, growthDisqualifyDays, buyNotSelectedPeriods, priceBreakdownPct, relativeWeaknessK, relativeWeaknessPeriods } = this.settings.sellParams;
            
            // 取得當日排名（用於排名相關判斷）
            const rankingMap = isRebalanceDay ? getExtendedRanking(date, validTickers) : null;
            
            // 取得當日的買入候選清單（用於 sell_not_selected）
            const buyCandidate = isRebalanceDay ? this.getTopStocks(date, validTickers) : [];
            
            // 收集要賣出的股票（先收集，後統一賣出，避免遍歷時修改）
            const toSell = [];
            
            for (const [ticker, position] of Object.entries(holdings)) {
                const priceData = prices[ticker]?.[date];
                
                // 取得當前價格（優先使用當日價格，否則使用最後已知價格）
                const currentPrice = priceData?.close || position.lastKnownPrice || position.avgCost;
                
                // 更新最後已知價格
                if (priceData?.close) {
                    position.lastKnownPrice = priceData.close;
                }
                
                // 計算回撤（從最高點）
                if (currentPrice > (position.peakPrice || position.avgCost)) {
                    position.peakPrice = currentPrice;
                }
                const drawdown = ((position.peakPrice - currentPrice) / position.peakPrice) * 100;
                
                let shouldSell = false;
                let sellReason = '';
                
                // === sell_drawdown: 價格破底（每天檢查）===
                if (usePriceBreakdown && drawdown >= priceBreakdownPct) {
                    shouldSell = true;
                    sellReason = `價格破底 (回撤${drawdown.toFixed(1)}%)`;
                }
                
                // === sell_sharpe_fail: Sharpe 長期失格（僅再平衡日檢查）===
                if (!shouldSell && useSharpeDisqualify && isRebalanceDay && rankingMap) {
                    const currentRank = rankingMap.get(ticker) || 999;
                    
                    if (currentRank > sharpeDisqualifyN) {
                        // 掉出 Top-N，增加失格計數
                        position.sharpeDisqualifyCount = (position.sharpeDisqualifyCount || 0) + 1;
                        
                        if (position.sharpeDisqualifyCount >= sharpeDisqualifyPeriods) {
                            shouldSell = true;
                            sellReason = `Sharpe失格 (連續${position.sharpeDisqualifyCount}期不在Top${sharpeDisqualifyN})`;
                        }
                    } else {
                        // 仍在 Top-N 內，重置計數
                        position.sharpeDisqualifyCount = 0;
                    }
                }
                
                // === sell_growth_fail: Growth 長期失格（僅再平衡日檢查）===
                if (!shouldSell && useGrowthDisqualify && isRebalanceDay) {
                    const rankings = window.chartApp?.stockDataCache?.getRankings() || {};
                    
                    // 取得最近 X 天的 Growth 值
                    const recentGrowths = [];
                    for (let j = Math.max(0, i - growthDisqualifyDays + 1); j <= i; j++) {
                        const d = dates[j];
                        const growth = rankings[d]?.[ticker]?.growth;
                        if (growth !== undefined) recentGrowths.push(growth);
                    }
                    
                    if (recentGrowths.length >= growthDisqualifyDays) {
                        const avgGrowth = recentGrowths.reduce((a, b) => a + b, 0) / recentGrowths.length;
                        if (avgGrowth < 0) {
                            shouldSell = true;
                            sellReason = `Growth失格 (近${growthDisqualifyDays}天均值${avgGrowth.toFixed(2)}<0)`;
                        }
                    }
                }
                
                // === sell_not_selected: BUY 多期未入選（僅再平衡日檢查）===
                if (!shouldSell && useBuyNotSelected && isRebalanceDay) {
                    if (!buyCandidate.includes(ticker)) {
                        // 未入選買入候選，增加計數
                        position.buyNotSelectedCount = (position.buyNotSelectedCount || 0) + 1;
                        
                        if (position.buyNotSelectedCount >= buyNotSelectedPeriods) {
                            shouldSell = true;
                            sellReason = `未入選 (連續${position.buyNotSelectedCount}期不在買入候選)`;
                        }
                    } else {
                        // 仍在買入候選內，重置計數
                        position.buyNotSelectedCount = 0;
                    }
                }
                
                // === sell_weakness: 相對強度長期停滯（僅再平衡日檢查）===
                if (!shouldSell && useRelativeWeakness && isRebalanceDay && rankingMap) {
                    const rankings = window.chartApp?.stockDataCache?.getRankings() || {};
                    const dailyRanking = rankings[date];
                    
                    const sharpeRank = rankingMap.get(ticker) || 999;
                    const growthRank = dailyRanking?.[ticker]?.growthRank || 999;
                    
                    if (sharpeRank > relativeWeaknessK && growthRank > relativeWeaknessK) {
                        // Sharpe 和 Growth 排名都很差，增加計數
                        position.relativeWeaknessCount = (position.relativeWeaknessCount || 0) + 1;
                        
                        if (position.relativeWeaknessCount >= relativeWeaknessPeriods) {
                            shouldSell = true;
                            sellReason = `相對弱勢 (Sharpe排${sharpeRank}/Growth排${growthRank}連續${position.relativeWeaknessCount}期)`;
                        }
                    } else {
                        // 至少有一個排名還行，重置計數
                        position.relativeWeaknessCount = 0;
                    }
                }
                
                if (shouldSell) {
                    toSell.push({ ticker, position, reason: sellReason, currentPrice });
                }
            }
            
            // 執行賣出
            for (const { ticker, position, reason, currentPrice } of toSell) {
                const priceData = prices[ticker]?.[date];
                const sellPrice = priceData?.low || currentPrice;
                const sellAmount = position.shares * sellPrice;
                const tickerInfo = stockInfo[ticker];
                const fee = this.calculateFee(sellAmount, tickerInfo?.country);
                const pnl = sellAmount - fee - (position.shares * position.avgCost);
                
                cash += sellAmount - fee;
                
                trades.push({
                    date,
                    action: 'sell',
                    ticker,
                    shares: position.shares,
                    price: sellPrice,
                    amount: sellAmount,
                    fee,
                    pnl,
                    reason,
                    buyDate: position.buyDate  // 加入買入日期
                });
                
                delete holdings[ticker];
            }
            
            // 2. 檢查買入條件（僅在再平衡日）
            if (isRebalanceDay) {
                // 根據投入方式決定是否允許買入
                const shouldInvest = this.checkInvestCondition(date, validTickers, cash);
                
                if (shouldInvest) {
                    const topStocks = this.getTopStocks(date, validTickers);
                    const currentPositions = Object.keys(holdings).length;
                    const availableSlots = this.settings.maxPositions - currentPositions;
                    
                    // 計算本次可用資金（根據投入方式，僅基於現金）
                    const investableAmount = this.calculateInvestableAmount(cash);
                    
                    if (availableSlots > 0 && investableAmount >= this.settings.amountPerStock) {
                        // 過濾掉已持有的股票
                        const buyable = topStocks.filter(t => !holdings[t]);
                        
                        // 選擇要買入的股票（已在 getTopStocks 中根據 buyRule 處理）
                        let toBuy = buyable.slice(0, Math.min(availableSlots, buyable.length));
                        
                        // 追蹤本次已用金額
                        let usedAmount = 0;
                        
                        for (const ticker of toBuy) {
                            // 檢查是否還有足夠可投入金額
                            if (usedAmount + this.settings.amountPerStock > investableAmount) break;
                            if (cash < this.settings.amountPerStock) break;
                            
                            const priceData = prices[ticker]?.[date];
                            if (!priceData || !priceData.close) continue;
                            
                            // 取得股票資訊（國家）
                            const tickerInfo = stockInfo[ticker];
                            const country = tickerInfo?.country || 'US';
                            
                            // 以收盤價買入
                            const buyPrice = priceData.close;
                            
                            // 計算可買股數：台股需整張（100股），美股可零股
                            let shares;
                            if (country === 'TW') {
                                // 台股：以 100 股（一張）為單位
                                const lots = Math.floor(this.settings.amountPerStock / (buyPrice * 100));
                                shares = lots * 100;
                            } else {
                                // 美股：可買零股
                                shares = Math.floor(this.settings.amountPerStock / buyPrice);
                            }
                            if (shares <= 0) continue;
                            
                            const buyAmount = shares * buyPrice;
                            const fee = this.calculateFee(buyAmount, country);
                            
                            if (cash >= buyAmount + fee) {
                                cash -= buyAmount + fee;
                                usedAmount += buyAmount + fee;
                                
                                holdings[ticker] = {
                                    shares,
                                    avgCost: buyPrice,
                                    buyDate: date,
                                    peakPrice: buyPrice,
                                    lastKnownPrice: buyPrice,  // 初始化最後已知價格
                                    rankingDropCount: 0  // 初始化排名掉落計數
                                };
                                
                                trades.push({
                                    date,
                                    action: 'buy',
                                    ticker,
                                    shares,
                                    price: buyPrice,
                                    amount: buyAmount,
                                    fee,
                                    pnl: 0,
                                    reason: '買入'
                                });
                            }
                        }
                    }
                }
            }
            
            // 3. 計算當日總資產
            let holdingsValue = 0;
            for (const [ticker, position] of Object.entries(holdings)) {
                const priceData = prices[ticker]?.[date];
                if (priceData?.close) {
                    holdingsValue += position.shares * priceData.close;
                    // 更新持倉的最後已知價格
                    position.lastKnownPrice = priceData.close;
                } else if (position.lastKnownPrice) {
                    // 使用最後已知價格
                    holdingsValue += position.shares * position.lastKnownPrice;
                } else {
                    // 完全沒有價格資料，使用成本
                    holdingsValue += position.shares * position.avgCost;
                }
            }
            
            const totalEquity = cash + holdingsValue;
            
            // 保存當日持有狀況的快照（深拷貝），以支援權益曲線點擊查看歷史持有
            const holdingsSnapshot = {};
            for (const [ticker, position] of Object.entries(holdings)) {
                const priceData = prices[ticker]?.[date];
                const currentPrice = priceData?.close || position.lastKnownPrice || position.avgCost;
                holdingsSnapshot[ticker] = {
                    shares: position.shares,
                    avgCost: position.avgCost,
                    buyDate: position.buyDate,
                    currentPrice,
                    profit: (currentPrice - position.avgCost) / position.avgCost * 100,
                    industry: stockInfo[ticker]?.industry || '未分類'
                };
            }
            
            equityCurve.push({ date, equity: totalEquity, cash, holdingsValue, holdings: holdingsSnapshot });
        }
        
        // 計算 benchmark（根據市場選擇）的權益曲線
        const benchmarkResult = this.calculateBenchmarkCurve(dates);
        
        // 計算績效指標，傳入最新持有股票資訊
        return this.calculateMetrics(equityCurve, trades, benchmarkResult.curve, benchmarkResult.marketName, holdings, prices, dates, stockInfo);
    }
    
    /**
     * 檢查投入條件
     * 根據 investRule 決定是否允許本次買入
     * @param {string} date - 當前日期
     * @param {Array} validTickers - 有效股票列表
     * @param {number} cash - 當前現金
     * @returns {boolean} - 是否允許投入
     */
    checkInvestCondition(date, validTickers, cash) {
        const { type, concentrateTopK } = this.settings.investRule;
        
        switch (type) {
            case 'hold-cash':
                // rebal_none 保留現金：永不投入
                return false;
                
            case 'delayed':
                // rebal_delayed 延遲投入：等市場轉強 (Sharpe Top5 均值 > 0)
                return this.checkMarketStrength(date, validTickers);
                
            case 'concentrated':
                // rebal_concentrated 集中投入：只在排名前 K 有明確領先時投入
                return this.checkConcentratedCondition(date, validTickers, concentrateTopK);
                
            case 'immediate':
            case 'batch':
            default:
                // rebal_immediate 立即投入 / rebal_batch 分批投入：無條件允許
                return true;
        }
    }
    
    /**
     * 檢查市場強度（用於 rebal_delayed 延遲投入）
     * @param {string} date - 當前日期
     * @param {Array} validTickers - 有效股票列表
     * @returns {boolean} - 市場是否轉強
     */
    checkMarketStrength(date, validTickers) {
        // 取得當日 Sharpe Top 5 的平均值
        const rankings = window.chartApp?.stockDataCache?.getRankings() || {};
        const dailyRanking = rankings[date];
        
        if (!dailyRanking) return false;
        
        // 篩選有效股票的 Sharpe 值
        const sharpeValues = validTickers
            .map(ticker => dailyRanking[ticker]?.sharpe)
            .filter(v => v !== undefined && !isNaN(v))
            .sort((a, b) => b - a);
        
        // 計算 Top 5 平均值
        const top5 = sharpeValues.slice(0, 5);
        if (top5.length === 0) return false;
        
        const avgSharpe = top5.reduce((sum, v) => sum + v, 0) / top5.length;
        return avgSharpe > 0;
    }
    
    /**
     * 檢查集中投入條件（用於 rebal_concentrated）
     * @param {string} date - 當前日期
     * @param {Array} validTickers - 有效股票列表
     * @param {number} topK - 前 K 名門檻
     * @returns {boolean} - 是否有明確領先標的
     */
    checkConcentratedCondition(date, validTickers, topK) {
        const topStocks = this.getTopStocks(date, validTickers);
        
        // 檢查是否有足夠的優質標的
        if (topStocks.length < topK) return false;
        
        // 取得排名資料
        const rankings = window.chartApp?.stockDataCache?.getRankings() || {};
        const dailyRanking = rankings[date];
        
        if (!dailyRanking) return false;
        
        // 檢查前 K 名的 Sharpe 是否都 > 0（有明確領先）
        for (let i = 0; i < Math.min(topK, topStocks.length); i++) {
            const ticker = topStocks[i];
            const sharpe = dailyRanking[ticker]?.sharpe;
            if (!sharpe || sharpe <= 0) return false;
        }
        
        return true;
    }
    
    /**
     * 計算可投入金額
     * 根據 investRule 決定本次可投入的資金上限
     * @param {number} cash - 當前現金
     * @returns {number} - 可投入金額
     */
    calculateInvestableAmount(cash) {
        const { type, batchRatio } = this.settings.investRule;
        
        switch (type) {
            case 'batch':
                // rebal_batch 分批投入：每次只投入現金的固定比例
                return cash * batchRatio;
                
            case 'hold-cash':
                // rebal_none 保留現金：不投入
                return 0;
                
            case 'immediate':
            case 'delayed':
            case 'concentrated':
            default:
                // rebal_immediate/rebal_delayed/rebal_concentrated：可用全部現金
                return cash;
        }
    }
    
    getRebalanceDates(dates) {
        if (this.settings.rebalanceFreq === 'daily') {
            return dates;
        }
        
        const rebalanceDates = [];
        let lastDate = null;
        
        for (const date of dates) {
            const d = new Date(date);
            
            if (this.settings.rebalanceFreq === 'weekly') {
                // 每週一
                if (d.getDay() === 1) {
                    rebalanceDates.push(date);
                }
            } else if (this.settings.rebalanceFreq === 'monthly') {
                // 每月第一個交易日
                if (!lastDate || new Date(lastDate).getMonth() !== d.getMonth()) {
                    rebalanceDates.push(date);
                }
            }
            
            lastDate = date;
        }
        
        // 確保第一天也是再平衡日
        if (dates.length > 0 && !rebalanceDates.includes(dates[0])) {
            rebalanceDates.unshift(dates[0]);
        }
        
        return rebalanceDates;
    }
    
    /**
     * 計算 benchmark 的權益曲線
     * 使用回測 priceData 中的指數資料，確保與回測區間一致
     */
    calculateBenchmarkCurve(dates) {
        // 根據選擇的市場決定使用哪個指數
        let indexTicker = '^IXIC';  // 預設 NASDAQ
        let marketName = '國際加權指數';
        
        switch (this.settings.market) {
            case 'us':
                indexTicker = '^IXIC';
                marketName = 'NASDAQ';
                break;
            case 'tw':
                indexTicker = '^TWII';
                marketName = '台灣加權指數';
                break;
            case 'global':
            default:
                // 國際加權：使用 NASDAQ 作為代表
                indexTicker = '^IXIC';
                marketName = '國際加權指數';
                break;
        }
        
        // 從回測的 priceData 取得指數資料（確保與回測區間一致）
        const { prices } = this.priceData;
        const indexPrices = prices[indexTicker];
        
        if (!indexPrices) {
            console.warn(`⚠️ 無法取得 ${indexTicker} 資料，使用空 benchmark`);
            return { curve: [], marketName };
        }
        
        console.log(`📊 使用 ${indexTicker} (${marketName}) 作為 benchmark`);
        
        // 計算 benchmark 的權益曲線（假設以初始資金全部投入）
        const initial = this.settings.initialCapital;
        const benchmarkCurve = [];
        let firstPrice = null;
        
        for (const date of dates) {
            const priceData = indexPrices[date];
            if (priceData?.close) {
                if (firstPrice === null) {
                    firstPrice = priceData.close;
                }
                // 根據價格變化計算權益
                const equity = initial * (priceData.close / firstPrice);
                benchmarkCurve.push({ date, equity });
            }
        }
        
        return { curve: benchmarkCurve, marketName };
    }
    
    /**
     * 取得單一指標的排名股票（使用完整排名表）
     * @param {string} date - 日期
     * @param {string[]} validTickers - 有效的股票列表
     * @param {string} metric - 'sharpe' 或 'growth'
     * @returns {Array<{ticker: string, rank: number, value: number, industry: string}>} 排名資訊
     */
    getRankingByMetric(date, validTickers, metric) {
        // 取得該市場對應的模式
        const marketModeMap = {
            'global': 'global',
            'us': 'nasdaq',
            'tw': 'twii'
        };
        const mode = marketModeMap[this.settings.market] || 'global';
        
        // 使用新的 getFullRanking 方法取得完整排名表
        const rankingMap = industryDataCache.getFullRanking(date, metric, mode);
        
        // 過濾出有效股票並組成排名陣列
        const ranked = [];
        validTickers.forEach(ticker => {
            const ranking = rankingMap.get(ticker);
            if (ranking) {
                const info = industryDataCache.getStockInfo(ticker);
                ranked.push({
                    ticker,
                    rank: ranking.rank,
                    value: ranking.value,
                    industry: info?.industry || '未知'
                });
            }
        });
        
        // 按排名排序
        ranked.sort((a, b) => a.rank - b.rank);
        
        return ranked;
    }
    
    /**
     * 取得綜合排名（Sharpe + Growth）
     * 使用 Borda Count: 總分 = Sharpe排名 + Growth排名，越低越好
     * @param {string} date - 日期
     * @param {string[]} validTickers - 有效股票列表
     * @returns {Array<{ticker: string, score: number, sharpeRank: number, growthRank: number}>}
     */
    getCombinedRanking(date, validTickers) {
        const sharpeRanked = this.getRankingByMetric(date, validTickers, 'sharpe');
        const growthRanked = this.getRankingByMetric(date, validTickers, 'growth');
        
        // 建立股票評分表
        const scoreMap = new Map();
        
        // Sharpe 排名分數（排名越前，分數越低）
        sharpeRanked.forEach(item => {
            if (!scoreMap.has(item.ticker)) {
                scoreMap.set(item.ticker, { 
                    ticker: item.ticker, 
                    sharpeRank: 999, 
                    growthRank: 999,
                    industry: item.industry
                });
            }
            scoreMap.get(item.ticker).sharpeRank = item.rank;
        });
        
        // Growth 排名分數
        growthRanked.forEach(item => {
            if (!scoreMap.has(item.ticker)) {
                scoreMap.set(item.ticker, { 
                    ticker: item.ticker, 
                    sharpeRank: 999, 
                    growthRank: 999,
                    industry: item.industry
                });
            }
            scoreMap.get(item.ticker).growthRank = item.rank;
            if (item.industry) {
                scoreMap.get(item.ticker).industry = item.industry;
            }
        });
        
        // 計算綜合分數並排序
        const combined = Array.from(scoreMap.values()).map(item => ({
            ...item,
            score: item.sharpeRank + item.growthRank
        }));
        
        // 分數越低越好
        combined.sort((a, b) => a.score - b.score);
        
        return combined;
    }
    
    /**
     * 分散產業輪選
     * 從候選股票中依產業輪流選取，確保產業分散
     * @param {Array} candidates - 候選股票（須含 industry 欄位）
     * @param {number} n - 要選取的數量
     * @returns {string[]} 選中的股票代碼
     */
    applyIndustryRotation(candidates, n) {
        if (candidates.length === 0) return [];
        
        // 按產業分組
        const byIndustry = new Map();
        candidates.forEach(item => {
            const industry = item.industry || '未知';
            if (!byIndustry.has(industry)) {
                byIndustry.set(industry, []);
            }
            byIndustry.get(industry).push(item.ticker);
        });
        
        // 輪流從各產業選取
        const selected = [];
        const industries = Array.from(byIndustry.keys());
        const industryPointers = new Map();
        industries.forEach(ind => industryPointers.set(ind, 0));
        
        let industryIndex = 0;
        while (selected.length < n) {
            const industry = industries[industryIndex % industries.length];
            const tickers = byIndustry.get(industry);
            const pointer = industryPointers.get(industry);
            
            if (pointer < tickers.length) {
                const ticker = tickers[pointer];
                if (!selected.includes(ticker)) {
                    selected.push(ticker);
                }
                industryPointers.set(industry, pointer + 1);
            }
            
            industryIndex++;
            
            // 防止無限迴圈：如果已遍歷所有產業且沒有新增，則退出
            if (industryIndex > industries.length * 50) break;
        }
        
        return selected;
    }
    
    /**
     * 主要選股函數（模組化版本）
     * 支援多選組合：Sharpe + Growth + 分散產業 + 隨機
     */
    getTopStocks(date, validTickers) {
        // 如果沒有排名資料，隨機選擇
        if (!industryDataCache.loaded) {
            return this.shuffle(validTickers).slice(0, this.settings.topN);
        }
        
        const { useSharpe, useGrowth, useIndustry, useRandom } = this.settings.buyRules;
        const topN = this.settings.topN;
        
        let candidates = [];
        
        // ===== Step 1: 取得候選股票（依據選擇的排名指標）=====
        if (useSharpe && useGrowth) {
            // 同時使用兩個指標：綜合排名（Borda Count）
            candidates = this.getCombinedRanking(date, validTickers);
        } else if (useSharpe) {
            // 只用 Sharpe
            candidates = this.getRankingByMetric(date, validTickers, 'sharpe');
        } else if (useGrowth) {
            // 只用 Growth
            candidates = this.getRankingByMetric(date, validTickers, 'growth');
        } else {
            // 預設使用所有有效股票
            candidates = validTickers.map(ticker => ({ ticker, industry: '未知' }));
        }
        
        // ===== Step 2: 分散產業（可選）=====
        let selectedTickers;
        if (useIndustry && candidates.length > 0) {
            // 使用產業輪選
            selectedTickers = this.applyIndustryRotation(candidates, topN * 2); // 取多一些供隨機用
        } else {
            // 直接取前 N（或更多供隨機用）
            const limit = useRandom ? topN * 2 : topN;
            selectedTickers = candidates.slice(0, limit).map(c => c.ticker);
        }
        
        // ===== Step 3: 隨機選取（可選）=====
        if (useRandom && selectedTickers.length > topN) {
            // 從候選池中隨機選取
            selectedTickers = this.shuffle(selectedTickers).slice(0, topN);
        } else {
            // 直接取前 N
            selectedTickers = selectedTickers.slice(0, topN);
        }
        
        return selectedTickers;
    }
    
    daysBetween(date1, date2) {
        const d1 = new Date(date1);
        const d2 = new Date(date2);
        return Math.floor((d2 - d1) / (1000 * 60 * 60 * 24));
    }
    
    /**
     * 計算交易手續費
     * @param {number} amount - 交易金額
     * @param {string} country - 國家代碼 ('US' 或 'TW')
     * @returns {number} 手續費
     * 
     * 手續費結構：
     * - 美股複委託：0.3%，最低 15 USD
     * - 台股：0.6%（含證交稅），無最低
     */
    calculateFee(amount, country) {
        const fees = this.settings.fees;
        
        if (country === 'TW') {
            // 台股：固定 0.6%
            return amount * fees.tw.rate;
        } else {
            // 美股複委託：0.3%，最低 15 USD
            const fee = amount * fees.us.rate;
            return Math.max(fee, fees.us.minFee);
        }
    }
    
    shuffle(array) {
        const arr = [...array];
        for (let i = arr.length - 1; i > 0; i--) {
            const j = Math.floor(Math.random() * (i + 1));
            [arr[i], arr[j]] = [arr[j], arr[i]];
        }
        return arr;
    }
    
    calculateMetrics(equityCurve, trades, benchmarkCurve = [], benchmarkMarketName = '國際加權指數', finalHoldings = {}, prices = {}, dates = [], stockInfo = {}) {
        if (equityCurve.length === 0) {
            return {
                totalReturn: 0,
                annualReturn: 0,
                maxDrawdown: 0,
                sharpeRatio: 0,
                sharpeVsBenchmark: 0,
                benchmarkSharpe: 0,
                winRate: 0,
                tradeCount: 0,
                equityCurve: [],
                benchmarkCurve: [],
                benchmarkMarketName: benchmarkMarketName,
                trades: [],
                holdings: []
            };
        }
        
        const initial = this.settings.initialCapital;
        const final = equityCurve[equityCurve.length - 1].equity;
        
        // 總報酬
        const totalReturn = (final - initial) / initial * 100;
        
        // 年化報酬
        const days = equityCurve.length;
        const years = days / 252;  // 假設 252 交易日
        const annualReturn = years > 0 ? (Math.pow(final / initial, 1 / years) - 1) * 100 : 0;
        
        // 最大回撤
        let peak = initial;
        let maxDrawdown = 0;
        for (const point of equityCurve) {
            peak = Math.max(peak, point.equity);
            const drawdown = (peak - point.equity) / peak * 100;
            maxDrawdown = Math.max(maxDrawdown, drawdown);
        }
        
        // 計算日報酬率
        const dailyReturns = [];
        for (let i = 1; i < equityCurve.length; i++) {
            const ret = (equityCurve[i].equity - equityCurve[i-1].equity) / equityCurve[i-1].equity;
            dailyReturns.push(ret);
        }
        
        // 策略夏普比率 (假設無風險利率 = 0)
        const avgReturn = dailyReturns.reduce((a, b) => a + b, 0) / dailyReturns.length;
        const stdDev = Math.sqrt(dailyReturns.reduce((sum, r) => sum + Math.pow(r - avgReturn, 2), 0) / dailyReturns.length);
        const sharpeRatio = stdDev > 0 ? (avgReturn / stdDev) * Math.sqrt(252) : 0;
        
        // 計算 benchmark 夏普比率
        let benchmarkSharpe = 0;
        if (benchmarkCurve.length > 1) {
            const benchmarkReturns = [];
            for (let i = 1; i < benchmarkCurve.length; i++) {
                const ret = (benchmarkCurve[i].equity - benchmarkCurve[i-1].equity) / benchmarkCurve[i-1].equity;
                benchmarkReturns.push(ret);
            }
            const bmAvgReturn = benchmarkReturns.reduce((a, b) => a + b, 0) / benchmarkReturns.length;
            const bmStdDev = Math.sqrt(benchmarkReturns.reduce((sum, r) => sum + Math.pow(r - bmAvgReturn, 2), 0) / benchmarkReturns.length);
            benchmarkSharpe = bmStdDev > 0 ? (bmAvgReturn / bmStdDev) * Math.sqrt(252) : 0;
        }
        
        // 計算相對 benchmark 的夏普比率（策略夏普 / benchmark 夏普）
        // 大於 1 表示優於市場，小於 1 表示不如市場
        const sharpeVsBenchmark = benchmarkSharpe !== 0 ? sharpeRatio / benchmarkSharpe : 0;
        
        // 勝率
        const sellTrades = trades.filter(t => t.action === 'sell');
        const winTrades = sellTrades.filter(t => t.pnl > 0);
        const winRate = sellTrades.length > 0 ? (winTrades.length / sellTrades.length) * 100 : 0;
        
        // 處理最新持有股票資訊
        const lastDate = dates[dates.length - 1];
        
        const holdingsInfo = Object.entries(finalHoldings).map(([ticker, pos]) => {
            // 找該股票最新可用的價格（從最新日期往回找）
            let currentPrice = pos.avgCost;
            let priceDate = pos.buyDate;
            
            const tickerPrices = prices[ticker];
            if (tickerPrices) {
                // 從最後一個日期往前找，找到第一個有效價格
                for (let i = dates.length - 1; i >= 0; i--) {
                    const d = dates[i];
                    if (tickerPrices[d]?.close) {
                        currentPrice = tickerPrices[d].close;
                        priceDate = d;
                        break;
                    }
                }
            }
            
            const marketValue = pos.shares * currentPrice;
            const profit = (currentPrice - pos.avgCost) / pos.avgCost * 100;
            
            // 取得產業別
            const industry = stockInfo[ticker]?.industry || '未分類';
            
            return {
                ticker,
                shares: pos.shares,
                avgCost: pos.avgCost,
                currentPrice,
                marketValue,
                profit,
                buyDate: pos.buyDate,
                priceDate,  // 加入價格日期，方便顯示
                industry    // 加入產業別
            };
        }).sort((a, b) => b.marketValue - a.marketValue);  // 按市值排序
        
        return {
            totalReturn,
            annualReturn,
            maxDrawdown,
            sharpeRatio,
            sharpeVsBenchmark,
            benchmarkSharpe,
            winRate,
            tradeCount: trades.length,
            equityCurve,
            benchmarkCurve,
            benchmarkMarketName,
            trades,
            holdings: holdingsInfo
        };
    }
    
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
    
    updateMetric(id, value, isPositive) {
        const el = document.getElementById(id);
        if (el) {
            el.textContent = value;
            el.classList.remove('positive', 'negative');
            if (isPositive !== null) {
                el.classList.add(isPositive ? 'positive' : 'negative');
            }
        }
    }
    
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
        const isProfit = totalData.length > 0 && totalData[totalData.length - 1] >= this.settings.initialCapital;
        
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
        
        // 如果有 benchmark 資料，加入第二條線
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
                borderWidth: 1.5,
                borderDash: [5, 5]
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
                        stacked: true,
                        grid: { color: '#21262d' },
                        ticks: { 
                            color: '#7d8590',
                            maxTicksLimit: 6,
                            font: { size: 10 }
                        }
                    },
                    y: {
                        display: true,
                        stacked: true,
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
        const holdingsArray = Object.entries(holdingsSnapshot).map(([ticker, h]) => ({
            ticker,
            shares: h.shares,
            avgCost: h.avgCost,
            currentPrice: h.currentPrice,
            marketValue: h.shares * h.currentPrice,
            profit: h.profit,
            buyDate: h.buyDate,
            industry: h.industry
        })).sort((a, b) => b.marketValue - a.marketValue);
        
        // 傳遞現金和總資產資訊
        this.displayHoldings(holdingsArray, point.date, point.cash, point.equity);
    }
    
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
                    <span class="holdings-total">現金: $${Math.round(cash).toLocaleString()} (100%)</span>
                </div>
            ` : '<div class="holdings-empty">無持有股票（所有部位已平倉）</div>';
            
            container.innerHTML = `
                <div class="holdings-header">${dateLabel}</div>
                ${cashInfo}
            `;
            return;
        }
        
        // 計算持股市值
        const holdingsValue = holdings.reduce((sum, h) => sum + h.marketValue, 0);
        
        // 如果有傳入 cash，使用它；否則從 totalEquity 反推
        const cashAmount = cash !== null ? cash : (totalEquity !== null ? totalEquity - holdingsValue : 0);
        const equity = totalEquity !== null ? totalEquity : (holdingsValue + cashAmount);
        
        // 計算比例
        const cashPct = equity > 0 ? (cashAmount / equity * 100).toFixed(1) : 0;
        const holdingsPct = equity > 0 ? (holdingsValue / equity * 100).toFixed(1) : 0;
        
        container.innerHTML = `
            <div class="holdings-header">${dateLabel}</div>
            <div class="holdings-summary">
                <span class="holdings-count">持有 ${holdings.length} 檔</span>
                <span class="holdings-cash">現金: $${Math.round(cashAmount).toLocaleString()} (${cashPct}%)</span>
                <span class="holdings-stocks-value">持股: $${Math.round(holdingsValue).toLocaleString()} (${holdingsPct}%)</span>
                <span class="holdings-total">總資產: $${Math.round(equity).toLocaleString()}</span>
            </div>
            ${holdings.map(h => {
                const profitClass = h.profit >= 0 ? 'positive' : 'negative';
                const profitStr = (h.profit >= 0 ? '+' : '') + h.profit.toFixed(1) + '%';
                // 計算單檔持股佔總資產比例
                const weight = equity > 0 ? (h.marketValue / equity * 100).toFixed(1) : 0;
                
                return `
                    <div class="holdings-item">
                        <span class="holdings-ticker">${h.ticker} <span class="holdings-industry">(${h.industry})</span></span>
                        <span class="holdings-weight">${weight}%</span>
                        <span class="holdings-shares">${h.shares} 股</span>
                        <span class="holdings-cost">成本: $${h.avgCost.toFixed(2)}</span>
                        <span class="holdings-current">現價: $${h.currentPrice.toFixed(2)}</span>
                        <span class="holdings-profit ${profitClass}">${profitStr}</span>
                        <span class="holdings-buy-date">買: ${h.buyDate}</span>
                    </div>
                `;
            }).join('')}
        `;
    }
    
    reset() {
        // 重置結果
        this.results = null;
        this.clearPreviousResults();
        
        // 重置日期
        this.setDefaultDates();
    }
    
    /**
     * 清空上一次回測的顯示結果
     */
    clearPreviousResults() {
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
}
