/**
 * config.js — BTC SMC 前端配置
 *
 * 本檔案只定義：
 *   API 端點路徑、圖表 UI 常數、視覺顏色
 *
 * ⚠️ 回測業務邏輯的預設值（initial_capital、leverage、risk_per_trade 等）
 *    統一由後端 DEFAULT_SMC_CONFIG (backtest/smc_config.py) 管理，
 *    前端透過 GET /api/backtest/config 取得，不在此重複定義。
 */

export const API = {
    HEALTH:          '/api/health',
    KLINE:           '/api/kline/btc',
    MARKET_STATUS:   '/api/market-status',
    SIGNALS:         '/api/btc/signals',
    BACKTEST_RUN:    '/api/backtest/run',
    BACKTEST_CONFIG: '/api/backtest/config',
};

/** 僅限 K 線圖 UI 的預設值（與回測業務邏輯無關） */
export const UI = {
    TIMEFRAME: '1d',   // 圖表預設 timeframe
    PERIOD:    '2y',   // 圖表預設顯示期間
};

export const SIGNAL_COLORS = {
    BOS_BULL:   '#26a69a',
    BOS_BEAR:   '#ef5350',
    CHOCH_BULL: '#00bcd4',
    CHOCH_BEAR: '#ff9800',
    FVG_BULL:   'rgba(38, 166, 154, 0.15)',
    FVG_BEAR:   'rgba(239, 83, 80, 0.15)',
    OB_BULL:    'rgba(38, 166, 154, 0.25)',
    OB_BEAR:    'rgba(239, 83, 80, 0.25)',
    LP_BUY:     '#00bcd4',
    LP_SELL:    '#ff9800',
};
