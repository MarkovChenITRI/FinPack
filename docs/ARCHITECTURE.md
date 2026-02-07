# FinPack 架構設計 v2（前端計算版）

## 設計理念

**計算前置化**：將回測、模擬等計算邏輯移至前端執行，後端只負責提供原始資料。

**插件化條件**：每個買入/賣出/再平衡條件為獨立 `.js` 檔案，透過註冊表統一管理。

**優點**：
- 避免大量資料來回傳輸
- 用戶調整參數後可即時重跑，無網路延遲
- 條件模組化，易於新增/修改單一策略
- 後端架構精簡，維護容易

---

## 目錄結構

```
this-repository/
├── main.py                    # Flask 入口：初始化 DataContainer、註冊路由
│
├── src/                       # 📦 資料基礎設施層
│   ├── __init__.py            # DataContainer（Singleton）
│   ├── config.py              # 股票清單、快取路徑等配置
│   ├── data.py                # yfinance 抓取 + pickle 快取
│   ├── align.py               # 日期對齊（bfill）
│   └── indicator.py           # 指標計算：sharpe_matrix, growth_matrix
│
├── routes/                    # 🌐 API 路由層（僅提供資料）
│   ├── __init__.py            # register_blueprints(app)
│   ├── market.py              # /api/market-data, /api/kline/<symbol>
│   └── stock.py               # /api/stocks, /api/industry/data, /api/backtest/prices
│
├── templates/
│   └── index.html             # SPA 單頁入口
│
└── static/
    ├── css/
    │   ├── base.css           # 變數、reset、typography
    │   ├── layout.css         # Grid/Flex 版面
    │   └── components/
    │       ├── charts.css
    │       ├── forms.css
    │       └── tables.css
    │
    └── js/
        ├── app.js             # 應用入口：初始化、事件綁定
        ├── config.js          # API endpoints 常數
        │
        ├── api/               # 📡 資料獲取層
        │   ├── client.js      # fetch wrapper（錯誤處理、retry）
        │   └── data.js        # 獲取價格、排名、股票資訊
        │
        ├── core/              # 🔧 共用核心模組
        │   ├── Portfolio.js   # 投資組合：持倉、現金、交易紀錄
        │   ├── Trade.js       # 交易執行器：手續費計算、買入/賣出
        │   └── Report.js      # 績效計算：報酬率、夏普、最大回撤
        │
        ├── simulator/         # 💰 手動交易模擬器
        │   ├── Session.js     # SimulatorSession：單次模擬會話管理
        │   └── Panel.js       # SimulatorPanel：UI 元件
        │
        ├── backtest/          # 📊 自動化回測引擎
        │   ├── Engine.js      # BacktestEngine：回測主程式
        │   ├── Panel.js       # BacktestPanel：UI 元件（表單 + 結果）
        │   │
        │   ├── buying/        # 🟢 買入條件插件（每個條件一個檔案）
        │   │   ├── index.js           # BuyConditionRegistry 註冊表
        │   │   ├── base.js            # BuyCondition 基類
        │   │   ├── sharpe_rank.js     # Sharpe Top-N 選股
        │   │   ├── sharpe_threshold.js # Sharpe 門檻過濾
        │   │   ├── sharpe_streak.js   # Sharpe 連續 Top-15
        │   │   ├── growth_rank.js     # Growth Top-K 選股
        │   │   ├── growth_streak.js   # Growth 連續動能
        │   │   ├── sort_sharpe.js     # 按 Sharpe 順序選股
        │   │   └── sort_industry.js   # 按產業分散選股
        │   │
        │   ├── selling/       # 🔴 賣出條件插件
        │   │   ├── index.js           # SellConditionRegistry 註冊表
        │   │   ├── base.js            # SellCondition 基類
        │   │   ├── sharpe_fail.js     # Sharpe 長期失格
        │   │   ├── growth_fail.js     # Growth 長期失格
        │   │   ├── not_selected.js    # 多期未入選淘汰
        │   │   ├── drawdown.js        # 價格破底停損
        │   │   └── weakness.js        # 相對弱勢退出
        │   │
        │   └── rebalance/     # 🔄 再平衡條件插件
        │       ├── index.js           # RebalanceConditionRegistry 註冊表
        │       ├── base.js            # RebalanceCondition 基類
        │       ├── immediate.js       # 立即投入
        │       ├── batch.js           # 分批投入
        │       ├── delayed.js         # 延遲投入
        │       ├── concentrated.js    # 集中投入
        │       └── none.js            # 保留現金
        │
        ├── components/        # 🎨 通用 UI 元件
        │   ├── MarketChart.js     # 市場看板
        │   └── IndustryChart.js   # 產業柱狀圖
        │
        └── utils/             # 🛠 工具函數
            ├── cache.js       # IndustryDataCache（排名資料快取）
            ├── formatter.js   # 數字/日期格式化
            └── chart.js       # Chart.js helpers
```

