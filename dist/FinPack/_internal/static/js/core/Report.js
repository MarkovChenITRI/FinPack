/**
 * Report - 績效報告模組
 * 
 * 負責：
 *   - 計算績效指標
 *   - 生成報告
 *   - 格式化輸出
 */

export class Report {
    /**
     * @param {Portfolio} portfolio - 投資組合實例
     */
    constructor(portfolio) {
        this.portfolio = portfolio;
    }
    
    /**
     * 計算完整績效指標
     * @returns {Object}
     */
    calculateMetrics() {
        const equity = this.portfolio.getEquityCurve();
        const trades = this.portfolio.getTradeLog();
        
        if (equity.length < 2) {
            return this._emptyMetrics();
        }
        
        const initialValue = this.portfolio.initialCapital;
        const finalValue = equity[equity.length - 1].equity;
        
        return {
            // 基本報酬
            totalReturn: this._calculateTotalReturn(initialValue, finalValue),
            totalReturnPct: ((finalValue - initialValue) / initialValue) * 100,
            
            // 年化報酬
            annualizedReturn: this._calculateAnnualizedReturn(equity),
            
            // 風險指標
            maxDrawdown: this._calculateMaxDrawdown(equity),
            volatility: this._calculateVolatility(equity),
            
            // 風險調整報酬
            sharpeRatio: this._calculateSharpeRatio(equity),
            sortinoRatio: this._calculateSortinoRatio(equity),
            calmarRatio: this._calculateCalmarRatio(equity),
            
            // 交易統計
            tradeStats: this._calculateTradeStats(trades),
            
            // 期間統計
            periodStats: this._calculatePeriodStats(equity)
        };
    }
    
    /**
     * 計算總報酬
     */
    _calculateTotalReturn(initial, final) {
        return final - initial;
    }
    
    /**
     * 計算年化報酬率
     */
    _calculateAnnualizedReturn(equity) {
        if (equity.length < 2) return 0;
        
        const startDate = new Date(equity[0].date);
        const endDate = new Date(equity[equity.length - 1].date);
        const years = (endDate - startDate) / (365.25 * 24 * 60 * 60 * 1000);
        
        if (years <= 0) return 0;
        
        const totalReturn = equity[equity.length - 1].equity / equity[0].equity;
        return (Math.pow(totalReturn, 1 / years) - 1) * 100;
    }
    
    /**
     * 計算最大回撤
     */
    _calculateMaxDrawdown(equity) {
        let maxDrawdown = 0;
        let peak = equity[0].equity;
        let drawdownStart = null;
        let drawdownEnd = null;
        let maxDrawdownStart = null;
        let maxDrawdownEnd = null;
        
        for (let i = 1; i < equity.length; i++) {
            const value = equity[i].equity;
            
            if (value > peak) {
                peak = value;
                drawdownStart = equity[i].date;
            }
            
            const drawdown = (peak - value) / peak;
            
            if (drawdown > maxDrawdown) {
                maxDrawdown = drawdown;
                maxDrawdownStart = drawdownStart;
                maxDrawdownEnd = equity[i].date;
            }
        }
        
        return {
            value: maxDrawdown * 100,  // 百分比
            startDate: maxDrawdownStart,
            endDate: maxDrawdownEnd
        };
    }
    
    /**
     * 計算波動率（年化標準差）
     */
    _calculateVolatility(equity) {
        const returns = this._calculateDailyReturns(equity);
        if (returns.length < 2) return 0;
        
        const mean = returns.reduce((a, b) => a + b, 0) / returns.length;
        const variance = returns.reduce((sum, r) => sum + Math.pow(r - mean, 2), 0) / (returns.length - 1);
        const stdDev = Math.sqrt(variance);
        
        // 年化：假設 252 個交易日
        return stdDev * Math.sqrt(252) * 100;
    }
    
    /**
     * 計算日報酬率
     */
    _calculateDailyReturns(equity) {
        const returns = [];
        for (let i = 1; i < equity.length; i++) {
            const dailyReturn = (equity[i].equity - equity[i - 1].equity) / equity[i - 1].equity;
            returns.push(dailyReturn);
        }
        return returns;
    }
    
