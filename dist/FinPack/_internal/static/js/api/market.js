/**
 * market.js - 市場數據 API
 * 
 * 對應後端路由：engine/routes/market.py
 */

import { get } from './client.js';
import { API } from '../config.js';

/**
 * 取得市場 K 線數據
 * @param {string} period - 時間範圍 (3mo, 6mo, 1y, 2y, 5y)
 * @returns {Promise<Object>} - { global, nasdaq, twii, gold, btc, bonds }
 */
export async function fetchMarketData(period = '1y') {
    return get(`${API.MARKET_DATA}?period=${period}`);
}

/**
 * 取得匯率
 * @returns {Promise<Object>} - { rate: number }
 */
export async function fetchExchangeRate() {
    return get(API.EXCHANGE_RATE);
}
