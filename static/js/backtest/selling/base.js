/**
 * SellConditionBase - 賣出條件基類
 * 
 * 所有賣出條件都必須繼承此類並實現 check() 方法
 */

export class SellConditionBase {
    /**
     * @param {string} id - 條件唯一識別碼
     * @param {string} name - 條件名稱
     * @param {string} description - 條件描述
     */
    constructor(id, name, description) {
        this.id = id;
        this.name = name;
        this.description = description;
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
     * 檢查是否應該賣出（子類必須實現）
     * 
     * @param {string} ticker - 股票代碼
     * @param {Object} position - 持倉資訊 {shares, avgCost, country, entryDate}
     * @param {Object} context - 上下文資料
     *   - date: 當前日期
     *   - price: 當前價格
     *   - ranking: 排名資料
     *   - history: 歷史資料
     *   - stockInfo: 股票資訊
     * @returns {Object} {shouldSell: boolean, reason: string}
     */
    check(ticker, position, context) {
        throw new Error('check() must be implemented by subclass');
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
     * @returns {Array}
     */
    getParamConfig() {
        return [];
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
            enabled: this.enabled,
            params: this.params,
            paramConfig: this.getParamConfig()
        };
    }
}
