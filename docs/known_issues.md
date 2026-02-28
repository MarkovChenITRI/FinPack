# 已知問題清單（技術債）

> 最後更新：2026-02-28（TM/YF 新增）
> 修復優先順序：🔴 嚴重（功能完全失效） → 🟡 高（維護風險） → 🟢 低（改善建議）

---

## Config 流程問題（Issues CF1–CF5）

> 標準流程：`DEFAULT_CONFIG → /api/backtest/config → this.config → applyConfigToDOM → _bindLiveUpdates → runBacktest → merge_config → engine_config → BacktestEngine`

| # | 優先 | 問題描述 | 位置 | 狀態 |
|---|------|----------|------|------|
| CF1 | 🔴 | `??` NaN 傳播：`parseFloat(v) ?? fallback` 無法攔截 NaN（`??` 只攔截 null/undefined），NaN 被 JSON.stringify 轉為 `null` 傳給後端，engine 的 `.get(key, default)` 返回 `null`（非 default），Python 數值比較 `< None` 拋出 TypeError → 500 錯誤 | `BacktestEngine.js` `_bindLiveUpdates`：`bt-sharpe-threshold`、`bt-growth-fail-threshold`、`bt-delayed-sharpe-threshold`、`bt-us-min-fee` | ✅ 已修復：改用 `Number.isFinite(p) ? p : fallback` |
| CF2 | 🔴 | JS 無 cache-busting：`<script src="/js/app.js">` 沒有版本參數，瀏覽器可能載入修復前的舊 JS（F1–F7 修復前不傳送 `this.config`，後端永遠收到空 payload → 使用 DEFAULT_CONFIG） | `templates/index.html:582`、`main.py` | ✅ 已修復：`serve_static` 對 `.js` 加 `Cache-Control: no-store`；`app.js` URL 加 `?v=20260228` |
| CF3 | 🟡 | `log_utils.py` 日誌誤導：仍記錄已廢棄的 `backtest_months`（永遠是 N/A），未記錄 `start_date`/`end_date` 的 config 設定值，無法從 log 確認前端參數是否正確傳達 | `backtest/log_utils.py:44` | ✅ 已修復：移除廢棄欄位，新增 `start_date`/`end_date`/`fees` logging |
| CF4 | 🟡 | `end_date=None → pd.Timestamp(datetime.today())` 產生帶時間的 tz-naive Timestamp，若 `close_df.index` 是 tz-aware 則 `searchsorted` 拋出 TypeError（`Cannot compare tz-naive and tz-aware`），造成 500 錯誤 | `web/routes/backtest.py:112`、`run.py:106` | ✅ 已修復：改用 `datetime.today().date()` 去除時間部分 |
| CF5 | 🟢 | 缺少 `bt-tw-min-fee` HTML 輸入框：台股最低手續費無法透過 UI 自訂（後端預設值 0 是正確的，但與美股三個費用輸入不對稱） | `templates/index.html`、`BacktestEngine.js` | 低優先，暫不修復 |

---

## 台股市場問題（Issues TM1–TM2）

> 台股回測相關的架構與資料問題

| # | 優先 | 問題描述 | 位置 | 狀態 |
|---|------|----------|------|------|
| TM1 | 🔴 | **`market` 未傳入 BacktestEngine → 台股零交易**：`engine_config` 缺少 `'market'` 欄位；`BacktestEngine._process_rebalance()` 內 `self.config.get('market', 'us')` 永遠回傳 `'us'`。當使用者選 `market='tw'` 時，`delayed`/`concentrated` 策略只查詢 `'US'` 排名，但 `indicators` 已被過濾為 TW-only → `sharpe_rank_by_country.get(date_str, {}).get('US', [])` 回傳空列表 → `avg_sharpe = 0 ≤ 0 = threshold` → 提前 `return` → 整個回測期間**完全無交易** | `web/routes/backtest.py:130`（engine_config）、`run.py:92`（config dict）、`backtest/engine.py:547,499`（`_process_rebalance` delayed/concentrated） | ✅ 已修復：`engine_config` 新增 `'market': config['market']`（API）；`config` 新增 `'market': market`（CLI） |
| TM2 | 🟡 | **多市場交易日歷未隔離**：`align_data_with_bfill` 以「有效交易日」的 `MIN_STOCKS_FOR_VALID_DAY=50` 門檻建立統一日期索引，實際上以美股交易日為主。TW 股票在美股假日（TW 有開市）的資料被過濾掉；在美股開市但 TW 休市的日子則以 bfill 填補假收盤價。當以 `market='tw'` 回測時，日期索引仍是美股日曆，導致 TW 股票 Sharpe/Growth 計算含有人工製造的零報酬日，略微失真。此問題在 TW 股票總數 < 50 時更嚴重（TW 實際交易日可能整批被過濾） | `core/align.py:46`、`core/config.py:47`（`MIN_STOCKS_FOR_VALID_DAY = 50`） | 🟡 待處理（低至中衝擊；若 watchlist TW 股票 ≥ 50 則影響輕微） |

