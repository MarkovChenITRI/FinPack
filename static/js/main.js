/**
 * FinPack 主入口點
 * 使用 ES Modules 載入所有模組
 */
import { FinPackApp } from './modules/FinPackApp.js';

// 初始化應用程式
document.addEventListener('DOMContentLoaded', () => {
    window.finPackApp = new FinPackApp();
    window.finPackApp.init();
});