---

## 層級職責

### 後端（Python）

| 層級 | 職責 | 禁止事項 |
|------|------|----------|
| `src/` | 資料抓取、快取、指標計算 | 不含業務邏輯 |
| `routes/` | 提供 JSON API | 不執行回測/模擬計算 |

### 前端（JavaScript）

| 層級 | 職責 | 依賴 |
|------|------|------|
| `api/` | 獲取後端資料 | → `routes/` |
| `core/` | 投資組合、交易、績效計算 | 無外部依賴 |
| `simulator/` | 手動模擬邏輯 + UI | → `core/` |
| `backtest/` | 自動回測邏輯 + UI | → `core/`, `utils/cache` |
| `backtest/buying/` | 買入條件插件 | → `core/` |
| `backtest/selling/` | 賣出條件插件 | → `core/` |
| `backtest/rebalance/` | 再平衡條件插件 | → `core/` |
| `components/` | 通用 UI 元件 | → `api/` |
| `utils/` | 共用工具、資料快取 | → `api/` |

---

## API 路由設計

### routes/market.py

| 路由 | 方法 | 說明 |
|------|------|------|
| `/api/market-data` | GET | 市場看板資料（指數、匯率摘要） |
| `/api/kline/<symbol>` | GET | 單一標的 K 線資料 |
| `/api/exchange-rate` | GET | 當前匯率 |

### routes/stock.py

| 路由 | 方法 | 說明 |
|------|------|------|
| `/api/stocks` | GET | 股票清單 |
| `/api/stocks/industries` | GET | 產業清單 |
| `/api/industry/data` | GET | 產業分析資料（sharpe_matrix, growth_matrix） |
| `/api/backtest/prices` | GET | 回測用價格矩陣 |

### /api/backtest/prices 回傳格式

```json
{
  "dates": ["2020-01-02", "2020-01-03", ...],
  "tickers": ["AAPL", "MSFT", ...],
  "prices": {
    "AAPL": {
      "2020-01-02": {"open": 100, "high": 105, "low": 99, "close": 103},
      ...
    }
  },
  "stockInfo": {
    "AAPL": {"country": "US", "industry": "科技"}
  },
  "ranking": {
    "sharpe": {
      "2020-01-02": [{"ticker": "AAPL", "value": 1.5, "rank": 1}, ...]
    },
    "growth": {
      "2020-01-02": [{"ticker": "AAPL", "value": 0.05, "rank": 3}, ...]
    }
  }
}
```

---

## 前端核心模組

### core/Portfolio.js

```javascript
/**
 * 投資組合管理
 */
export class Portfolio {
    constructor(initialCapital) {
        this.initialCapital = initialCapital;
        this.cash = initialCapital;
        this.positions = {};  // {ticker: Position}
        this.trades = [];     // TradeRecord[]
    }
    
    // 持倉操作
    addPosition(ticker, shares, cost, country, industry, date) { }
    reducePosition(ticker, shares) { }
    removePosition(ticker) { }
    hasPosition(ticker) { }
    getPositionCount() { }
    
    // 價格追蹤
    updatePeakPrice(ticker, price) { }
    
    // 計算
    calculateMarketValue(prices) { }
    calculateHoldingsValue(prices) { }
    calculateTotalPnL(prices) { }
    
    // 交易紀錄
    recordTrade(trade) { }
}

/**
 * 持倉資料結構
 */
class Position {
    ticker: string;
    shares: number;
    avgCost: number;
    country: string;      // 'US' | 'TW'
    industry: string;
    buyDate: string;
    peakPrice: number;    // 歷史最高價（停損追蹤）
}

/**
 * 交易紀錄
 */
class TradeRecord {
    id: number;
    date: string;
    ticker: string;
    action: string;       // 'buy' | 'sell'
    shares: number;
    price: number;
    amount: number;
    fee: number;
    total: number;
    pnl: number;          // 僅賣出時有值
}
```

