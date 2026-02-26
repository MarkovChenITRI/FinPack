# 已知問題清單（技術債）

> 最後更新：2026-02
> 本文件記錄目前程式碼中的已知問題，**不動程式碼，僅文件記錄**。
> 修復優先順序：🔴 嚴重（功能完全失效） → 🟡 高（維護風險） → 🟢 低（改善建議）

---

## 🔴 嚴重問題（功能完全失效）

### Issue #1：container.get_market_data() 不存在

**檔案**：[web/routes/market.py:43](../web/routes/market.py#L43)

**問題描述**：
`web/routes/market.py` 的 `get_market_data()` 路由呼叫 `container.get_market_data(period)`，但 `DataContainer` 類別（`core/container.py`）完全沒有這個方法。

**影響**：`GET /api/market-data` API 必定返回 HTTP 500 錯誤。

**現況**：
```python
# web/routes/market.py:43
data = container.get_market_data(period)  # ← AttributeError: DataContainer has no attribute 'get_market_data'
```

**根本原因**：`MarketDataLoader`（`web/market.py`）提供 `get_all_market_data()` 方法，但沒有被連接到 `DataContainer`。

**建議修復方向**：在 `DataContainer.__init__` 中初始化 `self.market_loader = MarketDataLoader()`，然後新增委派方法 `get_market_data()`、`get_kline()` 等。

---

### Issue #2：container.get_kline() 不存在

**檔案**：[web/routes/market.py:69](../web/routes/market.py#L69)、[web/routes/market.py:126](../web/routes/market.py#L126)、[web/routes/market.py:148](../web/routes/market.py#L148)

**問題描述**：多個路由呼叫 `container.get_kline(symbol, period)` 但方法不存在。

**影響**：
- `GET /api/kline/<symbol>` → HTTP 500
- `GET /api/market-status` → HTTP 500（用於判斷最新資料日期）
- `GET /api/date-info/<date>` → HTTP 500

---

### Issue #3：container.get_exchange_rate() 不存在

**檔案**：[web/routes/market.py:95](../web/routes/market.py#L95)

**問題描述**：`GET /api/exchange-rate` 路由呼叫 `container.get_exchange_rate()` 但方法不存在。

**影響**：`GET /api/exchange-rate` 必定返回 HTTP 500。

---

### Issue #4：container.get_exchange_rate_history() 不存在

**檔案**：[web/routes/market.py:100](../web/routes/market.py#L100)

**問題描述**：`GET /api/exchange-rate?history=true` 呼叫 `container.get_exchange_rate_history()` 但方法不存在。

---

### Issue #5：container.market_loader 屬性不存在（benchmark 曲線失效）

**檔案**：[web/routes/backtest.py:533](../web/routes/backtest.py#L533)、[web/routes/backtest.py:571](../web/routes/backtest.py#L571)、[web/routes/backtest.py:595](../web/routes/backtest.py#L595)

**問題描述**：`_calculate_benchmark_curve()` 函數嘗試存取 `container.market_loader.get_weighted_kline(...)`，但 `DataContainer` 沒有 `market_loader` 屬性。

**影響**：`POST /api/backtest/run` 的 `benchmark_curve` 欄位必定引發 `AttributeError`，除非外層 try/except 捕獲到錯誤後返回空陣列。

**現況**：由於整個 `run_backtest` 有大型 try/except，實際上會返回 `benchmark_curve: []`，但不會讓整個回測失敗。

---

## 🟡 高優先（維護風險）

### Issue #6：CONDITION_OPTIONS 重複定義

**檔案 1**：[backtest/config.py:11](../backtest/config.py#L11)（應為唯一真相來源）
**檔案 2**：[web/routes/backtest.py:31](../web/routes/backtest.py#L31)（重複定義）

**問題描述**：`CONDITION_OPTIONS` 字典在兩個檔案中各定義了一份，內容目前相同但未來可能出現偏差。

**影響**：若修改 `backtest/config.py` 中的選項，`web/routes/backtest.py` 不會自動同步，導致 `/api/backtest/config` API 返回過時的選項定義。

**建議修復**：`web/routes/backtest.py` 改為：
```python
from backtest.config import CONDITION_OPTIONS, DEFAULT_CONFIG
```

---

### Issue #7：DEFAULT_CONFIG 重複定義

**檔案 1**：[backtest/config.py:138](../backtest/config.py#L138)（唯一真相來源）
**檔案 2**：[web/routes/backtest.py:158](../web/routes/backtest.py#L158)（重複定義）

**問題描述**：同 Issue #6，`DEFAULT_CONFIG` 也在兩處定義。

---

### Issue #8：_build_close_df() 重複定義

**檔案 1**：[core/container.py:23](../core/container.py#L23)（`build_close_df` 函數）
**檔案 2**：[web/routes/backtest.py:470](../web/routes/backtest.py#L470)（`_build_close_df` 私有函數）

**問題描述**：完全相同的邏輯在兩處實作。若修改一處，另一處不會同步。

**建議修復**：`web/routes/backtest.py` 改為：
```python
from core.container import build_close_df
```

---

### Issue #9：_filter_by_market() 重複定義

**檔案 1**：[core/container.py:44](../core/container.py#L44)（`filter_by_market` 函數）
**檔案 2**：[web/routes/backtest.py:483](../web/routes/backtest.py#L483)（`_filter_by_market` 私有函數）

**問題描述**：同 Issue #8，邏輯完全相同。

---

### Issue #10：merge_config() 重複定義

**檔案 1**：[backtest/config.py:172](../backtest/config.py#L172)（`merge_config` 函數）
**檔案 2**：[web/routes/backtest.py:425](../web/routes/backtest.py#L425)（`_merge_config` 私有函數）

**問題描述**：合併使用者配置與預設值的邏輯在兩處各自實作，邏輯略有差異（`backtest/config.py` 版本支援 `start_date` / `end_date`，`web/routes/backtest.py` 版本不支援）。

---

## 🟢 低優先（改善建議）

### Issue #11：MarketDataLoader 未連接至 DataContainer

**背景**：`DataContainer`（`core/container.py`）初始化後並未建立 `MarketDataLoader` 實例，導致 Issues #1-#5。

**建議修復方向**：
1. 在 `DataContainer.load_or_fetch()` 中新增：
   ```python
   from web.market import MarketDataLoader
   self.market_loader = MarketDataLoader()
   ```
2. 新增委派方法 `get_market_data()`、`get_kline()`、`get_exchange_rate()`
3. 或考慮將 `MarketDataLoader` 移至 `core/` 層

> 注意：從 `core/` 引用 `web/` 會違反模組獨立性原則（見 ARCHITECTURE.md）。應考慮將市場資料載入邏輯移至 `core/` 或建立獨立的服務層。

---

### Issue #12：get_stock_ohlcv() 回傳 string index

**檔案**：[core/container.py:250](../core/container.py#L250)

**問題描述**：`get_stock_ohlcv()` 將 DatetimeIndex 轉為字串（`[:10]`），返回 string-indexed DataFrame。呼叫端需要注意 index 類型已改變。

---

### Issue #13：FX 匯率預設值硬編碼

**檔案**：[core/currency.py](../core/currency.py)

**問題描述**：當快取不存在時，`FX` 使用預設匯率 `32.0 TWD/USD`（硬編碼）。若市場匯率大幅偏離 32.0，計算結果將不準確。

**建議**：可考慮在 `FX` 初始化時若無快取則即時抓取最新匯率。

---

### Issue #14：寬泛的 except 遮蔽錯誤

**檔案**：[web/routes/stock.py:270](../web/routes/stock.py#L270)

**問題描述**：`except: continue` 會靜默吞掉所有例外，難以除錯。

---

## 版本歷史

| 日期 | 說明 |
|------|------|
| 2026-02 | 初版：依據代碼審閱建立問題清單 |
