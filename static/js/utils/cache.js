/**
 * 產業資料快取 - 預計算 Top 15 柱狀圖數據
 * 
 * 職責：
 *   - load()      載入後端矩陣 + 預計算每日 Top 15
 *   - getTopAnalysis(date, mode, dataType)  查表取得預計算結果 (IndustryBarChart 使用)
 *   - getFullRanking(date, metric, mode)    保留供擴展使用 (回測由後端執行)
 * 
 * 數據來源：/api/industry/data → stock_cache.sharpe_matrix, slope_matrix
 */
export class IndustryDataCache {
    constructor() {
        this.loaded = false;
        this.dates = [];
        this.latestValidDate = {};  // 每個 mode 最新有效日期 {global: '2026-02-04', nasdaq: '2026-02-04', twii: '2026-02-05'}
        
        // 預計算的結果表：precomputed[mode][dataType][date] = result
        // mode: 'global' | 'nasdaq' | 'twii'
        // dataType: 'sharpe' | 'slope'
        this.precomputed = {
            global: { sharpe: {}, slope: {} },
            nasdaq: { sharpe: {}, slope: {} },
            twii: { sharpe: {}, slope: {} }
        };
        
        // 原始資料（供回測引擎查詢任意股票排名）
        this._tickers = [];
        this._stockInfo = {};
        this._sharpeMatrix = [];
        this._slopeMatrix = [];
        this._dateIndex = {};    // date -> index
        this._tickerIndex = {};  // ticker -> index
    }
    
