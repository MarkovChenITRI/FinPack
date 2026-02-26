# backtest/ 回測引擎參考文件

> 取代舊版 `engine_document.md`（原文件描述的是已廢棄的 v2 JavaScript 前端引擎）
> 本文件描述 v3 Python 後端引擎
> 最後更新：2026-02

---

## 一、架構概覽

回測引擎完全以 Python 實作，部署於後端。前端**不執行任何回測計算**，僅負責：
- 送出回測參數（POST /api/backtest/run）
- 接收並顯示 JSON 結果

```
backtest/
├── __init__.py    # 統一匯出介面
├── config.py      # 配置定義（CONDITION_OPTIONS, DEFAULT_CONFIG, merge_config）
├── engine.py      # BacktestEngine + 相關資料類別
└── report.py      # format_backtest_report（CLI 格式化輸出）
```

---

## 二、配置模組（config.py）

**這是 CONDITION_OPTIONS 和 DEFAULT_CONFIG 的唯一真相來源**，`web/routes/backtest.py` 目前有重複定義（已列入已知問題）。

### 2.1 CONDITION_OPTIONS

前端下拉選單的選項定義，結構：

```python
CONDITION_OPTIONS = {
    'buy_conditions': { <condition_key>: { 'name', 'description', 'params', 'category' } },
    'sell_conditions': { <condition_key>: { 'name', 'description', 'params' } },
    'rebalance_strategies': { <strategy_key>: { 'name', 'description', 'params' } }
}
```

### 2.2 DEFAULT_CONFIG

回測預設參數（數值型，不含 Money 類型）：

```python
DEFAULT_CONFIG = {
    'initial_capital': 1_000_000,    # TWD
    'amount_per_stock': 100_000,     # TWD
    'max_positions': 10,
    'market': 'us',                  # 'us' | 'tw' | 'global'
    'backtest_months': 6,
    'rebalance_freq': 'weekly',      # 'daily' | 'weekly' | 'monthly'
    'buy_conditions': {
        'sharpe_rank':     {'enabled': True,  'top_n': 15},
        'sharpe_threshold':{'enabled': True,  'threshold': 1.0},
        'sharpe_streak':   {'enabled': False, 'days': 3, 'top_n': 10},
        'growth_streak':   {'enabled': True,  'days': 2, 'percentile': 30},
        'growth_rank':     {'enabled': False, 'top_n': 7},
        'sort_sharpe':     {'enabled': True},
        'sort_industry':   {'enabled': False, 'per_industry': 2},
    },
    'sell_conditions': {
        'sharpe_fail': {'enabled': True,  'periods': 2, 'top_n': 15},
        'growth_fail': {'enabled': False, 'days': 5, 'threshold': 0},
        'not_selected':{'enabled': False, 'periods': 3},
        'drawdown':    {'enabled': True,  'threshold': 0.40},
        'weakness':    {'enabled': False, 'rank_k': 20, 'periods': 3},
    },
    'rebalance_strategy': {
        'type': 'delayed',
        'top_n': 5,
        'sharpe_threshold': 0,
        'batch_ratio': 0.20,
        'concentrate_top_k': 3,
        'lead_margin': 0.30,
    }
}
```

### 2.3 merge_config()

```python
from backtest.config import merge_config

config = merge_config(user_params)
# 深度合併使用者參數與 DEFAULT_CONFIG
# 保留 DEFAULT_CONFIG 中未被覆蓋的值
```

---

## 三、資料類別

定義於 `backtest/engine.py`。

### TradeType（Enum）

```python
class TradeType(Enum):
    BUY  = "buy"
    SELL = "sell"
```

### Trade（dataclass）

```python
@dataclass
class Trade:
    date: str
    symbol: str
    trade_type: TradeType
    shares: float
    price: Money        # 買入價（原始幣別）
    amount: Money       # 交易金額（TWD）
    fee: Money          # 手續費（TWD）
    pnl: Money          # 損益（TWD，僅賣出有意義）
```

### Position（dataclass）

```python
@dataclass
class Position:
    symbol: str
    shares: float
    avg_cost: Money     # 平均成本（原始幣別）
    cost_basis: Money   # 總成本（TWD）
    buy_date: str       # 首次買入日期
    peak_price: float   # 歷史最高價（用於 drawdown 計算）
```

### BacktestResult（dataclass）

```python
@dataclass
class BacktestResult:
    initial_capital: Money    # 初始資金（TWD）
    final_equity: Money       # 最終總資產（TWD）
    total_return: float       # 總報酬率（0.15 = 15%）
    annualized_return: float  # 年化報酬率
    max_drawdown: float       # 最大回撤（0.08 = 8%）
    sharpe_ratio: float       # 策略 Sharpe Ratio
    total_trades: int
    win_trades: int
    loss_trades: int
    win_rate: float           # 勝率（0~1）
    equity_curve: List[Dict]  # [{'date', 'equity', 'cash', 'positions_value'}]
    trades: List[Dict]        # Trade 序列化
```

---

## 四、BacktestEngine 類別

### 4.1 建立引擎

```python
from backtest.engine import BacktestEngine
from core.currency import twd, FX

engine = BacktestEngine(
    close_df    = close_df,       # DataFrame [Date × Symbol]
    indicators  = indicators,     # Indicators 實例
    stock_info  = stock_info,     # Dict[ticker, {country, industry}]
    config      = engine_config,  # 含 Money 類型的配置 dict
    fx          = fx              # FX 匯率實例
)
```

**engine_config 格式**：
```python
engine_config = {
    'initial_capital':   twd(1_000_000),   # Money
    'amount_per_stock':  twd(100_000),     # Money
    'max_positions':     10,
    'rebalance_freq':    'weekly',
    'buy_conditions':    { ... },
    'sell_conditions':   { ... },
    'rebalance_strategy':{ ... },
}
```

