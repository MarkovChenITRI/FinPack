/**
 * Data API - 統一的數據獲取接口
 * 
 * 整合所有後端 API 呼叫，提供簡潔的前端數據接口
 */

const API_BASE = '';

/**
 * 通用 API 請求
 */
async function apiRequest(endpoint, options = {}) {
    const response = await fetch(`${API_BASE}${endpoint}`, {
        headers: {
            'Content-Type': 'application/json',
            ...options.headers
        },
        ...options
    });
    
    if (!response.ok) {
        throw new Error(`API Error: ${response.status}`);
    }
    
    return response.json();
}

// ===== 市場數據 =====

/**
 * 取得市場 K 線數據
 * @param {string} period - 時間範圍 (1y, 2y, 5y)
 */
export async function getMarketData(period = '1y') {
    return apiRequest(`/api/market-data?period=${period}`);
}

/**
 * 取得指定標的 K 線
 * @param {string} symbol
 * @param {string} period
 */
export async function getKline(symbol, period = '1y') {
    return apiRequest(`/api/kline/${symbol}?period=${period}`);
}

/**
 * 取得匯率
 */
export async function getExchangeRate() {
    return apiRequest('/api/exchange-rate');
}

// ===== 股票數據 =====

/**
 * 取得股票列表
 * @param {Object} options - {country, industry}
 */
export async function getStocks(options = {}) {
    const params = new URLSearchParams();
    if (options.country) params.set('country', options.country);
    if (options.industry) params.set('industry', options.industry);
    
    const query = params.toString();
    return apiRequest(`/api/stocks${query ? '?' + query : ''}`);
}

/**
 * 取得產業列表
 */
export async function getIndustries() {
    return apiRequest('/api/stocks/industries');
}

/**
 * 取得單一股票 Sharpe 數據
 * @param {string} ticker
 */
export async function getStockSharpe(ticker) {
    return apiRequest(`/api/stocks/${ticker}/sharpe`);
}

/**
 * 取得股票價格
 * @param {string} ticker
 * @param {string} date
 */
export async function getStockPrice(ticker, date) {
    return apiRequest(`/api/stock-price/${ticker}?date=${date}`);
}

// ===== 產業分析數據 =====

/**
 * 取得完整產業分析數據（含排名）
 * @param {string} period
 */
export async function getIndustryData(period = '1y') {
    return apiRequest(`/api/industry/data?period=${period}`);
}

/**
 * 取得 Sharpe Top N 分析
 * @param {Object} options - {country, top, date}
 */
export async function getIndustryTop(options = {}) {
    const params = new URLSearchParams();
    if (options.country) params.set('country', options.country);
    if (options.top) params.set('top', options.top);
    if (options.date) params.set('date', options.date);
    
    const query = params.toString();
    return apiRequest(`/api/industry/top${query ? '?' + query : ''}`);
}

/**
 * 取得 Growth Top N 分析
 * @param {Object} options - {country, top, date}
 */
export async function getIndustryGrowthTop(options = {}) {
    const params = new URLSearchParams();
    if (options.country) params.set('country', options.country);
    if (options.top) params.set('top', options.top);
    if (options.date) params.set('date', options.date);
    
    const query = params.toString();
    return apiRequest(`/api/industry/slope-top${query ? '?' + query : ''}`);
}

// ===== 回測數據 =====

/**
 * 取得回測用價格數據
 * @param {string} period
 */
export async function getBacktestPrices(period = '2y') {
    return apiRequest(`/api/backtest/prices?period=${period}`);
}

/**
 * 取得完整回測數據包
 * @param {string} period
 * @returns {Object} 包含所有回測需要的數據
 */
export async function getBacktestDataBundle(period = '2y') {
    const [industryData, pricesData] = await Promise.all([
        getIndustryData(period),
        getBacktestPrices(period)
    ]);
    
    return {
        dates: industryData.dates,
        stockInfo: industryData.stockInfo,
        sharpeRank: industryData.sharpeRank,
        growthRank: industryData.growthRank,
        prices: pricesData.prices,
        sharpeValues: matrixToDateMap(industryData.sharpe, industryData.dates, industryData.tickers),
        growthValues: matrixToDateMap(industryData.growth, industryData.dates, industryData.tickers)
    };
}

// ===== 系統 =====

/**
 * 健康檢查
 */
export async function healthCheck() {
    return apiRequest('/api/health');
}

/**
 * 重新整理快取
 */
export async function refreshCache() {
    return apiRequest('/api/cache/refresh', { method: 'POST' });
}

// ===== 輔助函數 =====

/**
 * 將矩陣格式轉換為 {date: {ticker: value}}
 */
function matrixToDateMap(matrix, dates, tickers) {
    const result = {};
    if (!matrix || !dates || !tickers) return result;
    
    for (let i = 0; i < dates.length; i++) {
        result[dates[i]] = {};
        for (let j = 0; j < tickers.length; j++) {
            if (matrix[i]?.[j] !== undefined && matrix[i][j] !== null) {
                result[dates[i]][tickers[j]] = matrix[i][j];
            }
        }
    }
    return result;
}

// ===== 數據快取 =====

class DataCache {
    constructor() {
        this._cache = new Map();
        this._ttl = 5 * 60 * 1000;  // 5 分鐘
    }
    
    async get(key, fetcher) {
        const cached = this._cache.get(key);
        if (cached && Date.now() - cached.time < this._ttl) {
            return cached.data;
        }
        
        const data = await fetcher();
        this._cache.set(key, { data, time: Date.now() });
        return data;
    }
    
    clear() {
        this._cache.clear();
    }
}

export const dataCache = new DataCache();

/**
 * 帶快取的數據獲取
 */
export async function getCachedIndustryData(period = '1y') {
    return dataCache.get(`industry_${period}`, () => getIndustryData(period));
}

export async function getCachedStocks() {
    return dataCache.get('stocks', getStocks);
}