    async load() {
        const startTime = performance.now();
        console.log('🔄 開始載入產業資料...');
        
        try {
            // 載入 6 年資料（指標計算需要 1 年，實際可用 5 年）
            const response = await fetch('/api/industry/data?period=6y');
            console.log('📥 API 回應狀態:', response.status);
            
            const data = await response.json();
            console.log('📊 收到資料:', {
                dates: data.dates?.length || 0,
                tickers: data.tickers?.length || 0,
                sharpe: data.sharpe?.length || 0,
                growth: data.growth?.length || 0,
                error: data.error || null
            });
            
            // 檢查 API 是否返回錯誤
            if (data.error) {
                console.error('❌ API 返回錯誤:', data.error);
                return;
            }
            
            const dates = data.dates || [];
            const tickers = data.tickers || [];
            const stockInfo = data.stockInfo || {};
            const sharpeMatrix = data.sharpe || [];
            const slopeMatrix = data.growth || [];  // API returns 'growth' for slope/growth rate
            
            // 額外檢查：顯示前5筆 stockInfo
            const infoEntries = Object.entries(stockInfo).slice(0, 5);
            console.log('📋 stockInfo 樣本:', infoEntries);
            
            // 統計 country 分布
            const countryStats = {};
            Object.values(stockInfo).forEach(info => {
                const country = info.country || '(empty)';
                countryStats[country] = (countryStats[country] || 0) + 1;
            });
            console.log('🌍 stockInfo country 分布:', countryStats);
            
            // 統計 industry 分布（前10個）
            const industryStats = {};
            Object.values(stockInfo).forEach(info => {
                const industry = info.industry || '(empty)';
                industryStats[industry] = (industryStats[industry] || 0) + 1;
            });
            const topIndustries = Object.entries(industryStats)
                .sort((a, b) => b[1] - a[1])
                .slice(0, 10);
            console.log('🏭 stockInfo industry 分布 (前10):', topIndustries);
            
            // 額外檢查：顯示最後一天的 sharpe 資料（非 null 值數量）
            if (sharpeMatrix.length > 0) {
                const lastRow = sharpeMatrix[sharpeMatrix.length - 1];
                const nonNullCount = lastRow.filter(v => v !== null && !isNaN(v)).length;
                console.log(`📈 最後一天 sharpe 資料: ${nonNullCount}/${lastRow.length} 個非空值`);
            }
            
            if (dates.length === 0 || tickers.length === 0) {
                console.error('❌ 資料為空！');
                return;
            }
            
            this.dates = dates;
            
            // 保留原始資料（供回測引擎查詢任意股票排名）
            this._tickers = tickers;
            this._stockInfo = stockInfo;
            this._sharpeMatrix = sharpeMatrix;
            this._slopeMatrix = slopeMatrix;
            
            // 建立日期索引（快速查找）
            this._dateIndex = {};
            dates.forEach((date, idx) => {
                this._dateIndex[date] = idx;
            });
            
            // 建立股票索引（快速查找）
            this._tickerIndex = {};
            tickers.forEach((ticker, idx) => {
                this._tickerIndex[ticker] = idx;
            });
            
            // 預計算所有組合
            const modes = ['global', 'nasdaq', 'twii'];
            
            // Debug: 確認數據在進入循環前是正確的
            console.log(`🔧 預計算前檢查:`);
            console.log(`   - dates: ${dates.length}, sharpeMatrix: ${sharpeMatrix.length} rows`);
            console.log(`   - sharpeMatrix[0] length: ${sharpeMatrix[0]?.length || 0}`);
            console.log(`   - sharpeMatrix[last] length: ${sharpeMatrix[sharpeMatrix.length-1]?.length || 0}`);
            if (sharpeMatrix.length > 0 && sharpeMatrix[sharpeMatrix.length-1]) {
                const lastRow = sharpeMatrix[sharpeMatrix.length-1];
                const nonNullCount = lastRow.filter(v => v !== null).length;
                console.log(`   - 最後一行非 null 值: ${nonNullCount}/${lastRow.length}`);
            }
            
            let computeCount = 0;
            let firstResult = null;
            for (const mode of modes) {
                // 先計算 sharpe（因為 slope 依賴 sharpe 的產業）
                dates.forEach((date, dateIdx) => {
                    const sharpeResult = this._computeTopN(
                        date, dateIdx, sharpeMatrix, tickers, stockInfo, mode, 'sharpe', 15, null
                    );
                    this.precomputed[mode]['sharpe'][date] = sharpeResult;
                    computeCount++;
                    
                    // 記錄第一個結果
                    if (!firstResult && mode === 'global' && dateIdx === dates.length - 1) {
                        firstResult = sharpeResult;
                        console.log(`🧪 第一個 global sharpe 結果 (${date}):`, {
                            industries: sharpeResult.industries.length,
                            top_stocks: sharpeResult.top_stocks.length,
                            firstIndustry: sharpeResult.industries[0]
                        });
                    }
                    
                    // 計算 slope，限制在 sharpe top 產業內
                    const sharpeTopIndustries = new Set(sharpeResult.industries.map(ind => ind.name));
                    const slopeResult = this._computeTopN(
                        date, dateIdx, slopeMatrix, tickers, stockInfo, mode, 'slope', 15, sharpeTopIndustries
                    );
                    slopeResult.sharpe_top_industries = [...sharpeTopIndustries];
                    this.precomputed[mode]['slope'][date] = slopeResult;
                    computeCount++;
                });
            }
            
            // 找出每個 mode 最新的有效日期（有產業資料的日期）
            for (const mode of modes) {
                for (let i = dates.length - 1; i >= 0; i--) {
                    const result = this.precomputed[mode]['sharpe'][dates[i]];
                    if (result && result.industries && result.industries.length > 0) {
                        this.latestValidDate[mode] = dates[i];
                        break;
                    }
                }
                // 如果找不到有效日期，使用最後一天作為 fallback
                if (!this.latestValidDate[mode] && dates.length > 0) {
                    this.latestValidDate[mode] = dates[dates.length - 1];
                    console.warn(`⚠️ ${mode} 模式找不到有效日期，使用最後一天: ${this.latestValidDate[mode]}`);
                }
            }
            
            this.loaded = true;
            const elapsed = (performance.now() - startTime).toFixed(0);
            console.log(`✅ 產業資料預計算完成: ${computeCount} 組結果，耗時 ${elapsed}ms`);
            console.log('📅 各模式最新有效日期:', this.latestValidDate);
            
            // Debug: 輸出最後一天的 precomputed 結果
            const lastDate = dates[dates.length - 1];
            const globalSharpe = this.precomputed['global']['sharpe'][lastDate];
            console.log(`📊 最後一天 (${lastDate}) global sharpe:`, {
                industries: globalSharpe?.industries?.length || 0,
                top_stocks: globalSharpe?.top_stocks?.length || 0,
                firstIndustry: globalSharpe?.industries?.[0] || null
            });
            
        } catch (error) {
            console.error('❌ 載入產業資料失敗:', error);
        }
    }
    