### core/Trade.js

```javascript
/**
 * 交易執行器
 */
export class TradeExecutor {
    static FEE_STRUCTURE = {
        US: { rate: 0.003, minFee: 15 },   // 美股複委託
        TW: { rate: 0.006, minFee: 0 }     // 台股（含證交稅）
    };
    
    constructor(portfolio, exchangeRate = 32) {
        this.portfolio = portfolio;
        this.exchangeRate = exchangeRate;
    }
    
    // 手續費計算
    calculateFee(amount, country) { }
    calculateBuyShares(amount, price, country) { }
    
    // 交易執行
    buy(ticker, price, amount, country, industry, date) { }
    sell(ticker, price, shares, date) { }
    sellAll(ticker, price, date) { }
}
```

### core/Report.js

```javascript
/**
 * 績效報告生成器
 */
export class ReportGenerator {
    constructor(portfolio) {
        this.portfolio = portfolio;
    }
    
    /**
     * 計算績效指標
     * @param {Array} equityCurve - [{date, equity, cash, holdingsValue}, ...]
     * @returns {Object} 績效指標
     */
    calculateMetrics(equityCurve) {
        return {
            totalReturn,        // 總報酬率 %
            annualizedReturn,   // 年化報酬率 %
            maxDrawdown,        // 最大回撤 %
            sharpeRatio,        // 夏普比率
            winRate,            // 勝率 %
            totalTrades,        // 總交易次數
            profitFactor        // 獲利因子
        };
    }
    
    calculateBenchmarkMetrics(benchmarkCurve) { }
}
```

---

## 模擬器模組

### simulator/Session.js

```javascript
/**
 * 模擬器會話
 * 管理單次手動模擬的狀態
 */
export class SimulatorSession {
    constructor(initialCapital = 1000000, exchangeRate = 32) {
        this.portfolio = new Portfolio(initialCapital);
        this.executor = new TradeExecutor(this.portfolio, exchangeRate);
        this.reporter = new ReportGenerator(this.portfolio);
        this.currentDate = null;
    }
    
    // 交易操作
    buy(ticker, price, amount, country, industry) { }
    sell(ticker, price, shares) { }
    sellAll(ticker, price) { }
    
    // 狀態查詢
    setCurrentDate(date) { }
    getPortfolio(prices) { }
    getPositions() { }
    getTrades() { }
    getReport(prices) { }
    
    // 重設
    reset(initialCapital) { }
}
```

### simulator/Panel.js

```javascript
/**
 * 模擬器 UI 面板
 */
export class SimulatorPanel {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        this.session = new SimulatorSession();
    }
    
    init() { }
    bindEvents() { }
    
    // UI 操作
    handleBuy() { }
    handleSell() { }
    updateDisplay(prices) { }
    renderPositions() { }
    renderTrades() { }
    renderReport() { }
}
```

---

## 回測引擎模組

### backtest/Engine.js

