/**
 * config.js - 前端配置中心
 * 
 * 統一定義：
 *   - API 端點路徑
 *   - 預設參數
 *   - 常數定義
 */

// ===== API 端點 =====
export const API = {
    // 市場數據
    MARKET_DATA: '/api/market-data',
    EXCHANGE_RATE: '/api/exchange-rate',
    
    // 股票數據
    STOCKS: '/api/stocks',
    STOCK_PRICE: '/api/stock-price',  // + /{ticker}?date={date}
    INDUSTRY_DATA: '/api/industry/data',
    
    // 回測相關
    BACKTEST_RUN: '/api/backtest/run',
    BACKTEST_CONFIG: '/api/backtest/config',
    BACKTEST_PRICES: '/api/backtest/prices'
};

// ===== 預設參數 =====
export const DEFAULTS = {
    INITIAL_CAPITAL: 1000000,
    EXCHANGE_RATE: 32.0,
    TOP_N: 15,
    AMOUNT_PER_STOCK: 100000,
    MAX_POSITIONS: 10
};

// ===== 常數定義 =====
// 不可交易的產業類型（由 TradingView 分類決定）
export const NON_TRADABLE_INDUSTRIES = new Set(['Market Index', 'Index']);
