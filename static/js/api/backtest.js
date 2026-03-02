/**
 * api/backtest.js — SMC 合約回測 API
 */
import { get, post } from './client.js';
import { API } from '../config.js';

export async function fetchBacktestConfig() {
    return get(API.BACKTEST_CONFIG);
}

/**
 * 執行 SMC 合約回測
 * @param {Object} params — 回測參數（符合 /api/backtest/run schema）
 */
export async function runBacktest(params) {
    return post(API.BACKTEST_RUN, params);
}
