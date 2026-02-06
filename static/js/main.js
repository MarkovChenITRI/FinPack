/**
 * main.js - 前端入口點
 * 
 * 資料流：
 *   DOMContentLoaded → FinPackApp.init()
 *     → 載入 K 線數據 (MarketChart)
 *     → 載入 Sharpe/Slope 矩陣 (IndustryDataCache)
 *     → 初始化柱狀圖 (IndustryBarChart)
 *     → 初始化交易模擬器/回測引擎
 */
import { FinPackApp } from './modules/FinPackApp.js';

// 初始化應用程式
document.addEventListener('DOMContentLoaded', () => {
    window.finPackApp = new FinPackApp();
    window.finPackApp.init();
});
