/**
 * backtest.js - 回測 API
 * 
 * 對應後端路由：engine/routes/backtest.py
 * 
 * 所有回測計算由後端執行：
 *   - POST /api/backtest/run → engine/backtest/tester.py
 */

import { get, post } from './client.js';
import { API } from '../config.js';

/**
 * 取得回測配置（可用的條件選項）
 * @returns {Promise<Object>} - { buy_conditions, sell_conditions, rebalance_conditions }
 */
export async function fetchBacktestConfig() {
    return get(API.BACKTEST_CONFIG);
}

/**
 * 執行回測（核心 API）
 * 
 * @param {Object} settings - 回測設定
 * @param {number} settings.initial_capital - 初始資金
 * @param {string} settings.start_date - 起始日期
 * @param {string} settings.end_date - 結束日期
 * @param {string} settings.rebalance_freq - 再平衡頻率 (daily/weekly/monthly)
 * @param {string} settings.market - 市場 (global/us/tw)
 * @param {number} settings.top_n - 每次買入數量
 * @param {Array<string>} settings.buy_conditions - 買入條件 (語意化鍵值)
 * @param {Array<string>} settings.sell_conditions - 賣出條件 (語意化鍵值)
 * @param {Object} settings.params - 條件參數
 * @returns {Promise<Object>} - { success, result: { metrics, equity_curve, trades } }
 */
export async function runBacktest(settings) {
    return post(API.BACKTEST_RUN, settings);
}
