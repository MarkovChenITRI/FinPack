/**
 * RebalanceStrategyBase - 再平衡策略基類
 * 
 * 所有再平衡策略都必須繼承此類並實現 shouldRebalance() 和 execute() 方法
 */

export class RebalanceStrategyBase {
    /**
     * @param {string} id - 策略唯一識別碼
     * @param {string} name - 策略名稱
     * @param {string} description - 策略描述
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
     * 啟用/停用策略
     * @param {boolean} enabled
     */
    setEnabled(enabled) {
        this.enabled = enabled;
    }
    
    /**
     * 判斷是否應該進行再平衡（子類必須實現）
     * 
     * @param {Object} context - 上下文資料
     *   - date: 當前日期
     *   - lastRebalanceDate: 上次再平衡日期
     *   - currentHoldings: 當前持倉
     *   - targetStocks: 目標股票列表
     * @returns {boolean}
     */
    shouldRebalance(context) {
        throw new Error('shouldRebalance() must be implemented by subclass');
    }
    
    /**
     * 執行再平衡（子類可覆寫）
     * 
     * @param {Object} trade - Trade 實例
     * @param {string[]} targetStocks - 目標股票列表
     * @param {Object} prices - 價格資料
     * @param {Object} stockInfo - 股票資訊
     * @param {string} date - 日期
     * @param {Object} options - 選項 (exchangeRate 等)
     * @returns {Object} {sells: [], buys: []}
     */
    execute(trade, targetStocks, prices, stockInfo, date, options = {}) {
        return trade.executeRebalance(targetStocks, prices, stockInfo, date, options);
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
     * 取得策略資訊
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