    /**
     * 計算單一日期的 Top N（僅在 load() 時呼叫）
     * @param {Set|null} industryFilter - 產業過濾器，僅包含這些產業的股票（用於 slope）
     */
    _computeTopN(date, dateIdx, matrix, tickers, stockInfo, mode, dataType, topN, industryFilter = null) {
        const row = matrix[dateIdx];
        if (!row) {
            console.warn(`⚠️ _computeTopN: ${date} (idx=${dateIdx}) 沒有 ${dataType} row 資料`);
            return { date, industries: [], top_stocks: [] };
        }
        
        // 第一次計算時（第一天、global、sharpe）或最後一天輸出詳細 debug
        const isFirstDebug = (dateIdx === 0 && mode === 'global' && dataType === 'sharpe');
        const isLastDebug = (dateIdx === matrix.length - 1 && mode === 'global' && dataType === 'sharpe');
        if (isFirstDebug || isLastDebug) {
            console.log(`🔬 _computeTopN debug (${isFirstDebug ? '首日' : '末日'}, ${mode}, ${dataType}):`);
            console.log(`   - date: ${date}`);
            console.log(`   - row length: ${row.length}`);
            console.log(`   - tickers length: ${tickers.length}`);
            console.log(`   - stockInfo keys: ${Object.keys(stockInfo).length}`);
            console.log(`   - 前5個 ticker: ${tickers.slice(0, 5)}`);
            console.log(`   - 前5個 row value: ${row.slice(0, 5)}`);
            // 檢查 tickers 和 stockInfo 是否匹配
            const matchCount = tickers.filter(t => stockInfo[t]).length;
            console.log(`   - ticker 在 stockInfo 中有資料: ${matchCount}/${tickers.length}`);
            // 顯示前5個非 null 的值
            const nonNullValues = row.map((v, i) => ({ ticker: tickers[i], value: v }))
                .filter(x => x.value !== null && !Number.isNaN(x.value))
                .slice(0, 5);
            console.log(`   - 前5個非 null 值:`, nonNullValues);
        }
        
        // 過濾出有效的股票
        const validStocks = [];
        let debugSkipped = { noInfo: 0, marketIndex: 0, wrongCountry: 0, wrongIndustry: 0, nullValue: 0, zeroSharpe: 0 };
        
        tickers.forEach((ticker, idx) => {
            const value = row[idx];
            const info = stockInfo[ticker];
            if (!info) {
                debugSkipped.noInfo++;
                // 輸出第一個 missing 的 ticker（debug）
                if (debugSkipped.noInfo === 1 && (isFirstDebug || isLastDebug)) {
                    console.log(`   - 第一個 missing ticker: "${ticker}" (idx=${idx})`);
                    console.log(`   - stockInfo 的前5個 key: ${Object.keys(stockInfo).slice(0, 5)}`);
                }
                return;
            }
            
            // 排除市場指數（^IXIC, ^TWII, GC=F, BTC-USD, TLT 等）
            if (info.industry === 'Market Index') {
                debugSkipped.marketIndex++;
                return;
            }
            
            // 根據 mode 過濾國家
            if (mode === 'nasdaq' && info.country !== 'US') {
                debugSkipped.wrongCountry++;
                return;
            }
            if (mode === 'twii' && info.country !== 'TW') {
                debugSkipped.wrongCountry++;
                return;
            }
            
            // 如果有產業過濾器，只保留符合的股票（用於 slope）
            if (industryFilter && !industryFilter.has(info.industry)) {
                debugSkipped.wrongIndustry++;
                return;
            }
            
            // 過濾無效值（null, undefined, NaN）
            // 注意：0 對於 slope 是有效值（排名不變），但對於 sharpe 可能無意義
            if (value === null || value === undefined || Number.isNaN(value)) {
                debugSkipped.nullValue++;
                return;
            }
            // 移除 sharpe === 0 的過濾，因為 0 也是有效的 sharpe 值
            
            validStocks.push({ ticker, value, country: info.country, industry: info.industry });
        });
        
        // 排序並取 Top N
        validStocks.sort((a, b) => b.value - a.value);
        const topStocks = validStocks.slice(0, topN);
        
        // Debug log（對最後一天的所有模式輸出）
        if (dateIdx === matrix.length - 1) {
            console.log(`🔍 _computeTopN (${date}, ${mode}, ${dataType}):`, {
                validStocks: validStocks.length,
                skipped: debugSkipped
            });
            // 如果 validStocks 為空，輸出警告
            if (validStocks.length === 0) {
                console.error(`❌ ${mode} ${dataType} 最後一天沒有 validStocks！`, debugSkipped);
            }
        }
        
        // 統計產業分布
        const industryStats = {};
        topStocks.forEach(stock => {
            const industry = stock.industry || '未分類';
            if (!industryStats[industry]) {
                industryStats[industry] = {
                    total: 0, US: 0, TW: 0,
                    stocks: [], US_stocks: [], TW_stocks: []
                };
            }
            industryStats[industry].total++;
            industryStats[industry].stocks.push(stock.ticker);
            
            if (stock.country === 'US') {
                industryStats[industry].US++;
                industryStats[industry].US_stocks.push(stock.ticker);
            } else if (stock.country === 'TW') {
                industryStats[industry].TW++;
                industryStats[industry].TW_stocks.push(stock.ticker);
            }
        });
        
        // 轉換為陣列並排序
        const industries = Object.entries(industryStats)
            .map(([name, stats]) => ({ name, ...stats }))
            .sort((a, b) => b.total - a.total);
        
        return {
            date,
            industries,
            top_stocks: topStocks.map(s => ({
                ticker: s.ticker,
                // slope 現在是「排名變化」（整數），sharpe 仍保持3位小數
                [dataType]: dataType === 'slope' 
                    ? Math.round(s.value)  // 排名變化：整數（+10 = 排名上升 10 位）
                    : Math.round(s.value * 1000) / 1000,  // Sharpe：3位小數
                country: s.country,
                industry: s.industry
            }))
        };
    }
    