---

## yfinance 快取穩健性問題（Issues YF1–YF4）

> 每日重啟 main.py 場景下的快取可靠性分析

| # | 優先 | 問題描述 | 位置 | 狀態 |
|---|------|----------|------|------|
| YF1 | 🟡 | **週末/假日後強制 refetch**：`load_stock_cache` 以**日曆天數**（非交易日）計算過期：`days_diff = (today - cache_data_date).days`。`CACHE_MAX_STALENESS_DAYS=1`，正常週末 `days_diff=3 > 1` → 每週一必然觸發完整重抓（TradingView + 100+ 檔 yfinance），啟動時間大幅延長。實際上，週末期間市場無異動，快取仍然有效。長假後的多天差距同理 | `core/data.py:231`（`load_stock_cache`）、`core/config.py:34`（`CACHE_MAX_STALENESS_DAYS`） | 🟡 待處理（可接受的權衡，但 Monday 啟動慢） |
| YF2 | 🟡 | **快取新鮮度使用單一 US 樣本股票**：`_get_cache_data_date` 以 `next(iter(raw_data))` 取樣本（通常是第一支 US 股票）。若某次 fetch 因網路問題遺漏部分 TW 股票（fetch_stock_history 拋出例外 → 跳過），TW 股票在快取中**靜默缺席**，但下次啟動時快取以 US 樣本判斷仍新鮮（`days_diff ≤ 1`）→ 不觸發 refetch → TW 股票永久缺失直到快取過期 | `core/data.py:168`（`_get_cache_data_date`）、`core/data.py:148-157`（`fetch_all_stock_data` 靜默跳過失敗） | 🟡 待處理 |
| YF3 | 🟢 | **yfinance 資料延遲問題**：美股收盤後到隔日 yfinance 更新可能有 15–30 分鐘延遲；台股收盤後延遲可能更長。若使用者在延遲視窗內啟動，當日最新收盤價尚未可用，但 `days_diff = 0` 或 `1`，快取判斷新鮮 → 使用前一日資料。目前系統無法區分「今日資料尚未釋出」與「今日資料已可用」 | `core/data.py:231`（staleness check） | 🟢 待處理（影響輕微；不影響歷史回測） |
| YF4 | 🟢 | **TW 特定停牌/限制股票**：yfinance 對台股（`.TW` / `.TWO`）的支援較美股不完整，部分流動性低的個股可能回傳空 DataFrame 或不完整歷史，觸發 `MIN_HISTORY_DAYS=100` 過濾後靜默略過，但不留下警告以外的記錄 | `core/data.py:152`（`MIN_HISTORY_DAYS` check）、`core/config.py:49` | 🟢 待處理（低影響）|

---

## 架構紀律問題（Issues AD1–AD6）

> 目標：唯一 config 源、嚴格介面、零重複。修復後 engine 不應存在任何 `.get(key, DEFAULT)` 備援

