/**
 * api/btc.js — BTC K 線與 SMC 信號 API
 */
import { get } from './client.js';
import { API } from '../config.js';

export async function fetchKline(timeframe = '1d', period = '2y') {
    return get(`${API.KLINE}?timeframe=${timeframe}&period=${period}`);
}

export async function fetchSignals(timeframe = '1d') {
    return get(`${API.SIGNALS}?timeframe=${timeframe}`);
}

export async function fetchMarketStatus() {
    return get(API.MARKET_STATUS);
}
