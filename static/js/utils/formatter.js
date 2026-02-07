/**
 * formatter.js - 數字格式化工具
 */

/**
 * 格式化金額（台幣）
 * @param {number} value - 金額
 * @returns {string} - 格式化後的字串
 */
export function formatTWD(value) {
    return `$${value.toLocaleString('zh-TW', { maximumFractionDigits: 0 })}`;
}

/**
 * 格式化百分比
 * @param {number} value - 數值
 * @param {number} decimals - 小數位數
 * @returns {string} - 格式化後的字串
 */
export function formatPercent(value, decimals = 2) {
    return `${value.toFixed(decimals)}%`;
}

/**
 * 格式化股數（去除尾部零）
 * @param {number} value - 股數
 * @returns {string} - 格式化後的字串
 */
export function formatShares(value) {
    return value.toFixed(4).replace(/\.?0+$/, '');
}

/**
 * 格式化日期
 * @param {Date|string} date - 日期
 * @returns {string} - YYYY-MM-DD 格式
 */
export function formatDate(date) {
    if (typeof date === 'string') return date;
    const d = new Date(date);
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    return `${y}-${m}-${day}`;
}