| # | 優先 | 問題描述 | 位置 | 狀態 |
|---|------|----------|------|------|
| AD1 | 🔴 | **engine.py 30+ 個 `.get(key,DEFAULT)` 備援含 9 個與 DEFAULT_CONFIG 不符的值**（見下表）：engine 使用自己的備援值而非 DEFAULT_CONFIG，若 config 漏傳某欄位，engine 靜默使用錯誤預設，不拋出任何錯誤 | `backtest/engine.py` | ✅ 已修復：移除所有備援；新增 `REQUIRED_CONFIG_KEYS` + `__init__` 缺欄位即拋 ValueError |
| AD2 | 🔴 | **回測執行 pipeline 重複 ~120 行**：`run.py:79-196`（CLI）與 `web/routes/backtest.py:73-200`（API）幾乎完全相同，邏輯修改需同步兩處，維護風險極高 | `run.py`、`web/routes/backtest.py` | ✅ 已修復：共用 pipeline 移至 `backtest/runner.py` |
| AD3 | 🟡 | **`merge_config()` 無驗證**：非法 market（如 `'invalid'`）、負數 capital、錯誤型別等皆被靜默接受，直到 engine 執行時才崩潰（或更糟：靜默產生錯誤結果） | `backtest/config.py:177` | ✅ 已修復：新增 `ConfigError` + `load_config()` 含完整驗證；`merge_config` 為別名 |
| AD4 | 🟡 | **`start_date` 備援 `'2020-01-01'` 在 run.py 而非 config.py**：預設值應集中在 DEFAULT_CONFIG，目前分散管理 | `run.py:115` | ✅ 已修復：`DEFAULT_CONFIG['start_date']` 為唯一來源；runner 直接讀取 |
| AD5 | 🟡 | **`fees` 備援直接使用 `FEES` 常數（兩處）**：`_buy_stocks`/`_sell_stocks` 內 `self.config.get('fees', FEES)` 使得 engine 與 core.config 產生直接耦合，且備援值可能與 DEFAULT_CONFIG 不同步 | `backtest/engine.py:637,702` | ✅ 已修復：改為 `self.config['fees']`；移除 `from core.config import FEES` |
| AD6 | 🟢 | **`merge_config` 命名不表達驗證語意**：函數命名應改為 `load_config` 以表達「載入並驗證」語意；保留 `merge_config` 作為向後相容別名 | `backtest/config.py:177` | ✅ 已修復：`load_config()` 為主函數；`merge_config = load_config` 為別名 |

**AD1 具體不符清單（engine.py 備援值 vs DEFAULT_CONFIG）**：

| 條件/欄位 | engine.py 備援值 | DEFAULT_CONFIG 值 | 影響 |
|-----------|-----------------|-------------------|------|
| `buy_cond['sharpe_threshold']['threshold']` | `0.5` | `1.0` | 買入 Sharpe 門檻不同（寬鬆 vs 嚴格） |
| `buy_cond['sharpe_streak']['top_n']` | `15` | `10` | 連續達標範圍不同 |
| `buy_cond['growth_streak']['days']` | `3` | `2` | 連續達標天數不同 |
| `buy_cond['growth_streak']['percentile']` | `50` | `30` | 百分位閾值不同 |
| `buy_cond['growth_rank']['top_n']` | `15` | `7` | 排名範圍不同 |
| `sell_cond['sharpe_fail']['periods']` | `3` | `2` | 賣出週期不同 |
| `strategy.get('type', 'batch')` | `'batch'` | `'delayed'` | 策略類型完全不同（最嚴重）|

---

## 待處理問題（Issues #12–#14）

| # | 優先 | 問題描述 | 位置 |
|---|------|----------|------|
| #12 | 🟢 | get_stock_analysis 部分邏輯可移至 core | `web/routes/stock.py` |
| #13 | 🟢 | market preload 失敗時無 fallback 提示 | `web/routes/market.py` |
| #14 | 🟢 | `except: continue` 過於寬泛 | `web/routes/stock.py:273` |

---

## 版本歷史

| 日期 | 修復內容 |
|------|----------|
| 2026-02-26 | Issues #1–#11, N1–N2（架構問題）|
| 2026-02-27 | Issues F1–F9（前端問題）|
| 2026-02-28 | Issues DT1–DT4（日期邏輯）；Issues DA1–DA3（全流程審計）；新增 CF1–CF5 |
| 2026-02-28 | Issue TM1 修復（台股零交易）；新增 TM2、YF1–YF4 分析 |
| 2026-02-28 | 新增 AD1–AD6（架構紀律問題）；待修復 |