    /**
     * 取得預計算的 Top N 結果（純查表，零計算）
     * @param {string|null} date - 日期，null 表示使用該 mode 最新有效日期
     * @param {string} mode - 'global' | 'nasdaq' | 'twii'
     * @param {string} dataType - 'sharpe' | 'slope'
     */
    getTopAnalysis(date, mode, dataType = 'sharpe') {
        if (!this.loaded) {
            console.warn('⚠️ getTopAnalysis: 快取尚未載入');
            return { date: null, industries: [], top_stocks: [] };
        }
        
        // 如果沒有指定日期，使用該 mode 最新有效日期
        if (!date) {
            date = this.latestValidDate[mode];
        }
        
        // 直接查表
        let result = this.precomputed[mode]?.[dataType]?.[date];
        
        // 如果該日期沒有資料（可能該市場當天沒開盤），往前找
        if ((!result || result.industries.length === 0) && this.dates.length > 0) {
            const dateIdx = this.dates.indexOf(date);
            if (dateIdx > 0) {
                // 往前找最近一個有資料的日期
                for (let i = dateIdx - 1; i >= Math.max(0, dateIdx - 5); i--) {
                    const prevDate = this.dates[i];
                    const prevResult = this.precomputed[mode]?.[dataType]?.[prevDate];
                    if (prevResult && prevResult.industries.length > 0) {
                        result = prevResult;
                        break;
                    }
                }
            }
            
            // 如果還是沒有，使用該 mode 最新有效日期
            if (!result || result.industries.length === 0) {
                const fallbackDate = this.latestValidDate[mode];
                result = this.precomputed[mode]?.[dataType]?.[fallbackDate];
            }
        }
        
        return result || { date: null, industries: [], top_stocks: [] };
    }
    
