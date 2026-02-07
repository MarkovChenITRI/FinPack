/**
 * stock.js - 股票數據 API
 * 
 * 對應後端路由：engine/routes/stock.py
 */

import { get } from './client.js';
import { API } from '../config.js';

/**
 * 取得股票清單
 * @returns {Promise<Object>} - { stocks: Array<{ticker, country, industry}> }
 */
export async function fetchStocks() {
    return get(API.STOCKS);
}

/**
 * 取得股票價格
 * @param {string} ticker - 股票代碼
 * @param {string} date - 日期 (YYYY-MM-DD)
 * @returns {Promise<Object>} - { open, high, low, close, country }
 */
export async function fetchStockPrice(ticker, date) {
    return get(`${API.STOCK_PRICE}/${ticker}?date=${date}`);
}

/**
 * 取得產業分析數據（Sharpe/Slope 矩陣）
 * @param {string} period - 時間範圍
 * @returns {Promise<Object>} - { dates, tickers, stockInfo, sharpe, slope }
 */
export async function fetchIndustryData(period = '6y') {
    return get(`${API.INDUSTRY_DATA}?period=${period}`);
}
