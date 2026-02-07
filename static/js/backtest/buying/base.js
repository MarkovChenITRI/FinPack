/**
 * BuyConditionBase - 買入條件基類
 * 
 * 所有買入條件都必須繼承此類並實現 filter() 方法
 */

export class BuyConditionBase {
    /**
     * @param {string} id - 條件唯一識別碼
     * @param {string} name - 條件名稱
     * @param {string} description - 條件描述
     * @param {string} category - 分類 (A/B/C)
     */
    constructor(id, name, description, category = 'A') {
        this.id = id;
        this.name = name;
        this.description = description;
        this.category = category;  // A=範圍, B=動能, C=挑選
        this.enabled = false;
        this.params = {};
    }
    
    /**
     * 設定參數
     * @param {Object} params
     */
    setParams(params) {
        this.params = { ...this.params, ...params };
    }
    
    /**
     * 啟用/停用條件
     * @param {boolean} enabled
     */
    setEnabled(enabled) {
        this.enabled = enabled;
    }
    
    /**
     * 過濾股票（子類必須實現）
     * 
     * @param {string[]} tickers - 待過濾的股票列表
     * @param {Object} context - 上下文資料
     *   - date: 當前日期
     *   - ranking: {sharpe: {US: [], TW: []}, growth: {US: [], TW: []}}
     *   - stockInfo: {ticker: {country, industry}}
     *   - prices: {ticker: price}
     *   - history: 歷史排名資料
     * @returns {string[]} 過濾後的股票列表
     */
    filter(tickers, context) {
        throw new Error('filter() must be implemented by subclass');
    }
    
    /**
     * 取得預設參數（子類可覆寫）
     * @returns {Object}
     */
    getDefaultParams() {
        return {};
    }
    
    /**
     * 取得參數 UI 配置（子類可覆寫）
     * @returns {Array} [{id, label, type, min, max, step, default}]
     */
    getParamConfig() {
        return [];
    }
    
    /**
     * 驗證參數（子類可覆寫）
     * @returns {boolean}
     */
    validateParams() {
        return true;
    }
    
    /**
     * 取得條件資訊
     * @returns {Object}
     */
    getInfo() {
        return {
            id: this.id,
            name: this.name,
            description: this.description,
            category: this.category,
            enabled: this.enabled,
            params: this.params,
            paramConfig: this.getParamConfig()
        };
    }
}
