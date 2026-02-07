# 前端模組規範（JavaScript）

## 一、設計理念

### 1.1 核心原則

**計算前置化**：所有回測、模擬計算在前端執行，後端僅提供原始資料。

**模組化設計**：將核心邏輯、交易模擬、回測引擎分離為獨立模組，各自內聚且鬆耦合。

**共用核心**：`core/` 定義所有模組共用的基礎元件（Portfolio, Trade, Report），確保行為一致。

**插件化條件**：回測條件採用插件模式，透過繼承基類實現，每個條件為獨立 `.js` 檔案。

**資料單向流動**：`api/` → `core/` → `simulator/` / `backtest/` → UI

---

## 二、模組結構

```
static/js/
├── app.js                   # 應用入口
├── config.js                # API endpoints 常數
│
├── api/                     # 📡 資料獲取層
│   ├── client.js            # fetch wrapper
│   └── data.js              # 統一資料介面
│
├── core/                    # 🔧 共用核心模組
│   ├── Portfolio.js         # 投資組合管理
│   ├── Trade.js             # 交易執行器
│   └── Report.js            # 績效報告生成
│
├── simulator/               # 💰 手動交易模擬器
│   ├── Session.js           # 模擬會話管理
│   └── Panel.js             # UI 面板
│
└── backtest/                # 📊 自動化回測引擎
    ├── Engine.js            # 回測主程式
    ├── Panel.js             # UI 面板
    │
    ├── buying/              # 🟢 買入條件插件
    │   ├── base.js          # BuyCondition 基類
    │   ├── index.js         # BuyConditionRegistry 註冊表
    │   ├── sharpe_rank.js
    │   ├── sharpe_threshold.js
    │   ├── sharpe_streak.js
    │   ├── growth_rank.js
    │   ├── growth_streak.js
    │   ├── sort_sharpe.js
    │   └── sort_industry.js
    │
    ├── selling/             # 🔴 賣出條件插件
    │   ├── base.js          # SellCondition 基類
    │   ├── index.js         # SellConditionRegistry 註冊表
    │   ├── sharpe_fail.js
    │   ├── growth_fail.js
    │   ├── not_selected.js
    │   ├── drawdown.js
    │   └── weakness.js
    │
    └── rebalance/           # 🔄 再平衡條件插件
        ├── base.js          # RebalanceCondition 基類
        ├── index.js         # RebalanceConditionRegistry 註冊表
        ├── immediate.js
        ├── batch.js
        ├── delayed.js
        ├── concentrated.js
        └── none.js
```

---

## 三、core/ 共用核心模組

### 3.1 設計原則

`core/` 定義被 `simulator/` 和 `backtest/` 共同使用的基礎元件，確保：
- 手動模擬與自動回測使用相同的持倉、交易、報告邏輯
- 行為一致性（手續費計算、損益計算、績效指標）

### 3.2 Portfolio — 投資組合

**職責**：管理現金、持倉、交易紀錄。

**核心資料結構**：

```javascript
// 持倉結構
class Position {
    ticker;       // 股票代碼
    shares;       // 持有股數
    avgCost;      // 平均成本
    country;      // 國家（'US' | 'TW'）
    industry;     // 產業
    buyDate;      // 買入日期
    peakPrice;    // 歷史最高價（用於停損）
}

// 交易紀錄
class TradeRecord {
    id;           // 交易 ID
    date;         // 交易日期
    ticker;       // 股票代碼
    action;       // 'buy' | 'sell'
    shares;       // 股數
    price;        // 單價
    amount;       // 交易金額
    fee;          // 手續費
    total;        // 實際金額（含手續費）
    pnl;          // 損益（僅賣出）
}
```

**核心方法**：

| 方法 | 說明 |
|------|------|
| `addPosition(ticker, shares, cost, ...)` | 新增/加碼持倉 |
| `reducePosition(ticker, shares)` | 減少/清除持倉 |
| `removePosition(ticker)` | 移除持倉 |
| `hasPosition(ticker)` | 是否持有 |
| `updatePeakPrice(ticker, price)` | 更新最高價（停損追蹤） |
| `recordTrade(trade)` | 記錄交易 |
| `calculateMarketValue(prices)` | 計算總市值 |
| `calculateTotalPnL(prices)` | 計算總損益 |

### 3.3 Trade — 交易執行器

