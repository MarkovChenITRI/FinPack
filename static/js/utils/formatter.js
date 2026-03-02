/**
 * formatter.js — BTC SMC 數字格式化工具
 */

export function formatUSD(value, decimals = 2) {
    return `$${Number(value).toLocaleString('en-US', {
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals,
    })}`;
}

export function formatPercent(value, decimals = 2, showSign = false) {
    const n = Number(value);
    const sign = showSign && n > 0 ? '+' : '';
    return `${sign}${n.toFixed(decimals)}%`;
}

export function formatDate(date) {
    if (typeof date === 'string') return date.slice(0, 10);
    const d = new Date(date);
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    return `${y}-${m}-${day}`;
}

export function formatBTC(value) {
    return `${Number(value).toFixed(6)} BTC`;
}

/** 將方向轉為中文 */
export function formatDirection(dir) {
    return dir === 'long' ? 'Long (多)' : 'Short (空)';
}

/** 根據正負值設定樣式類名 */
export function signClass(value) {
    return Number(value) >= 0 ? 'positive' : 'negative';
}
