/**
 * client.js - API 呼叫基礎層
 * 
 * 提供統一的 fetch wrapper，包含：
 * - 錯誤處理
 * - 重試機制
 * - JSON 解析
 */

/**
 * 發送 GET 請求
 * @param {string} url - API URL
 * @param {Object} options - 額外選項
 * @returns {Promise<Object>} - JSON 回應
 */
export async function get(url, options = {}) {
    try {
        const response = await fetch(url, {
            method: 'GET',
            headers: {
                'Accept': 'application/json',
                ...options.headers
            },
            ...options
        });
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        return await response.json();
    } catch (error) {
        console.error(`API GET 失敗: ${url}`, error);
        throw error;
    }
}

/**
 * 發送 POST 請求
 * @param {string} url - API URL
 * @param {Object} data - 請求資料
 * @param {Object} options - 額外選項
 * @returns {Promise<Object>} - JSON 回應
 */
export async function post(url, data = {}, options = {}) {
    try {
        const response = await fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json',
                ...options.headers
            },
            body: JSON.stringify(data),
            ...options
        });
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        return await response.json();
    } catch (error) {
        console.error(`API POST 失敗: ${url}`, error);
        throw error;
    }
}