    /**
     * 計算 Sharpe Ratio
     * @param {number} riskFreeRate - 年化無風險利率（預設 2%）
     */
    _calculateSharpeRatio(equity, riskFreeRate = 0.02) {
        const returns = this._calculateDailyReturns(equity);
        if (returns.length < 2) return 0;
        
        const mean = returns.reduce((a, b) => a + b, 0) / returns.length;
        const stdDev = Math.sqrt(returns.reduce((sum, r) => sum + Math.pow(r - mean, 2), 0) / (returns.length - 1));
        
        if (stdDev === 0) return 0;
        
        // 年化
        const annualizedReturn = mean * 252;
        const annualizedStdDev = stdDev * Math.sqrt(252);
        
        return (annualizedReturn - riskFreeRate) / annualizedStdDev;
    }
    
    /**
     * 計算 Sortino Ratio（只考慮下行風險）
     */
    _calculateSortinoRatio(equity, riskFreeRate = 0.02) {
        const returns = this._calculateDailyReturns(equity);
        if (returns.length < 2) return 0;
        
        const mean = returns.reduce((a, b) => a + b, 0) / returns.length;
        
        // 只計算負報酬的標準差
        const negativeReturns = returns.filter(r => r < 0);
        if (negativeReturns.length === 0) return Infinity;
        
        const downside = Math.sqrt(negativeReturns.reduce((sum, r) => sum + r * r, 0) / negativeReturns.length);
        
        if (downside === 0) return 0;
        
        // 年化
        const annualizedReturn = mean * 252;
        const annualizedDownside = downside * Math.sqrt(252);
        
        return (annualizedReturn - riskFreeRate) / annualizedDownside;
    }
    
    /**
     * 計算 Calmar Ratio（報酬 / 最大回撤）
     */
    _calculateCalmarRatio(equity) {
        const annualizedReturn = this._calculateAnnualizedReturn(equity);
        const maxDrawdown = this._calculateMaxDrawdown(equity).value;
        
        if (maxDrawdown === 0) return Infinity;
        
        return annualizedReturn / maxDrawdown;
    }
    
    /**
     * 計算交易統計
     */
    _calculateTradeStats(trades) {
        const sells = trades.filter(t => t.action === 'SELL');
        
        if (sells.length === 0) {
            return {
                totalTrades: trades.length,
                buyCount: trades.filter(t => t.action === 'BUY').length,
                sellCount: 0,
                winRate: 0,
                avgProfit: 0,
                avgLoss: 0,
                profitFactor: 0,
                avgHoldingDays: 0
            };
        }
        
        const winners = sells.filter(t => t.profit > 0);
        const losers = sells.filter(t => t.profit <= 0);
        
        const totalProfit = winners.reduce((sum, t) => sum + t.profit, 0);
        const totalLoss = Math.abs(losers.reduce((sum, t) => sum + t.profit, 0));
        
        return {
            totalTrades: trades.length,
            buyCount: trades.filter(t => t.action === 'BUY').length,
            sellCount: sells.length,
            winRate: (winners.length / sells.length) * 100,
            winCount: winners.length,
            loseCount: losers.length,
            avgProfit: winners.length > 0 ? totalProfit / winners.length : 0,
            avgLoss: losers.length > 0 ? totalLoss / losers.length : 0,
            profitFactor: totalLoss > 0 ? totalProfit / totalLoss : Infinity,
            avgHoldingDays: sells.reduce((sum, t) => sum + (t.holdingDays || 0), 0) / sells.length,
            totalFees: trades.reduce((sum, t) => sum + (t.fee || 0), 0)
        };
    }
    
    /**
     * 計算期間統計
     */
    _calculatePeriodStats(equity) {
        if (equity.length < 2) {
            return {
                tradingDays: 0,
                startDate: null,
                endDate: null,
                bestDay: { date: null, return: 0 },
                worstDay: { date: null, return: 0 }
            };
        }
        
        const returns = [];
        for (let i = 1; i < equity.length; i++) {
            const dailyReturn = (equity[i].equity - equity[i - 1].equity) / equity[i - 1].equity;
            returns.push({
                date: equity[i].date,
                return: dailyReturn * 100
            });
        }
        
        const best = returns.reduce((a, b) => a.return > b.return ? a : b);
        const worst = returns.reduce((a, b) => a.return < b.return ? a : b);
        
        return {
            tradingDays: equity.length,
            startDate: equity[0].date,
            endDate: equity[equity.length - 1].date,
            bestDay: best,
            worstDay: worst
        };
    }
    