```javascript
import { Portfolio } from '../core/Portfolio.js';
import { TradeExecutor } from '../core/Trade.js';
import { ReportGenerator } from '../core/Report.js';
import { BuyConditionRegistry } from './buying/index.js';
import { SellConditionRegistry } from './selling/index.js';
import { RebalanceConditionRegistry } from './rebalance/index.js';

/**
 * 回測設定
 */
export class BacktestConfig {
    initialCapital = 1000000;
    startDate = null;
    endDate = null;
    rebalanceFreq = 'weekly';  // 'daily' | 'weekly' | 'monthly'
    market = 'global';         // 'global' | 'us' | 'tw'
    topN = 5;
    amountPerStock = 100000;
    maxPositions = 10;
    exchangeRate = 32;
    
    // 條件鍵值
    buyConditions = ['sharpe_rank'];
    sellConditions = ['sharpe_fail', 'drawdown'];
    rebalanceCondition = 'batch';
}

/**
 * 回測引擎
 */
export class BacktestEngine {
    constructor(config = new BacktestConfig()) {
        this.config = config;
        this.portfolio = null;
        this.executor = null;
        this.reporter = null;
        
        // 條件實例
        this.buyConditions = [];
        this.sellConditions = [];
        this.rebalanceCondition = null;
        
        // 資料
        this.prices = null;
        this.ranking = null;
        this.stockInfo = null;
        this.dates = [];
    }
    
    /**
     * 載入資料
     */
    loadData(data) {
        this.prices = data.prices;
        this.ranking = data.ranking;
        this.stockInfo = data.stockInfo;
        this.dates = data.dates;
    }
    
    /**
     * 載入條件插件
     */
    loadConditions() {
        // 買入條件
        this.buyConditions = this.config.buyConditions.map(key => 
            BuyConditionRegistry.create(key, { topN: this.config.topN })
        );
        
        // 賣出條件
        this.sellConditions = this.config.sellConditions.map(key =>
            SellConditionRegistry.create(key)
        );
        
        // 再平衡條件
        this.rebalanceCondition = RebalanceConditionRegistry.create(
            this.config.rebalanceCondition
        );
    }
    
    /**
     * 執行回測
     */
    run() {
        // 1. 初始化
        this.portfolio = new Portfolio(this.config.initialCapital);
        this.executor = new TradeExecutor(this.portfolio, this.config.exchangeRate);
        this.reporter = new ReportGenerator(this.portfolio);
        this.loadConditions();
        
        // 2. 篩選日期範圍
        const tradingDates = this._getTradingDates();
        const rebalanceDates = this._getRebalanceDates(tradingDates);
        
        // 3. 逐日模擬
        const equityCurve = [];
        
        for (const date of tradingDates) {
            const dayPrices = this._getDayPrices(date);
            const isRebalance = rebalanceDates.has(date);
            
            // 更新最高價
            this._updatePeakPrices(dayPrices);
            
            if (isRebalance) {
                // 檢查賣出
                this._checkSellConditions(date, dayPrices);
                
                // 檢查買入
                this._checkBuyConditions(date, dayPrices);
            }
            
            // 記錄權益
            equityCurve.push(this._recordEquity(date, dayPrices));
        }
        
        // 4. 計算績效
        const metrics = this.reporter.calculateMetrics(equityCurve);
        
        return {
            config: this.config,
            equityCurve,
            trades: this.portfolio.trades,
            holdings: this._getFinalHoldings(),
            metrics
        };
    }
    
    // 私有方法
    _getTradingDates() { }
    _getRebalanceDates(dates) { }
    _getDayPrices(date) { }
    _updatePeakPrices(prices) { }
    _checkSellConditions(date, prices) { }
    _checkBuyConditions(date, prices) { }
    _recordEquity(date, prices) { }
    _getFinalHoldings() { }
}
```

### backtest/Panel.js

```javascript
/**
 * 回測 UI 面板
 */
export class BacktestPanel {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        this.engine = null;
        this.data = null;
        this.results = null;
    }
    
    async init() { }
    bindEvents() { }
    
    // 設定收集
    collectSettings() { }
    
    // 執行
    async runBacktest() { }
    
    // 結果顯示
    displayResults() { }
    drawEquityCurve() { }
    displayTradeLog() { }
    displayHoldings() { }
    updateMetrics() { }
}
```

---

## 條件插件系統

### 買入條件 backtest/buying/

#### buying/base.js

```javascript
/**
 * 買入條件基類
 */
export class BuyCondition {
    constructor(name, description, options = {}) {
        this.name = name;
        this.description = description;
        this.options = options;
    }
    
    /**
     * 評估買入候選
     * @param {Object} context - {date, prices, ranking, portfolio, stockInfo}
     * @returns {Array} 候選股票 [{ticker, score, country, industry}, ...]
     */
    evaluate(context) {
        throw new Error('Must implement evaluate()');
    }
}
```

#### buying/index.js（註冊表）

