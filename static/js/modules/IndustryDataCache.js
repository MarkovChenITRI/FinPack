/**
 * 產業資料快取 - 完全預計算架構
 * 
 * 設計原則：
 * - 所有 Top 15 結果在 load() 時就預先計算完成
 * - 滑鼠移動時只是「查表」，零計算延遲
 * - 與 OHLC 標籤完全同步（都是純查表操作）
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
                slope: data.slope?.length || 0
            });
            
            const dates = data.dates || [];
            const tickers = data.tickers || [];
            const stockInfo = data.stockInfo || {};
            const sharpeMatrix = data.sharpe || [];
            const slopeMatrix = data.slope || [];
            
            if (dates.length === 0 || tickers.length === 0) {
                console.error('❌ 資料為空！');
                return;
            }
            
            this.dates = dates;
            
            // 預計算所有組合
            const modes = ['global', 'nasdaq', 'twii'];
            const dataTypes = ['sharpe', 'slope'];
            
            let computeCount = 0;
            for (const mode of modes) {
                // 先計算 sharpe（因為 slope 依賴 sharpe 的產業）
                dates.forEach((date, dateIdx) => {
                    const sharpeResult = this._computeTopN(
                        date, dateIdx, sharpeMatrix, tickers, stockInfo, mode, 'sharpe', 15, null
                    );
                    this.precomputed[mode]['sharpe'][date] = sharpeResult;
                    computeCount++;
                    
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
            // global 模式需要同時有 US 和 TW 資料
            for (const mode of modes) {
                for (let i = dates.length - 1; i >= 0; i--) {
                    const result = this.precomputed[mode]['sharpe'][dates[i]];
                    if (result && result.industries && result.industries.length > 0) {
                        // global 模式：確保同時有 US 和 TW 資料
                        if (mode === 'global') {
                            const hasUS = result.industries.some(ind => ind.US > 0);
                            const hasTW = result.industries.some(ind => ind.TW > 0);
                            if (hasUS && hasTW) {
                                this.latestValidDate[mode] = dates[i];
                                break;
                            }
                        } else {
                            this.latestValidDate[mode] = dates[i];
                            break;
                        }
                    }
                }
            }
            
            this.loaded = true;
            const elapsed = (performance.now() - startTime).toFixed(0);
            console.log(`✅ 產業資料預計算完成: ${computeCount} 組結果，耗時 ${elapsed}ms`);
            console.log('📅 各模式最新有效日期:', this.latestValidDate);
            
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
            return { date, industries: [], top_stocks: [] };
        }
        
        // 過濾出有效的股票
        const validStocks = [];
        tickers.forEach((ticker, idx) => {
            const value = row[idx];
            const info = stockInfo[ticker];
            if (!info) return;
            
            // 排除市場指數（^IXIC, ^TWII, GC=F, BTC-USD, TLT 等）
            if (info.industry === 'Market Index') return;
            
            // 根據 mode 過濾國家
            if (mode === 'nasdaq' && info.country !== 'US') return;
            if (mode === 'twii' && info.country !== 'TW') return;
            
            // 如果有產業過濾器，只保留符合的股票（用於 slope）
            if (industryFilter && !industryFilter.has(info.industry)) return;
            
            if (value !== null && value !== undefined && !isNaN(value) && value !== 0) {
                validStocks.push({ ticker, value, country: info.country, industry: info.industry });
            }
        });
        
        // 排序並取 Top N
        validStocks.sort((a, b) => b.value - a.value);
        const topStocks = validStocks.slice(0, topN);
        
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
                [dataType]: Math.round(s.value * (dataType === 'slope' ? 1000000 : 1000)) / (dataType === 'slope' ? 1000000 : 1000),
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
}

// 全域產業資料快取單例
export const industryDataCache = new IndustryDataCache();
