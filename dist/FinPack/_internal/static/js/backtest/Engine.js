/**
 * BacktestEngine - 回測引擎
 * 
 * 整合所有模組執行回測：
 *   - Portfolio: 投資組合管理
 *   - Trade: 交易執行
 *   - Report: 績效報告
 *   - BuyConditions: 買入條件
 *   - SellConditions: 賣出條件
 *   - RebalanceStrategy: 再平衡策略
 */

// 不可交易的 industry 類型（由 TradingView 分類決定）
const NON_TRADABLE_INDUSTRIES = new Set(['Market Index', 'Index']);

import { Portfolio } from '../core/Portfolio.js';
import { Trade } from '../core/Trade.js';
import { Report } from '../core/Report.js';
import { createBuyConditions, applyBuyConditions } from './buying/index.js';
import { createSellConditions, checkSellConditions } from './selling/index.js';
import { createAndConfigureStrategy } from './rebalance/index.js';

export class BacktestEngine {
    /**
     * @param {Object} options
     *   - initialCapital: 初始資金
     *   - fees: 手續費結構
     *   - amountPerStock: 每檔投入金額
     *   - maxPositions: 最大持倉數
     */
    constructor(options = {}) {
        this.options = {
            initialCapital: options.initialCapital || 1000000,
            fees: options.fees || {
                us: { rate: 0.003, minFee: 15 },
                tw: { rate: 0.006, minFee: 0 }
            },
            amountPerStock: options.amountPerStock || 100000,
            maxPositions: options.maxPositions || 10,
            market: options.market || 'global'  // 'global', 'us', 'tw'
        };
        
        // 初始化模組
        this.portfolio = new Portfolio({
            initialCapital: this.options.initialCapital,
            fees: this.options.fees
        });
        
        this.trade = new Trade(this.portfolio, {
            amountPerStock: this.options.amountPerStock,
            maxPositions: this.options.maxPositions
        });
        
        // 條件與策略（稍後設定）
        this.buyConditions = [];
        this.sellConditions = [];
        this.rebalanceStrategy = null;
        
        // 運行狀態
        this.isRunning = false;
        this.lastRebalanceDate = null;
        this.selectionHistory = {};  // date -> selected tickers
    }
    
    /**
     * 設定買入條件
     * @param {Object} config - {conditionId: {enabled, params}}
     */
    setBuyConditions(config) {
        this.buyConditions = createBuyConditions(config);
    }
    
    /**
     * 設定賣出條件
     * @param {Object} config - {conditionId: {enabled, params}}
     */
    setSellConditions(config) {
        this.sellConditions = createSellConditions(config);
    }
    
    /**
     * 設定再平衡策略
     * @param {string} strategyId
     * @param {Object} params
     */
    setRebalanceStrategy(strategyId, params = {}) {
        this.rebalanceStrategy = createAndConfigureStrategy(strategyId, params);
    }
    