```javascript
import { SharpeRankCondition } from './sharpe_rank.js';
import { SharpeThresholdCondition } from './sharpe_threshold.js';
import { SharpeStreakCondition } from './sharpe_streak.js';
import { GrowthRankCondition } from './growth_rank.js';
import { GrowthStreakCondition } from './growth_streak.js';
import { SortSharpeCondition } from './sort_sharpe.js';
import { SortIndustryCondition } from './sort_industry.js';

export const BuyConditionRegistry = {
    _conditions: {
        'sharpe_rank': SharpeRankCondition,
        'sharpe_threshold': SharpeThresholdCondition,
        'sharpe_streak': SharpeStreakCondition,
        'growth_rank': GrowthRankCondition,
        'growth_streak': GrowthStreakCondition,
        'sort_sharpe': SortSharpeCondition,
        'sort_industry': SortIndustryCondition,
    },
    
    create(key, options = {}) {
        const ConditionClass = this._conditions[key];
        if (!ConditionClass) throw new Error(`Unknown buy condition: ${key}`);
        return new ConditionClass(options);
    },
    
    list() {
        return Object.keys(this._conditions);
    },
    
    getInfo(key) {
        const ConditionClass = this._conditions[key];
        return ConditionClass ? ConditionClass.INFO : null;
    }
};
```

#### buying/sharpe_rank.js（範例）

```javascript
import { BuyCondition } from './base.js';

/**
 * Sharpe Top-N 選股
 */
export class SharpeRankCondition extends BuyCondition {
    static INFO = {
        key: 'sharpe_rank',
        name: 'Sharpe Top-N',
        description: '選取 Sharpe Ratio 排名前 N 的股票',
        category: 'range',  // 買入範圍
        risk: 'medium'
    };
    
    constructor(options = {}) {
        super('sharpe_rank', 'Sharpe Top-N 選股', options);
        this.topN = options.topN || 5;
    }
    
    evaluate(context) {
        const { date, prices, ranking, stockInfo } = context;
        
        const dayRanking = ranking.sharpe[date] || [];
        const candidates = [];
        
        for (const item of dayRanking.slice(0, this.topN)) {
            const ticker = item.ticker;
            if (prices[ticker]?.[date]) {
                candidates.push({
                    ticker,
                    score: item.value,
                    country: stockInfo[ticker]?.country || '',
                    industry: stockInfo[ticker]?.industry || '未分類'
                });
            }
        }
        
        return candidates;
    }
}
```

### 賣出條件 backtest/selling/

#### selling/base.js

```javascript
/**
 * 賣出條件基類
 */
export class SellCondition {
    constructor(name, description, options = {}) {
        this.name = name;
        this.description = description;
        this.options = options;
    }
    
    /**
     * 評估是否應賣出
     * @param {Object} context - {date, ticker, position, prices, ranking}
     * @returns {boolean} 是否應賣出
     */
    evaluate(context) {
        throw new Error('Must implement evaluate()');
    }
}
```

#### selling/index.js（註冊表）

```javascript
import { SharpeFailCondition } from './sharpe_fail.js';
import { GrowthFailCondition } from './growth_fail.js';
import { NotSelectedCondition } from './not_selected.js';
import { DrawdownCondition } from './drawdown.js';
import { WeaknessCondition } from './weakness.js';

export const SellConditionRegistry = {
    _conditions: {
        'sharpe_fail': SharpeFailCondition,
        'growth_fail': GrowthFailCondition,
        'not_selected': NotSelectedCondition,
        'drawdown': DrawdownCondition,
        'weakness': WeaknessCondition,
    },
    
    create(key, options = {}) {
        const ConditionClass = this._conditions[key];
        if (!ConditionClass) throw new Error(`Unknown sell condition: ${key}`);
        return new ConditionClass(options);
    },
    
    list() {
        return Object.keys(this._conditions);
    }
};
```

#### selling/drawdown.js（範例）

```javascript
import { SellCondition } from './base.js';

/**
 * 價格破底停損
 */
export class DrawdownCondition extends SellCondition {
    static INFO = {
        key: 'drawdown',
        name: '價格破底',
        description: '從高點回撤超過指定百分比時賣出',
        defaultThreshold: 40
    };
    
    constructor(options = {}) {
        super('drawdown', '價格破底停損', options);
        this.threshold = options.threshold || 40;  // 預設 40%
    }
    
    evaluate(context) {
        const { ticker, position, prices, date } = context;
        
        const currentPrice = prices[ticker]?.[date]?.close;
        if (!currentPrice || !position.peakPrice) return false;
        
        const drawdown = (position.peakPrice - currentPrice) / position.peakPrice * 100;
        return drawdown >= this.threshold;
    }
}
```