### 4.2 執行回測

```python
result = engine.run(
    start_date = pd.Timestamp('2025-01-01'),
    end_date   = pd.Timestamp('2025-06-30')
)
# 返回 BacktestResult
```

### 4.3 存取執行狀態

```python
engine.cash        # Money（TWD）：當前現金
engine.positions   # Dict[str, Position]：當前持倉
engine.trades      # List[Trade]：所有交易記錄
```

---

## 五、回測執行流程

```
BacktestEngine.run(start_date, end_date)
    ↓
逐日迴圈（close_df.index 中 start_date ~ end_date 的交易日）：
    │
    ├── _calc_equity(date)           計算當日總資產
    │   └── 現金 + Σ(持倉市值，USD 股票自動轉 TWD)
    │
    ├── _check_rebalance_day(date)   判斷是否為再平衡日
    │   └── 依 rebalance_freq：weekly（週一）、monthly（月初）、daily（每天）
    │
    ├── _evaluate_sells(date)        評估賣出條件
    │   └── 對每個持倉，任一賣出條件為 True 則加入賣出清單
    │
    ├── _execute_sells(date, sells)  執行賣出
    │   └── 更新 cash、positions、trades
    │
    ├── _process_rebalance(date)     執行買入（每天都執行）
    │   ├── _select_stocks(date)     → 依買入條件篩選候選股
    │   └── _buy_stocks(date, candidates)  → 依再平衡策略執行買入
    │
    └── 記錄 equity_curve
```

---

## 六、買入條件（buy_conditions）

買入條件採用**交集**：候選股必須同時通過所有 `enabled: True` 的條件。

| 條件 key | 邏輯 | 主要參數 |
|----------|------|---------|
| `sharpe_rank` | 當日 Sharpe 排名 ≤ top_n | `top_n`（預設 15） |
| `sharpe_threshold` | 當日 Sharpe ≥ threshold | `threshold`（預設 1.0） |
| `sharpe_streak` | 連續 days 天 Sharpe 排名 ≤ top_n | `days`, `top_n` |
| `growth_rank` | 當日 Growth 排名 ≤ top_n | `top_n`（預設 7） |
| `growth_streak` | 連續 days 天 Growth 排名在前 percentile% | `days`, `percentile` |
| `sort_sharpe` | 候選股按 Sharpe 降序排列（影響買入順序） | — |
| `sort_industry` | 每個產業最多選 per_industry 檔（round-robin） | `per_industry`（預設 2） |

---

## 七、賣出條件（sell_conditions）

賣出條件採用**聯集**：任一 `enabled: True` 條件滿足即觸發賣出。

| 條件 key | 邏輯 | 主要參數 |
|----------|------|---------|
| `sharpe_fail` | 連續 periods 個再平衡日未進入 Sharpe 前 top_n | `periods`, `top_n` |
| `growth_fail` | 最近 days 天 Growth 均值 < threshold | `days`, `threshold` |
| `not_selected` | 連續 periods 個再平衡日未被買入條件選中 | `periods` |
| `drawdown` | 從買入價或歷史最高價下跌超過 threshold | `threshold`（預設 0.40 = 40%） |
| `weakness` | 連續 periods 個再平衡日 Sharpe 排名 > rank_k | `rank_k`, `periods` |

---

## 八、再平衡策略（rebalance_strategy）

控制**何時及如何買入**候選股。

| 策略 type | 邏輯 | 主要參數 |
|-----------|------|---------|
| `immediate` | 有空間就立即買入（用 `amount_per_stock`） | — |
| `batch` | 每次只用現金的 batch_ratio 比例投入，分散在所有候選 | `batch_ratio`（預設 0.20） |
| `delayed` | Top-N 平均 Sharpe > sharpe_threshold 才買入 | `top_n`, `sharpe_threshold` |
| `concentrated` | Top-K 的平均 Sharpe 領先次群超過 lead_margin 才買入 | `concentrate_top_k`, `lead_margin` |
| `none` | 不主動再平衡（只賣，不因再平衡而買） | — |

---

## 九、CLI 與 Web API 的差異

| 面向 | run.py（CLI） | web/routes/backtest.py（API） |
|------|--------------|-------------------------------|
| 配置來源 | `FRONTEND_DEFAULTS`（繼承 `DEFAULT_CONFIG`） | 前端 POST body 合併預設值 |
| 金額包裝 | 在 `FRONTEND_DEFAULTS` 中包裝為 `twd(...)` | 在 `run_backtest()` 中包裝為 `twd(...)` |
| 日期範圍 | 用 `backtest_months` 從最新日期往回算 | 可直接傳 `start_date` / `end_date` |
| 輸出格式 | `format_backtest_report()`（純文字） | JSON response |
| benchmark 曲線 | 不計算 | 嘗試計算（目前有已知問題） |

---

## 十、格式化報告（report.py）

```python
from backtest.report import format_backtest_report

text = format_backtest_report(
    result          = result,           # BacktestResult
    cash            = engine.cash,      # Money（TWD）
    current_holdings= current_holdings, # List[Dict]
    initial_capital = initial_capital,  # Money（TWD）
    amount_per_stock= amount_per_stock, # Money（TWD）
    max_positions   = max_positions,    # int
    start_dt        = start_dt,         # pd.Timestamp
    end_dt          = end_dt,           # pd.Timestamp
    elapsed         = elapsed           # float（秒）
)
print(text)
```

輸出內容：
- 回測參數摘要
- 績效指標（報酬率、年化報酬、最大回撤、Sharpe、勝率）
- 當前持倉列表
- 所有交易記錄
- 簡易權益曲線