    /**
     * 執行回測
     * @param {Object} data - 回測數據
     *   - dates: 日期陣列
     *   - prices: {ticker: {date: price}}
     *   - stockInfo: {ticker: {country, industry}}
     *   - sharpeRank: {date: {US: [], TW: []}}
     *   - growthRank: {date: {US: [], TW: []}}
     *   - sharpeValues: {date: {ticker: value}}
     *   - growthValues: {date: {ticker: value}}
     *   - exchangeRates: {date: rate} 美元兌台幣歷史匯率
     * @param {Object} options
     *   - startDate: 開始日期
     *   - endDate: 結束日期
     *   - onProgress: 進度回調
     * @returns {Object} 回測結果
     */
    async run(data, options = {}) {
        if (this.isRunning) {
            throw new Error('Backtest already running');
        }
        
        this.isRunning = true;
        this.portfolio.reset();
        this.lastRebalanceDate = null;
        this.selectionHistory = {};
        
        const { dates, prices, stockInfo, sharpeRank, growthRank, sharpeValues, growthValues, exchangeRates } = data;
        const { startDate, endDate, onProgress } = options;
        
        // 預設匯率（如果沒有歷史數據）
        const defaultExchangeRate = 32.0;
        
        // 過濾日期範圍
        const tradingDates = dates.filter(d => {
            if (startDate && d < startDate) return false;
            if (endDate && d > endDate) return false;
            return true;
        });
        
        // 記錄配置日期 vs 實際交易日期
        const actualStartDate = tradingDates.length > 0 ? tradingDates[0] : null;
        const actualEndDate = tradingDates.length > 0 ? tradingDates[tradingDates.length - 1] : null;
        
        // 保存日期元數據
        this.dateMetadata = {
            configuredStart: startDate,
            configuredEnd: endDate,
            actualStart: actualStartDate,
            actualEnd: actualEndDate,
            startMismatch: startDate && actualStartDate && actualStartDate !== startDate,
            endMismatch: endDate && actualEndDate && actualEndDate !== endDate,
            availableDates: dates.length,
            tradingDays: tradingDates.length
        };
        
        console.log('🚀 開始回測:', {
            configuredDates: `${startDate} ~ ${endDate}`,
            actualDates: `${actualStartDate} ~ ${actualEndDate}`,
            tradingDays: tradingDates.length,
            buyConditions: this.buyConditions.map(c => c.id),
            sellConditions: this.sellConditions.map(c => c.id),
            rebalanceStrategy: this.rebalanceStrategy?.id
        });
        
        // 警告日期不匹配
        if (this.dateMetadata.startMismatch) {
            console.warn(`⚠️ 起始日期調整: ${startDate} → ${actualStartDate} (非交易日)`);
        }
        if (this.dateMetadata.endMismatch) {
            console.warn(`⚠️ 結束日期調整: ${endDate} → ${actualEndDate} (非交易日)`);
        }
        
        // 驗證日期範圍
        if (tradingDates.length === 0) {
            return {
                success: false,
                error: `指定日期範圍內無交易日數據。API 數據範圍: ${dates[0] || 'N/A'} ~ ${dates[dates.length - 1] || 'N/A'}`,
                dateMetadata: this.dateMetadata
            };
        }
        
        // 檢查日期範圍是否在 API 數據範圍內
        if (startDate && dates.length > 0 && startDate < dates[0]) {
            console.warn(`⚠️ 配置起始日期 ${startDate} 早於 API 數據 ${dates[0]}，實際從 ${actualStartDate} 開始`);
        }
        if (endDate && dates.length > 0 && endDate > dates[dates.length - 1]) {
            console.warn(`⚠️ 配置結束日期 ${endDate} 晚於 API 數據 ${dates[dates.length - 1]}，實際至 ${actualEndDate} 結束`);
        }
        
        try {
            for (let i = 0; i < tradingDates.length; i++) {
                const date = tradingDates[i];
                
                // 取得當日匯率（如果沒有該日資料，找最近的前一天）
                let exchangeRate = exchangeRates?.[date] || defaultExchangeRate;
                if (!exchangeRates?.[date] && exchangeRates) {
                    // 找最近的歷史匯率
                    const sortedDates = Object.keys(exchangeRates).sort();
                    for (let j = sortedDates.length - 1; j >= 0; j--) {
                        if (sortedDates[j] <= date) {
                            exchangeRate = exchangeRates[sortedDates[j]];
                            break;
                        }
                    }
                }
                
                // 準備當日上下文
                const context = this._buildContext(date, {
                    prices: this._getPricesForDate(prices, date),
                    stockInfo,
                    ranking: {
                        sharpe: sharpeRank?.[date] || {},
                        growth: growthRank?.[date] || {}
                    },
                    sharpeValues: sharpeValues?.[date] || {},
                    growthValues: growthValues?.[date] || {},
                    history: {
                        sharpeRank,
                        growthRank,
                        growthValues
                    },
                    market: this.options.market,
                    exchangeRate  // 當日匯率
                });
                
                // Debug: 首日輸出詳細資訊
                if (i === 0) {
                    console.log('📅 首日上下文:', {
                        date,
                        exchangeRate,
                        pricesCount: Object.keys(context.prices).length,
                        sharpeUSRank: context.ranking.sharpe?.US?.slice(0, 5),
                        sharpeTWRank: context.ranking.sharpe?.TW?.slice(0, 5),
                        sharpeValuesCount: Object.keys(context.sharpeValues).length,
                        sampleSharpeValues: Object.entries(context.sharpeValues).slice(0, 3)
                    });
                }
                
                // 1. 檢查賣出條件
                await this._processSellSignals(date, context);
                
                // 2. 選股
                const selectedStocks = this._selectStocks(context);
                this.selectionHistory[date] = selectedStocks;
                
                // Debug: 首日輸出選股結果
                if (i === 0) {
                    console.log('📊 首日選股結果:', selectedStocks.slice(0, 10));
                }
                
                // 3. 檢查再平衡
                await this._processRebalance(date, selectedStocks, context);
                
                // 4. 買入新股（如果有空位）
                await this._processBuySignals(date, selectedStocks, context);
                
                // 5. 記錄每日權益（傳入 stockInfo 和 exchangeRate 以記錄每日持有詳情）
                this.portfolio.recordHistory(date, context.prices, context.stockInfo, context.exchangeRate);
                
                // 進度回調
                if (onProgress) {
                    onProgress({
                        current: i + 1,
                        total: tradingDates.length,
                        date,
                        equity: this.portfolio.calculateValue(context.prices, context.exchangeRate).totalValue
                    });
                }
                
                // 保存最後一天的資訊供 finalPositions 使用
                this.lastPrices = context.prices;
                this.lastExchangeRate = context.exchangeRate;
            }
            
            // 生成報告
            const report = new Report(this.portfolio);
            
            // 構建 finalPositions 包含最新價格
            const positions = this.portfolio.getPositions();
            const finalPositions = {};
            for (const [ticker, pos] of positions) {
                finalPositions[ticker] = {
                    ...pos,
                    lastPrice: this.lastPrices?.[ticker] || pos.avgCost,
                    exchangeRate: pos.country.toUpperCase() === 'US' ? this.lastExchangeRate : 1
                };
            }
            
            return {
                success: true,
                metrics: report.calculateMetrics(),
                equityCurve: this.portfolio.getEquityCurve(),
                trades: this.portfolio.getTradeLog(),
                finalPositions,
                selectionHistory: this.selectionHistory,
                dateMetadata: this.dateMetadata  // 包含配置日期 vs 實際日期的資訊
            };
            
        } catch (error) {
            return {
                success: false,
                error: error.message
            };
        } finally {
            this.isRunning = false;
        }
    }
    