    /**
     * 空白指標（無數據時）
     */
    _emptyMetrics() {
        return {
            totalReturn: 0,
            totalReturnPct: 0,
            annualizedReturn: 0,
            maxDrawdown: { value: 0, startDate: null, endDate: null },
            volatility: 0,
            sharpeRatio: 0,
            sortinoRatio: 0,
            calmarRatio: 0,
            tradeStats: {
                totalTrades: 0,
                buyCount: 0,
                sellCount: 0,
                winRate: 0,
                avgProfit: 0,
                avgLoss: 0,
                profitFactor: 0,
                avgHoldingDays: 0,
                totalFees: 0
            },
            periodStats: {
                tradingDays: 0,
                startDate: null,
                endDate: null,
                bestDay: { date: null, return: 0 },
                worstDay: { date: null, return: 0 }
            }
        };
    }
    
    /**
     * 生成文字報告
     * @returns {string}
     */
    generateTextReport() {
        const metrics = this.calculateMetrics();
        const lines = [];
        
        lines.push('═'.repeat(50));
        lines.push('回測績效報告');
        lines.push('═'.repeat(50));
        
        lines.push('\n📊 報酬指標');
        lines.push('-'.repeat(30));
        lines.push(`總報酬: ${this._formatCurrency(metrics.totalReturn)} (${metrics.totalReturnPct.toFixed(2)}%)`);
        lines.push(`年化報酬: ${metrics.annualizedReturn.toFixed(2)}%`);
        
        lines.push('\n📉 風險指標');
        lines.push('-'.repeat(30));
        lines.push(`最大回撤: ${metrics.maxDrawdown.value.toFixed(2)}%`);
        lines.push(`波動率: ${metrics.volatility.toFixed(2)}%`);
        
        lines.push('\n⚖️ 風險調整報酬');
        lines.push('-'.repeat(30));
        lines.push(`Sharpe Ratio: ${metrics.sharpeRatio.toFixed(2)}`);
        lines.push(`Sortino Ratio: ${metrics.sortinoRatio.toFixed(2)}`);
        lines.push(`Calmar Ratio: ${metrics.calmarRatio.toFixed(2)}`);
        
        lines.push('\n📈 交易統計');
        lines.push('-'.repeat(30));
        lines.push(`總交易次數: ${metrics.tradeStats.totalTrades}`);
        lines.push(`勝率: ${metrics.tradeStats.winRate.toFixed(1)}%`);
        lines.push(`獲利因子: ${metrics.tradeStats.profitFactor.toFixed(2)}`);
        lines.push(`平均持有天數: ${metrics.tradeStats.avgHoldingDays.toFixed(1)}`);
        lines.push(`總手續費: ${this._formatCurrency(metrics.tradeStats.totalFees)}`);
        
        lines.push('\n📅 期間統計');
        lines.push('-'.repeat(30));
        lines.push(`交易天數: ${metrics.periodStats.tradingDays}`);
        lines.push(`期間: ${metrics.periodStats.startDate} ~ ${metrics.periodStats.endDate}`);
        lines.push(`最佳單日: ${metrics.periodStats.bestDay.date} (${metrics.periodStats.bestDay.return.toFixed(2)}%)`);
        lines.push(`最差單日: ${metrics.periodStats.worstDay.date} (${metrics.periodStats.worstDay.return.toFixed(2)}%)`);
        
        lines.push('\n' + '═'.repeat(50));
        
        return lines.join('\n');
    }
    
    /**
     * 格式化貨幣
     */
    _formatCurrency(value) {
        return value.toLocaleString('zh-TW', { 
            style: 'currency', 
            currency: 'TWD',
            maximumFractionDigits: 0
        });
    }
    
    /**
     * 生成 JSON 報告
     * @returns {Object}
     */
    generateJsonReport() {
        return {
            metrics: this.calculateMetrics(),
            equityCurve: this.portfolio.getEquityCurve(),
            trades: this.portfolio.getTradeLog(),
            finalPositions: Object.fromEntries(this.portfolio.getPositions())
        };
    }
}
