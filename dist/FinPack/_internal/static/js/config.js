/**
 * config.js - API 端點配置
 * 
 * 統一定義所有後端 API 路徑，方便維護與修改
 */

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

export const DEFAULTS = {
    INITIAL_CAPITAL: 1000000,
    EXCHANGE_RATE: 32.0,
    TOP_N: 15
};