### 再平衡條件 backtest/rebalance/

#### rebalance/base.js

```javascript
/**
 * 再平衡條件基類
 */
export class RebalanceCondition {
    constructor(name, description, options = {}) {
        this.name = name;
        this.description = description;
        this.options = options;
    }
    
    /**
     * 計算應投入金額
     * @param {Object} context - {date, portfolio, prices, ranking, candidates}
     * @returns {number} 應投入金額（0 表示不投入）
     */
    calculateInvestAmount(context) {
        throw new Error('Must implement calculateInvestAmount()');
    }
}
```

#### rebalance/index.js（註冊表）

```javascript
import { ImmediateCondition } from './immediate.js';
import { BatchCondition } from './batch.js';
import { DelayedCondition } from './delayed.js';
import { ConcentratedCondition } from './concentrated.js';
import { NoneCondition } from './none.js';

export const RebalanceConditionRegistry = {
    _conditions: {
        'immediate': ImmediateCondition,
        'batch': BatchCondition,
        'delayed': DelayedCondition,
        'concentrated': ConcentratedCondition,
        'none': NoneCondition,
    },
    
    create(key, options = {}) {
        const ConditionClass = this._conditions[key];
        if (!ConditionClass) throw new Error(`Unknown rebalance condition: ${key}`);
        return new ConditionClass(options);
    },
    
    list() {
        return Object.keys(this._conditions);
    }
};
```

#### rebalance/batch.js（範例）

```javascript
import { RebalanceCondition } from './base.js';

/**
 * 分批投入
 */
export class BatchCondition extends RebalanceCondition {
    static INFO = {
        key: 'batch',
        name: '分批投入',
        description: '固定比例投入，平滑成本',
        defaultRatio: 0.2
    };
    
    constructor(options = {}) {
        super('batch', '分批投入', options);
        this.ratio = options.ratio || 0.2;  // 每次投入 20%
    }
    
    calculateInvestAmount(context) {
        const { portfolio } = context;
        return portfolio.cash * this.ratio;
    }
}
```

---

## 條件鍵值對照表

### 買入條件

| 鍵值 | 檔案 | 類別 | 說明 |
|------|------|------|------|
| `sharpe_rank` | `buying/sharpe_rank.js` | 範圍 | Sharpe Top-N 選股 |
| `sharpe_threshold` | `buying/sharpe_threshold.js` | 範圍 | Sharpe 門檻過濾 |
| `sharpe_streak` | `buying/sharpe_streak.js` | 範圍 | Sharpe 連續 Top-15 |
| `growth_rank` | `buying/growth_rank.js` | 動能 | Growth Top-K 選股 |
| `growth_streak` | `buying/growth_streak.js` | 動能 | Growth 連續動能 |
| `sort_sharpe` | `buying/sort_sharpe.js` | 選股 | 按 Sharpe 順序 |
| `sort_industry` | `buying/sort_industry.js` | 選股 | 按產業分散 |

### 賣出條件

| 鍵值 | 檔案 | 說明 |
|------|------|------|
| `sharpe_fail` | `selling/sharpe_fail.js` | Sharpe 長期失格 |
| `growth_fail` | `selling/growth_fail.js` | Growth 長期失格 |
| `not_selected` | `selling/not_selected.js` | 多期未入選淘汰 |
| `drawdown` | `selling/drawdown.js` | 價格破底停損 |
| `weakness` | `selling/weakness.js` | 相對弱勢退出 |

### 再平衡條件

| 鍵值 | 檔案 | 說明 |
|------|------|------|
| `immediate` | `rebalance/immediate.js` | 立即投入 |
| `batch` | `rebalance/batch.js` | 分批投入 |
| `delayed` | `rebalance/delayed.js` | 延遲投入 |
| `concentrated` | `rebalance/concentrated.js` | 集中投入 |
| `none` | `rebalance/none.js` | 保留現金 |

---

## 資料流

