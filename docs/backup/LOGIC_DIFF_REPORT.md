# FinPack 後端 vs 前端邏輯差異修復報告

## 修復總結

本次修復解決了 `run.py` (Python 後端) 與 `main.py` (JS 前端) 回測結果不一致的問題。

## 已修復的差異

### 1. ✅ sort_industry 選股邏輯

**問題**：
- 後端只選每個產業 1 檔，且是單一選取
- 前端選每個產業最多 2 檔，使用 round-robin 方式分散選取

**修復**：
- `backtest/engine.py` 的 `_select_stocks()` 增加 `per_industry` 參數
- 改用 round-robin 選取邏輯
- `run.py` 的 `FRONTEND_DEFAULTS` 加入 `'per_industry': 2`

### 2. ✅ drawdown 回撤計算基準

**問題**：
- 後端固定從「最高價」計算回撤
- 前端預設從「買入價」計算（`fromHighest: false`）

**修復**：
- `backtest/engine.py` 的 `_check_sell()` 增加 `from_highest` 參數判斷
- `run.py` 的 `FRONTEND_DEFAULTS` 加入 `'from_highest': False`

### 3. ✅ batch 再平衡策略

**問題**：
- 後端 batch 策略是「賣出邏輯」：賣出 20% 不在候選的持倉，然後用固定金額買入
- 前端 batch 策略是「買入邏輯」：用 20% 現金分散買入新候選

**修復**：
- 完全重寫 `_process_rebalance()` 方法
- batch: 用 `cash × batch_ratio` 分配買入所有候選
- immediate: 用固定 `amount_per_stock` 買入
- concentrated: 只買前 K 名
- delayed: 市場不好時不買

### 4. ✅ 買入時機

**問題**：
- 後端只在 `_is_rebalance_day` (週/月第一天) 才會買入
- 前端每天都會嘗試買入（通過 `_processRebalance` + `_processBuySignals`）

**修復**：
- 修改 `_process_day()` 移除 `_is_rebalance_day` 限制
- 現在每天都會執行 `_process_rebalance()` 來嘗試買入

## 已驗證一致的邏輯

### 買入條件
- ✅ sharpe_rank: Top-N 過濾
- ✅ sharpe_threshold: 閾值過濾  
- ✅ sharpe_streak: 連續在 Top-N
- ✅ growth_streak: Growth 連續性
- ✅ growth_rank: Growth Top-N 過濾
- ✅ sort_sharpe: 按 Sharpe 排序
- ✅ sort_industry: 分產業選取（已修復）

### 賣出條件
- ✅ sharpe_fail: 連續 N 期掉出 Top-K
- ✅ growth_fail: Growth 連續負值
- ✅ not_selected: 連續未被選中
- ✅ drawdown: 回撤停損（已修復）
- ✅ weakness: 排名弱勢

### 其他
- ✅ 手續費計算: 美股 0.3%/最低 $15，台股 0.6%
- ✅ 持倉管理: 最大持倉數、買入金額等

## 測試驗證

建立了以下測試文件驗證邏輯一致性：
- `test_logic_standalone.py` - 獨立數據測試
- `test_logic_real.py` - 真實快取數據測試
- `test_batch_strategy.py` - batch 策略專項測試

## 修改的檔案

1. `backtest/engine.py`
   - `_select_stocks()`: 新增 per_industry, round-robin
   - `_check_sell()`: 新增 from_highest 參數
   - `_process_rebalance()`: 完全重寫為買入邏輯
   - `_buy_stocks()`: 新方法處理批量買入
   - `_process_day()`: 移除 rebalance day 限制

2. `run.py`
   - `FRONTEND_DEFAULTS`: 更新預設值
     - `sort_industry.per_industry: 2`
     - `drawdown.from_highest: False`

---
最後更新：2025-02
