/**
 * simulator.js - 交易模擬器 API
 * 
 * 封裝與股票價格相關的 API 呼叫
 */

import { get } from './client.js';
import { API } from '../config.js';

/**
 * 取得股票清單
 * @returns {Promise<Object>} - { stocks: Array }
 */
export async function fetchStocks() {
    return get(API.STOCKS);
}

/**
 * 取得指定日期的股票價格
 * @param {string} ticker - 股票代碼
 * @param {string} date - 日期 (YYYY-MM-DD)
 * @returns {Promise<Object>} - { open, high, low, close, country }
 */
export async function fetchStockPrice(ticker, date) {
    return get(`${API.STOCK_PRICE}/${ticker}?date=${date}`);
}