    // =========================================================================
    // 回測引擎專用方法（查詢任意股票的排名）
    // =========================================================================
    
    /**
     * 取得特定日期、特定股票的指標值和排名
     * @param {string} date - 日期 YYYY-MM-DD
     * @param {string} ticker - 股票代碼
     * @param {string} metric - 'sharpe' | 'growth'
     * @param {string} mode - 'global' | 'nasdaq' | 'twii'
     * @returns {{ value: number, rank: number } | null}
     */
    getStockMetric(date, ticker, metric = 'sharpe', mode = 'global') {
        if (!this.loaded) return null;
        
        const dateIdx = this._dateIndex[date];
        const tickerIdx = this._tickerIndex[ticker];
        
        if (dateIdx === undefined || tickerIdx === undefined) return null;
        
        const matrix = metric === 'growth' ? this._slopeMatrix : this._sharpeMatrix;
        const row = matrix[dateIdx];
        if (!row) return null;
        
        const value = row[tickerIdx];
        if (value === null || value === undefined || isNaN(value)) return null;
        
        // 計算該股票在當日的排名
        // 先收集同模式下所有有效股票的值
        const validStocks = [];
        this._tickers.forEach((t, idx) => {
            const info = this._stockInfo[t];
            if (!info) return;
            if (info.industry === 'Market Index') return;
            if (mode === 'nasdaq' && info.country !== 'US') return;
            if (mode === 'twii' && info.country !== 'TW') return;
            
            const v = row[idx];
            if (v !== null && v !== undefined && !isNaN(v)) {
                validStocks.push({ ticker: t, value: v });
            }
        });
        
        // 排序（值大的排名靠前）
        validStocks.sort((a, b) => b.value - a.value);
        
        // 找出目標股票的排名
        const rank = validStocks.findIndex(s => s.ticker === ticker) + 1;
        
        return { value, rank: rank || 999 };
    }
    
    /**
     * 取得特定日期的完整排名表（所有股票）
     * @param {string} date - 日期 YYYY-MM-DD
     * @param {string} metric - 'sharpe' | 'growth'
     * @param {string} mode - 'global' | 'nasdaq' | 'twii'
     * @returns {Map<string, { value: number, rank: number }>}
     */
    getFullRanking(date, metric = 'sharpe', mode = 'global') {
        if (!this.loaded) return new Map();
        
        const dateIdx = this._dateIndex[date];
        if (dateIdx === undefined) return new Map();
        
        const matrix = metric === 'growth' ? this._slopeMatrix : this._sharpeMatrix;
        const row = matrix[dateIdx];
        if (!row) return new Map();
        
        // 收集同模式下所有有效股票
        const validStocks = [];
        this._tickers.forEach((ticker, idx) => {
            const info = this._stockInfo[ticker];
            if (!info) return;
            if (info.industry === 'Market Index') return;
            if (mode === 'nasdaq' && info.country !== 'US') return;
            if (mode === 'twii' && info.country !== 'TW') return;
            
            const value = row[idx];
            if (value !== null && value !== undefined && !isNaN(value)) {
                validStocks.push({ ticker, value });
            }
        });
        
        // 排序（值大的排名靠前）
        validStocks.sort((a, b) => b.value - a.value);
        
        // 建立排名 Map
        const rankingMap = new Map();
        validStocks.forEach((stock, idx) => {
            rankingMap.set(stock.ticker, { value: stock.value, rank: idx + 1 });
        });
        
        return rankingMap;
    }
    
    /**
     * 取得股票資訊
     * @param {string} ticker
     * @returns {{ country: string, industry: string } | null}
     */
    getStockInfo(ticker) {
        return this._stockInfo[ticker] || null;
    }
}

// 全域產業資料快取單例
export const industryDataCache = new IndustryDataCache();