**職責**：執行買入/賣出，計算手續費。

**手續費結構**：

```javascript
static FEE_STRUCTURE = {
    US: { rate: 0.003, minFee: 15 },   // 美股複委託 0.3%，最低 15 USD
    TW: { rate: 0.006, minFee: 0 }     // 台股 0.6%（含證交稅）
};
```

**核心方法**：

| 方法 | 說明 |
|------|------|
| `calculateFee(amount, country)` | 計算手續費 |
| `calculateBuyShares(amount, price, country)` | 計算可買股數 |
| `buy(ticker, price, amount, ...)` | 執行買入 |
| `sell(ticker, price, shares, ...)` | 執行賣出 |
| `sellAll(ticker, price, date)` | 全數賣出 |

**匯率處理**：美股交易以台幣計價，透過 `exchangeRate` 進行轉換。

### 3.4 Report — 報告生成器

**職責**：計算績效指標，產生報告。

**績效指標**：

| 指標 | 計算方式 |
|------|----------|
| `totalReturn` | (最終市值 - 初始資金) / 初始資金 × 100% |
| `annualizedReturn` | 複合年化報酬率 |
| `maxDrawdown` | 歷史最大回撤百分比 |
| `sharpeRatio` | (超額報酬均值 / 波動率) × √252 |
| `sortinoRatio` | 使用下行標準差計算 |
| `calmarRatio` | 年化報酬 / 最大回撤 |
| `winRate` | 獲利交易數 / 總交易數 × 100% |
| `profitFactor` | 總獲利 / 總虧損 |

---

## 四、simulator/ 手動模擬器

### 4.1 設計原則

**會話管理**：每個模擬實例為一個 `SimulatorSession`，封裝 Portfolio、TradeExecutor、ReportGenerator。

**前端互動**：配合前端 K 線圖的日期選擇，在指定日期執行買賣。

**本地持久化**：使用 localStorage 保存模擬狀態，支援重新載入。

### 4.2 SimulatorSession

**核心方法**：

| 方法 | 說明 |
|------|------|
| `buy(ticker, price, amount, ...)` | 執行買入並返回結果 |
| `sell(ticker, price, shares, ...)` | 執行賣出並返回結果 |
| `getPortfolio(prices)` | 取得投資組合狀態 |
| `getPositions()` | 取得所有持倉 |
| `getTrades()` | 取得交易紀錄 |
| `getReport(equityCurve)` | 取得績效報告 |
| `reset(initialCapital)` | 重設會話 |
| `save()` | 保存至 localStorage |
| `load()` | 從 localStorage 載入 |

### 4.3 SimulatorPanel

**UI 功能**：

- 買入表單（股票、金額、模式）
- 賣出操作（單賣、全賣）
- 持倉列表顯示
- 交易紀錄查看
- 績效報告展示

---

## 五、backtest/ 回測引擎

### 5.1 設計原則

**條件插件化**：買入、賣出、再平衡條件皆為獨立 `.js` 檔案，透過繼承基類實現。

**配置驅動**：回測參數透過 `BacktestConfig` 集中管理。

**迴圈架構**：逐日遍歷交易日，依序執行：更新價格 → 檢查賣出 → 檢查買入 → 記錄權益。

### 5.2 BacktestConfig — 回測配置

```javascript
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
```

### 5.3 BacktestEngine — 回測主程式

**執行流程**：

```
1. 初始化 Portfolio、TradeExecutor、ReportGenerator
2. 載入條件插件（根據 config）
3. 取得交易日期序列
4. 決定再平衡日期
5. 逐日迴圈：
   a. 取得當日價格
   b. 更新持倉最高價
   c. 若為再平衡日：
      - 檢查賣出條件 → 執行賣出
      - 檢查買入條件 → 執行買入
   d. 記錄權益曲線
6. 計算績效指標
7. 返回 BacktestResult
```

**核心方法**：

| 方法 | 說明 |
|------|------|
| `loadData(data)` | 載入價格、排名、股票資訊 |
| `loadConditions()` | 根據配置載入條件插件 |
| `run()` | 執行回測，返回結果 |
| `_getTradingDates()` | 取得交易日期序列 |
| `_getRebalanceDates()` | 計算再平衡日期 |
| `_checkSellConditions()` | 檢查並執行賣出 |
| `_checkBuyConditions()` | 檢查並執行買入 |