    /**
     * 建立上下文
     */
    _buildContext(date, additionalContext) {
        return {
            date,
            currentHoldings: this.portfolio.getHoldings(),
            lastRebalanceDate: this.lastRebalanceDate,
            selectionHistory: this.selectionHistory,
            priceHistory: additionalContext.prices,  // 這裡需要完整價格歷史
            ...additionalContext
        };
    }
    
    /**
     * 取得特定日期的價格
     */
    _getPricesForDate(prices, date) {
        const result = {};
        for (const [ticker, priceData] of Object.entries(prices)) {
            if (priceData[date] !== undefined) {
                result[ticker] = priceData[date];
            }
        }
        return result;
    }
    
    /**
     * 選股
     */
    _selectStocks(context) {
        // 取得所有可投資股票
        let candidates = Object.keys(context.stockInfo);
        
        // 根據 TradingView 分類排除不可交易的標的（Market Index, Index 等）
        candidates = candidates.filter(t => !NON_TRADABLE_INDUSTRIES.has(context.stockInfo[t]?.industry));
        
        // 根據市場過濾
        if (this.options.market === 'us') {
            candidates = candidates.filter(t => context.stockInfo[t]?.country === 'US');
        } else if (this.options.market === 'tw') {
            candidates = candidates.filter(t => context.stockInfo[t]?.country === 'TW');
        }
        
        // 套用買入條件
        return applyBuyConditions(candidates, this.buyConditions, context);
    }
    
    /**
     * 處理賣出信號
     */
    async _processSellSignals(date, context) {
        const holdings = this.portfolio.getHoldings();
        const exchangeRate = context.exchangeRate || 32.0;
        
        for (const ticker of holdings) {
            const position = this.portfolio.getPosition(ticker);
            const price = context.prices[ticker];
            
            if (!position || price === undefined) continue;
            
            // 檢查所有賣出條件
            const sellCheck = checkSellConditions(
                ticker, 
                position, 
                this.sellConditions,
                { ...context, price }
            );
            
            if (sellCheck.shouldSell) {
                const reasons = sellCheck.reasons.map(r => r.reason).join('; ');
                this.trade.executeSell(ticker, price, date, reasons, { exchangeRate });
            }
        }
    }
    
    /**
     * 處理再平衡
     */
    async _processRebalance(date, targetStocks, context) {
        if (!this.rebalanceStrategy || !this.rebalanceStrategy.enabled) return;
        
        const exchangeRate = context.exchangeRate || 32.0;
        
        const rebalanceContext = {
            date,
            currentHoldings: this.portfolio.getHoldings(),
            targetStocks,
            lastRebalanceDate: this.lastRebalanceDate
        };
        
        if (this.rebalanceStrategy.shouldRebalance(rebalanceContext)) {
            this.rebalanceStrategy.execute(
                this.trade,
                targetStocks,
                context.prices,
                context.stockInfo,
                date,
                { exchangeRate }  // 傳入匯率
            );
            this.lastRebalanceDate = date;
        }
    }
    
    /**
     * 處理買入信號
     */
    async _processBuySignals(date, selectedStocks, context) {
        const exchangeRate = context.exchangeRate || 32.0;
        
        // 過濾掉已持有的
        const currentHoldings = new Set(this.portfolio.getHoldings());
        const toBuy = selectedStocks.filter(t => !currentHoldings.has(t));
        
        // 按優先順序買入（假設 selectedStocks 已排序）
        for (const ticker of toBuy) {
            // 檢查是否還有空位
            if (this.portfolio.getPositionCount() >= this.options.maxPositions) break;
            
            const price = context.prices[ticker];
            const info = context.stockInfo[ticker];
            
            if (price !== undefined && info) {
                this.trade.executeBuy(ticker, price, info.country, date, { exchangeRate });
            }
        }
    }
    
    /**
     * 取得當前配置摘要
     */
    getConfigSummary() {
        return {
            options: this.options,
            buyConditions: this.buyConditions.map(c => c.getInfo()),
            sellConditions: this.sellConditions.map(c => c.getInfo()),
            rebalanceStrategy: this.rebalanceStrategy?.getInfo() || null
        };
    }
    
    /**
     * 重置引擎
     */
    reset() {
        this.portfolio.reset();
        this.lastRebalanceDate = null;
        this.selectionHistory = {};
        this.isRunning = false;
    }
}