```
┌─────────────────────────────────────────────────────────────────┐
│                           使用者操作                              │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│  backtest/Panel.js                                              │
│  - 收集設定（條件鍵值、參數）                                      │
│  - 呼叫 api/data.js 載入資料                                      │
│  - 建立 BacktestEngine，執行 run()                                │
│  - 渲染結果（圖表、交易紀錄、持倉）                                 │
└─────────────────────────────────────────────────────────────────┘
        │                           │
        ▼                           ▼
┌───────────────────┐    ┌─────────────────────────────────────────┐
│   api/data.js     │    │  backtest/Engine.js                     │
│                   │    │                                         │
│ GET /api/backtest │    │  loadConditions() 從註冊表建立實例       │
│     /prices       │    │  run() 執行回測迴圈                      │
└───────────────────┘    └─────────────────────────────────────────┘
        │                           │
        ▼                           ├───────────────────┐
┌───────────────────┐               ▼                   ▼
│   routes/stock.py │    ┌─────────────────┐  ┌─────────────────┐
│                   │    │ buying/index.js │  │ selling/index.js│
│ 從 src 讀取資料   │    │                 │  │                 │
└───────────────────┘    │ → sharpe_rank   │  │ → sharpe_fail   │
        │                │ → growth_rank   │  │ → drawdown      │
        ▼                │ → sort_industry │  │ → weakness      │
┌───────────────────┐    └─────────────────┘  └─────────────────┘
│      src/         │               │
│  DataContainer    │               ▼
└───────────────────┘    ┌─────────────────┐
                         │    core/        │
                         │  Portfolio.js   │
                         │  Trade.js       │
                         │  Report.js      │
                         └─────────────────┘
```

---

## 新增條件指南

### 新增買入條件

1. 建立 `backtest/buying/<key>.js`
2. 繼承 `BuyCondition`，實作 `evaluate(context)`
3. 在 `buying/index.js` 的 `_conditions` 註冊

```javascript
// backtest/buying/momentum.js
import { BuyCondition } from './base.js';

export class MomentumCondition extends BuyCondition {
    static INFO = {
        key: 'momentum',
        name: '動量選股',
        description: '選取近期漲幅最大的股票'
    };
    
    constructor(options = {}) {
        super('momentum', '動量選股', options);
        this.lookback = options.lookback || 20;
    }
    
    evaluate(context) {
        // 實作選股邏輯
        return candidates;
    }
}
```

### 新增賣出條件

1. 建立 `backtest/selling/<key>.js`
2. 繼承 `SellCondition`，實作 `evaluate(context)`
3. 在 `selling/index.js` 註冊

### 新增再平衡條件

1. 建立 `backtest/rebalance/<key>.js`
2. 繼承 `RebalanceCondition`，實作 `calculateInvestAmount(context)`
3. 在 `rebalance/index.js` 註冊

---

## 禁止事項

1. **routes/ 禁止執行回測/模擬計算**：僅提供資料
2. **條件插件禁止互相依賴**：每個條件應獨立運作
3. **core/ 模組必須純淨**：不依賴 DOM、API、外部狀態
4. **Panel 禁止直接操作 Portfolio**：應透過 Engine 或 Session

---

## 移植對照表

| Python (engine/) | JavaScript (static/js/) |
|------------------|-------------------------|
| `core/portfolio.py` | `core/Portfolio.js` |
| `core/trade.py` | `core/Trade.js` |
| `core/report.py` | `core/Report.js` |
| `simulator/session.py` | `simulator/Session.js` |
| `backtest/tester.py` | `backtest/Engine.js` |
| `backtest/condition/buying.py` | `backtest/buying/*.js` |
| `backtest/condition/selling.py` | `backtest/selling/*.js` |
| `backtest/condition/rebalance.py` | `backtest/rebalance/*.js` |

---

## 開發優先順序

### Phase 1：核心模組
1. `core/Portfolio.js`
2. `core/Trade.js`
3. `core/Report.js`

### Phase 2：條件插件
1. `backtest/buying/base.js` + `index.js`
2. `backtest/buying/sharpe_rank.js`（核心買入條件）
3. `backtest/selling/base.js` + `index.js`
4. `backtest/selling/drawdown.js`（核心賣出條件）
5. `backtest/rebalance/base.js` + `index.js`
6. `backtest/rebalance/batch.js`（預設再平衡）

### Phase 3：引擎整合
1. `backtest/Engine.js`
2. `backtest/Panel.js`

### Phase 4：模擬器
1. `simulator/Session.js`
2. `simulator/Panel.js`

### Phase 5：清理
1. 移除 `engine/` 目錄
2. 簡化 `routes/`
