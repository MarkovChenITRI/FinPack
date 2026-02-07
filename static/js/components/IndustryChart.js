/**
 * IndustryBarChart - 產業分布柱狀圖 (Chart.js)
 * 
 * 職責：
 *   - init()            初始化橫向長條圖
 *   - loadData(mode, date)  從 industryDataCache 查表並更新圖表
 *   - updateChart(data)     繪製產業分布
 * 
 * 數據來源：industryDataCache.getTopAnalysis() (純查表，無 API)
 */
import { industryDataCache } from '../utils/cache.js';

export class IndustryBarChart {
    constructor(canvasId, legendId, dataType = 'sharpe', chartTitle = 'Sharpe') {
        this.canvasId = canvasId;
        this.legendId = legendId;
        this.dataType = dataType;  // 'sharpe' | 'slope'
        this.chartTitle = chartTitle;
        this.chart = null;
        this.currentMode = 'global';
        this.currentData = null;
    }

    init() {
        const ctx = document.getElementById(this.canvasId).getContext('2d');
        
        this.chart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: [],
                datasets: []
            },
            options: {
                indexAxis: 'y',  // 橫向
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: false  // 我們用自訂 legend
                    },
                    tooltip: {
                        backgroundColor: '#1a1f2a',
                        titleColor: '#e6edf3',
                        bodyColor: '#7d8590',
                        borderColor: '#2d333b',
                        borderWidth: 1,
                        cornerRadius: 8,
                        padding: 12,
                        callbacks: {
                            afterBody: (tooltipItems) => {
                                const item = tooltipItems[0];
                                const industryData = this.currentData?.industries?.[item.dataIndex];
                                if (!industryData) return '';
                                
                                // 根據 dataset 決定顯示哪個國家的股票
                                let stocks = [];
                                if (this.currentMode === 'global') {
                                    // 國際加權模式：根據滑鼠所在的 dataset 顯示對應國家
                                    const datasetLabel = item.dataset.label;
                                    if (datasetLabel === '美股') {
                                        stocks = industryData.US_stocks || [];
                                    } else if (datasetLabel === '台股') {
                                        stocks = industryData.TW_stocks || [];
                                    }
                                } else {
                                    // 單一國家模式：顯示所有股票
                                    stocks = industryData.stocks || [];
                                }
                                
                                if (stocks.length > 0) {
                                    return `股票: ${stocks.join(', ')}`;
                                }
                                return '';
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        stacked: true,
                        grid: {
                            color: '#21262d'
                        },
                        ticks: {
                            color: '#7d8590',
                            stepSize: 1
                        },
                        title: {
                            display: true,
                            text: 'Top 15 股票數量',
                            color: '#7d8590'
                        }
                    },
                    y: {
                        stacked: true,
                        grid: {
                            display: false
                        },
                        ticks: {
                            color: '#e6edf3',
                            font: {
                                size: 13
                            },
                            autoSkip: false  // 禁止自動跳過標籤
                        }
                    }
                }
            }
        });
    }

    /**
     * 從前端快取取得預計算結果並更新圖表（同步，無網路延遲）
     * @param {string} mode - 'global' | 'nasdaq' | 'twii'
     * @param {string|null} date - 日期，null 表示使用最新有效日期
     */
    loadData(mode, date = null) {
        this.currentMode = mode;
        this.currentDate = date;
        
        // 從前端快取取得預計算結果
        const data = industryDataCache.getTopAnalysis(date, mode, this.dataType);
        
        console.log(`📊 ${this.chartTitle} loadData:`, { 
            mode, 
            requestedDate: date, 
            actualDate: data?.date,
            industries: data?.industries?.length || 0 
        });
        
        this.currentData = data;
        this.updateChart(data, mode);
        this.updateLegend(mode);
    }

    updateChart(data, mode) {
        if (!data.industries || data.industries.length === 0) {
            this.chart.data.labels = ['無資料'];
            this.chart.data.datasets = [{
                data: [0],
                backgroundColor: '#545d68'
            }];
            this.chart.update();
            return;
        }

        const labels = data.industries.map(ind => ind.name);
        
        let datasets = [];
        
        if (mode === 'global') {
            // 國際加權：堆疊顯示 US 和 TW
            datasets = [
                {
                    label: '美股',
                    data: data.industries.map(ind => ind.US || 0),
                    backgroundColor: '#58a6ff',
                    borderRadius: 4
                },
                {
                    label: '台股',
                    data: data.industries.map(ind => ind.TW || 0),
                    backgroundColor: '#f59e0b',
                    borderRadius: 4
                }
            ];
        } else if (mode === 'nasdaq') {
            // 美股：藍色
            datasets = [{
                label: '美股',
                data: data.industries.map(ind => ind.total || 0),
                backgroundColor: '#58a6ff',
                borderRadius: 4
            }];
        } else if (mode === 'twii') {
            // 台股：橘色
            datasets = [{
                label: '台股',
                data: data.industries.map(ind => ind.total || 0),
                backgroundColor: '#f59e0b',
                borderRadius: 4
            }];
        }

        this.chart.data.labels = labels;
        this.chart.data.datasets = datasets;
        this.chart.update('none');
    }

    updateLegend(mode) {
        const legendContainer = document.getElementById(this.legendId);
        if (!legendContainer) return;
        
        if (mode === 'global') {
            legendContainer.innerHTML = `
                <div class="legend-item">
                    <span class="legend-color blue"></span>
                    <span>美股</span>
                </div>
                <div class="legend-item">
                    <span class="legend-color orange"></span>
                    <span>台股</span>
                </div>
            `;
        } else if (mode === 'nasdaq') {
            legendContainer.innerHTML = `
                <div class="legend-item">
                    <span class="legend-color blue"></span>
                    <span>美股</span>
                </div>
            `;
        } else if (mode === 'twii') {
            legendContainer.innerHTML = `
                <div class="legend-item">
                    <span class="legend-color orange"></span>
                    <span>台股</span>
                </div>
            `;
        }
    }

    destroy() {
        if (this.chart) {
            this.chart.destroy();
            this.chart = null;
        }
    }
}