### 5.4 condition/ — 條件插件系統

#### 基類定義

```javascript
// buying/base.js
export class BuyCondition {
    constructor(name, description) {
        this.name = name;
        this.description = description;
    }
    
    // 返回候選股票列表 [{ticker, score, country, industry}]
    evaluate(date, prices, ranking, portfolio) {
        throw new Error('Must implement evaluate()');
    }
}

// selling/base.js
export class SellCondition {
    constructor(name, description) {
        this.name = name;
        this.description = description;
    }
    
    // 返回是否應該賣出
    evaluate(date, ticker, position, prices, ranking) {
        throw new Error('Must implement evaluate()');
    }
}

// rebalance/base.js
export class RebalanceCondition {
    constructor(name, description) {
        this.name = name;
        this.description = description;
    }
    
    // 返回投入金額（0 = 不投入，> 0 = 投入該金額）
    evaluate(date, portfolio, prices, ranking) {
        throw new Error('Must implement evaluate()');
    }
}
```

#### 條件註冊表

```javascript
// buying/index.js
export const BuyConditionRegistry = {
    _conditions: { /* 鍵值 → 類別對照 */ },
    
    create(key, config = {}) {
        const Condition = this._conditions[key];
        if (!Condition) throw new Error(`Unknown buy condition: ${key}`);
        return new Condition(config);
    },
    
    list() {
        return Object.keys(this._conditions);
    }
};
```

---

## 六、api/ 資料獲取層

### 6.1 data.js — 統一資料介面

**核心功能**：

| 方法 | 說明 |
|------|------|
| `fetchStocks()` | 取得股票清單 |
| `fetchIndustryData()` | 取得產業分析資料（含 ranking） |
| `fetchBacktestPrices(startDate, endDate)` | 取得回測用價格矩陣 |
| `fetchKline(symbol)` | 取得單一標的 K 線 |
| `fetchExchangeRate()` | 取得匯率 |

**快取機制**：
- 使用 Map 快取已獲取的資料
- 支援強制刷新選項

---

## 七、擴充指南

### 7.1 新增買入條件

1. 在 `backtest/buying/` 建立新檔案（如 `momentum.js`）
2. 繼承 `BuyCondition` 基類
3. 實現 `evaluate()` 方法
4. 在 `buying/index.js` 匯入並註冊

```javascript
// momentum.js
import { BuyCondition } from './base.js';

export class MomentumCondition extends BuyCondition {
    constructor(config = {}) {
        super('momentum', '動量選股');
        this.lookback = config.lookback || 20;
    }
    
    evaluate(date, prices, ranking, portfolio) {
        // 實現選股邏輯
        return candidates;  // [{ticker, score, country, industry}]
    }
}
```

### 7.2 新增賣出條件

1. 在 `backtest/selling/` 建立新檔案
2. 繼承 `SellCondition` 基類
3. 實現 `evaluate()` 方法
4. 在 `selling/index.js` 匯入並註冊

### 7.3 新增再平衡條件

1. 在 `backtest/rebalance/` 建立新檔案
2. 繼承 `RebalanceCondition` 基類
3. 實現 `evaluate()` 方法
4. 在 `rebalance/index.js` 匯入並註冊

---

## 八、禁止事項

1. **禁止在 `core/` 引用 `simulator/` 或 `backtest/`**：`core/` 是被共用的基礎
2. **禁止條件類別之間互相依賴**：每個條件應獨立運作
3. **禁止繞過 `TradeExecutor` 直接操作 `Portfolio`**：交易必須透過執行器
4. **禁止在 UI 層直接計算業務邏輯**：應委派給對應模組
5. **禁止直接修改 `Portfolio` 的內部狀態**：使用提供的方法

---

## 九、測試檢查點

新增或修改模組後，應驗證：

1. 回測可正常運行並產生正確結果
2. 模擬器買賣功能正常
3. 條件插件正確觸發
4. 績效指標計算正確
5. 手續費計算符合預期
6. 持倉、交易紀錄正確更新

---

## 十、版本紀錄

| 版本 | 日期 | 說明 |
|------|------|------|
| 1.0 | 2025-01 | 初版：後端 Python engine/ 架構 |
| 2.0 | 2025-06 | 完全重構：移至前端 JavaScript，後端僅提供資料 |
