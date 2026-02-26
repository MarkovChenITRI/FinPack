"""
前後端邏輯比對測試 - 分段獨立測試

測試方法：
1. 用固定的小量數據
2. 模擬前端 JS 的邏輯（用 Python 實現）
3. 執行後端的對應邏輯
4. 比較結果
"""
import pandas as pd
import numpy as np

# =============================================================================
# 測試數據準備（模擬 5 檔股票、3 天數據）
# =============================================================================

# 模擬收盤價
dates = pd.to_datetime(['2025-01-06', '2025-01-07', '2025-01-08'])
tickers = ['AAPL', 'GOOGL', 'MSFT', 'TSLA', 'NVDA']
stock_info = {
    'AAPL': {'country': 'US', 'industry': 'Technology'},
    'GOOGL': {'country': 'US', 'industry': 'Technology'},
    'MSFT': {'country': 'US', 'industry': 'Software'},
    'TSLA': {'country': 'US', 'industry': 'Automotive'},
    'NVDA': {'country': 'US', 'industry': 'Semiconductors'},
}

# 模擬 Sharpe 排名（每天的排名）
# 假設 2025-01-08 的 Sharpe 排名是：NVDA > TSLA > MSFT > AAPL > GOOGL
sharpe_rank_by_country = {
    '2025-01-06': {'US': ['AAPL', 'MSFT', 'GOOGL', 'NVDA', 'TSLA']},
    '2025-01-07': {'US': ['MSFT', 'NVDA', 'AAPL', 'TSLA', 'GOOGL']},
    '2025-01-08': {'US': ['NVDA', 'TSLA', 'MSFT', 'AAPL', 'GOOGL']},
}

# 模擬 Growth 排名（排名變化）
growth_rank_by_country = {
    '2025-01-06': {'US': ['AAPL', 'MSFT', 'GOOGL', 'NVDA', 'TSLA']},
    '2025-01-07': {'US': ['NVDA', 'MSFT', 'TSLA', 'AAPL', 'GOOGL']},
    '2025-01-08': {'US': ['TSLA', 'NVDA', 'AAPL', 'MSFT', 'GOOGL']},
}

# 模擬 Sharpe 值（用於 sort_industry）
sharpe_values = {
    '2025-01-08': {'NVDA': 2.5, 'TSLA': 2.0, 'MSFT': 1.5, 'AAPL': 1.0, 'GOOGL': 0.5}
}


# =============================================================================
# 測試 1: sharpe_rank 條件
# =============================================================================

def test_sharpe_rank():
    """
    前端 JS 邏輯 (sharpe_rank.js):
    ```javascript
    filter(tickers, context) {
        const { ranking, stockInfo, market } = context;
        const topN = this.params.top_n || 15;
        
        const selectedTickers = new Set();
        if (market === 'us') {
            const usRanking = ranking.sharpe.US || [];
            usRanking.slice(0, topN).forEach(t => selectedTickers.add(t));
        }
        return tickers.filter(t => selectedTickers.has(t));
    }
    ```
    """
    print("\n" + "="*60)
    print("TEST 1: sharpe_rank 條件")
    print("="*60)
    
    # 測試參數
    date = '2025-01-08'
    market = 'us'
    top_n = 3  # 只取前 3 名
    input_tickers = tickers.copy()  # 全部 5 檔
    
    print(f"輸入: {input_tickers}")
    print(f"Sharpe 排名 (US): {sharpe_rank_by_country[date]['US']}")
    print(f"top_n: {top_n}")
    
    # === 模擬前端 JS 邏輯 ===
    selected_tickers_js = set()
    us_ranking = sharpe_rank_by_country[date].get('US', [])
    for t in us_ranking[:top_n]:
        selected_tickers_js.add(t)
    js_result = [t for t in input_tickers if t in selected_tickers_js]
    
    print(f"\n[前端 JS 邏輯]")
    print(f"  selectedTickers: {selected_tickers_js}")
    print(f"  結果: {js_result}")
    
    # === 後端 Python 邏輯 (check_in_sharpe_top_k) ===
    py_result = []
    for symbol in input_tickers:
        country = stock_info[symbol]['country']
        ranking = sharpe_rank_by_country[date].get(country, [])
        if symbol in ranking[:top_n]:
            py_result.append(symbol)
    
    print(f"\n[後端 Python 邏輯]")
    print(f"  結果: {py_result}")
    
    # === 比較 ===
    if set(js_result) == set(py_result):
        print(f"\n✅ sharpe_rank 邏輯一致!")
    else:
        print(f"\n❌ sharpe_rank 邏輯不一致!")
        print(f"  JS 有但 Python 沒有: {set(js_result) - set(py_result)}")
        print(f"  Python 有但 JS 沒有: {set(py_result) - set(js_result)}")
    
    return js_result, py_result


# =============================================================================
# 測試 2: growth_streak 條件
# =============================================================================

def test_growth_streak():
    """
    前端 JS 邏輯 (growth_streak.js):
    ```javascript
    filter(tickers, context) {
        const { history, date, market } = context;
        const periods = this.params.days || 3;
        const percentile = this.params.percentile || 50;
        
        // 取得最近 N 期的日期
        const dates = Object.keys(history.growthRank).sort();
        const currentIndex = dates.indexOf(date);
        const recentDates = dates.slice(currentIndex - periods + 1, currentIndex + 1);
        
        // 找出在所有期間都在排名前 X% 的股票
        const consistentTickers = new Set(tickers);
        
        for (const d of recentDates) {
            const dayRank = history.growthRank[d];
            const topPctSet = new Set();
            const usRanking = dayRank.US || [];
            const topN = Math.ceil(usRanking.length * percentile / 100);
            usRanking.slice(0, topN).forEach(t => topPctSet.add(t));
            
            // 移除不在該期排名前 X% 的股票
            for (const ticker of consistentTickers) {
                if (!topPctSet.has(ticker)) {
                    consistentTickers.delete(ticker);
                }
            }
        }
        return Array.from(consistentTickers);
    }
    ```
    """
    print("\n" + "="*60)
    print("TEST 2: growth_streak 條件")
    print("="*60)
    
    # 測試參數
    current_date = '2025-01-08'
    market = 'us'
    periods = 3  # 連續 3 天
    percentile = 50  # 前 50%
    input_tickers = tickers.copy()
    
    print(f"輸入: {input_tickers}")
    print(f"periods: {periods}, percentile: {percentile}%")
    
    # === 模擬前端 JS 邏輯 ===
    all_dates = sorted(growth_rank_by_country.keys())
    current_idx = all_dates.index(current_date)
    recent_dates = all_dates[max(0, current_idx - periods + 1):current_idx + 1]
    
    print(f"recent_dates: {recent_dates}")
    
    consistent_tickers_js = set(input_tickers)
    
    for d in recent_dates:
        day_rank = growth_rank_by_country[d]
        us_ranking = day_rank.get('US', [])
        top_n = max(1, int(len(us_ranking) * percentile / 100))
        top_pct_set = set(us_ranking[:top_n])
        
        print(f"  {d}: US ranking = {us_ranking}, top {percentile}% = {top_pct_set}")
        
        to_remove = []
        for ticker in consistent_tickers_js:
            if ticker not in top_pct_set:
                to_remove.append(ticker)
        for t in to_remove:
            consistent_tickers_js.remove(t)
    
    js_result = list(consistent_tickers_js)
    
    print(f"\n[前端 JS 邏輯]")
    print(f"  結果: {js_result}")
    
    # === 後端 Python 邏輯 (check_growth_streak) ===
    py_result = []
    for symbol in input_tickers:
        country = stock_info[symbol]['country']
        
        # 檢查連續 periods 天都在前 percentile%
        all_passed = True
        for i in range(periods):
            check_idx = current_idx - i
            if check_idx < 0:
                all_passed = False
                break
            d = all_dates[check_idx]
            ranking = growth_rank_by_country[d].get(country, [])
            if not ranking:
                all_passed = False
                break
            top_n = max(1, int(len(ranking) * percentile / 100))
            if symbol not in ranking[:top_n]:
                all_passed = False
                break
        
        if all_passed:
            py_result.append(symbol)
    
    print(f"\n[後端 Python 邏輯]")
    print(f"  結果: {py_result}")
    
    # === 比較 ===
    if set(js_result) == set(py_result):
        print(f"\n✅ growth_streak 邏輯一致!")
    else:
        print(f"\n❌ growth_streak 邏輯不一致!")
        print(f"  JS 有但 Python 沒有: {set(js_result) - set(py_result)}")
        print(f"  Python 有但 JS 沒有: {set(py_result) - set(js_result)}")
    
    return js_result, py_result


# =============================================================================
# 測試 3: sort_industry 條件
# =============================================================================

def test_sort_industry():
    """
    前端 JS 邏輯 (sort_industry.js):
    ```javascript
    filter(tickers, context) {
        const { sharpeValues, stockInfo } = context;
        const { perIndustry } = this.params;  // 預設 2
        
        // 按產業分組
        const industryGroups = {};
        for (const ticker of tickers) {
            const industry = stockInfo[ticker]?.industry || '未分類';
            if (!industryGroups[industry]) industryGroups[industry] = [];
            industryGroups[industry].push({ ticker, sharpe: sharpeValues[ticker] });
        }
        
        // 每個產業按 Sharpe 排序
        for (const industry in industryGroups) {
            industryGroups[industry].sort((a, b) => b.sharpe - a.sharpe);
        }
        
        // 按產業內最高 Sharpe 排序產業
        const industries = Object.keys(industryGroups).sort((a, b) => {
            return (industryGroups[b][0]?.sharpe || 0) - (industryGroups[a][0]?.sharpe || 0);
        });
        
        // 輪流從每個產業選取
        const selected = [];
        const industryCount = {};
        let hasMore = true;
        while (hasMore) {
            hasMore = false;
            for (const industry of industries) {
                const count = industryCount[industry] || 0;
                if (count >= perIndustry) continue;
                const stock = industryGroups[industry][count];
                if (stock) {
                    selected.push(stock.ticker);
                    industryCount[industry] = count + 1;
                    hasMore = true;
                }
            }
        }
        return selected;
    }
    ```
    """
    print("\n" + "="*60)
    print("TEST 3: sort_industry 條件")
    print("="*60)
    
    # 測試參數
    date = '2025-01-08'
    per_industry = 2
    input_tickers = tickers.copy()
    
    print(f"輸入: {input_tickers}")
    print(f"per_industry: {per_industry}")
    print(f"Sharpe 值: {sharpe_values[date]}")
    print(f"產業分布:")
    for t in input_tickers:
        print(f"  {t}: {stock_info[t]['industry']}, sharpe={sharpe_values[date].get(t, 0)}")
    
    # === 模擬前端 JS 邏輯 ===
    industry_groups_js = {}
    for ticker in input_tickers:
        industry = stock_info.get(ticker, {}).get('industry', '未分類')
        if industry not in industry_groups_js:
            industry_groups_js[industry] = []
        industry_groups_js[industry].append({
            'ticker': ticker,
            'sharpe': sharpe_values[date].get(ticker, 0)
        })
    
    # 每個產業按 Sharpe 排序
    for industry in industry_groups_js:
        industry_groups_js[industry].sort(key=lambda x: x['sharpe'], reverse=True)
    
    # 按產業內最高 Sharpe 排序產業
    industries_js = sorted(
        industry_groups_js.keys(),
        key=lambda i: industry_groups_js[i][0]['sharpe'] if industry_groups_js[i] else 0,
        reverse=True
    )
    
    print(f"\n[前端 JS 邏輯]")
    print(f"  產業分組後:")
    for ind in industries_js:
        stocks = [(s['ticker'], s['sharpe']) for s in industry_groups_js[ind]]
        print(f"    {ind}: {stocks}")
    print(f"  產業順序 (按最高 Sharpe): {industries_js}")
    
    # 輪流選取
    selected_js = []
    industry_count_js = {}
    has_more = True
    max_rounds = per_industry * len(industries_js) + 1
    round_count = 0
    
    while has_more and round_count < max_rounds:
        has_more = False
        for industry in industries_js:
            count = industry_count_js.get(industry, 0)
            if count >= per_industry:
                continue
            if count < len(industry_groups_js[industry]):
                selected_js.append(industry_groups_js[industry][count]['ticker'])
                industry_count_js[industry] = count + 1
                has_more = True
        round_count += 1
    
    print(f"  選取順序: {selected_js}")
    
    # === 後端 Python 邏輯 (engine.py _select_stocks) ===
    # 模擬候選人資料
    candidates = []
    for symbol in input_tickers:
        candidates.append({
            'symbol': symbol,
            'sharpe': sharpe_values[date].get(symbol, 0),
            'industry': stock_info.get(symbol, {}).get('industry', 'Unknown')
        })
    
    # 按產業分組
    industry_groups_py = {}
    for c in candidates:
        ind = c['industry']
        if ind not in industry_groups_py:
            industry_groups_py[ind] = []
        industry_groups_py[ind].append(c)
    
    # 每個產業按 Sharpe 排序
    for ind in industry_groups_py:
        industry_groups_py[ind].sort(
            key=lambda x: x['sharpe'] if x['sharpe'] is not None else -999,
            reverse=True
        )
    
    # 按產業內最高 Sharpe 排序產業順序
    industries_py = sorted(
        industry_groups_py.keys(),
        key=lambda i: (industry_groups_py[i][0]['sharpe']
                      if industry_groups_py[i][0]['sharpe'] is not None else -999),
        reverse=True
    )
    
    # 輪流從每個產業選取
    selected_py = []
    industry_count_py = {}
    has_more = True
    max_rounds = per_industry * len(industries_py) + 1
    round_count = 0
    
    while has_more and round_count < max_rounds:
        has_more = False
        for ind in industries_py:
            count = industry_count_py.get(ind, 0)
            if count >= per_industry:
                continue
            if count < len(industry_groups_py[ind]):
                selected_py.append(industry_groups_py[ind][count]['symbol'])
                industry_count_py[ind] = count + 1
                has_more = True
        round_count += 1
    
    print(f"\n[後端 Python 邏輯]")
    print(f"  產業順序: {industries_py}")
    print(f"  選取順序: {selected_py}")
    
    # === 比較 ===
    if selected_js == selected_py:
        print(f"\n✅ sort_industry 邏輯一致! (順序也相同)")
    elif set(selected_js) == set(selected_py):
        print(f"\n⚠️ sort_industry 結果相同但順序不同!")
        print(f"  JS 順序:     {selected_js}")
        print(f"  Python 順序: {selected_py}")
    else:
        print(f"\n❌ sort_industry 邏輯不一致!")
        print(f"  JS 有但 Python 沒有: {set(selected_js) - set(selected_py)}")
        print(f"  Python 有但 JS 沒有: {set(selected_py) - set(selected_js)}")
    
    return selected_js, selected_py


# =============================================================================
# 測試 4: 完整流程（A+B+C 條件串接）
# =============================================================================

def test_full_flow():
    """測試完整的買入條件串接流程"""
    print("\n" + "="*60)
    print("TEST 4: 完整流程 (sharpe_rank → growth_streak → sort_industry)")
    print("="*60)
    
    date = '2025-01-08'
    top_n = 3
    periods = 2  # 為了測試能通過，改成 2 天
    percentile = 60  # 60% = 5 檔取 3 檔
    per_industry = 2
    
    print(f"參數: top_n={top_n}, periods={periods}, percentile={percentile}%, per_industry={per_industry}")
    
    # Step 1: sharpe_rank
    candidates = tickers.copy()
    print(f"\n[Step 1] sharpe_rank 輸入: {candidates}")
    
    us_ranking = sharpe_rank_by_country[date].get('US', [])
    selected_set = set(us_ranking[:top_n])
    candidates = [t for t in candidates if t in selected_set]
    print(f"  Sharpe Top {top_n}: {us_ranking[:top_n]}")
    print(f"  sharpe_rank 輸出: {candidates}")
    
    # Step 2: growth_streak
    print(f"\n[Step 2] growth_streak 輸入: {candidates}")
    
    all_dates = sorted(growth_rank_by_country.keys())
    current_idx = all_dates.index(date)
    recent_dates = all_dates[max(0, current_idx - periods + 1):current_idx + 1]
    
    consistent = set(candidates)
    for d in recent_dates:
        us_ranking = growth_rank_by_country[d].get('US', [])
        top_n_growth = max(1, int(len(us_ranking) * percentile / 100))
        top_set = set(us_ranking[:top_n_growth])
        print(f"  {d}: top {percentile}% = {list(top_set)}")
        consistent = consistent & top_set
    
    candidates = [t for t in candidates if t in consistent]
    print(f"  growth_streak 輸出: {candidates}")
    
    # Step 3: sort_industry
    print(f"\n[Step 3] sort_industry 輸入: {candidates}")
    
    if candidates:
        # 按產業分組
        industry_groups = {}
        for t in candidates:
            ind = stock_info[t]['industry']
            if ind not in industry_groups:
                industry_groups[ind] = []
            industry_groups[ind].append({
                'ticker': t,
                'sharpe': sharpe_values[date].get(t, 0)
            })
        
        # 排序
        for ind in industry_groups:
            industry_groups[ind].sort(key=lambda x: x['sharpe'], reverse=True)
        
        industries = sorted(
            industry_groups.keys(),
            key=lambda i: industry_groups[i][0]['sharpe'],
            reverse=True
        )
        
        # 輪流選取
        selected = []
        count = {}
        has_more = True
        while has_more:
            has_more = False
            for ind in industries:
                c = count.get(ind, 0)
                if c >= per_industry:
                    continue
                if c < len(industry_groups[ind]):
                    selected.append(industry_groups[ind][c]['ticker'])
                    count[ind] = c + 1
                    has_more = True
        
        candidates = selected
    
    print(f"  sort_industry 輸出: {candidates}")
    print(f"\n最終候選: {candidates}")
    
    return candidates


# =============================================================================
# 主程式
# =============================================================================

if __name__ == '__main__':
    print("="*60)
    print("前後端邏輯比對測試")
    print("="*60)
    
    test_sharpe_rank()
    test_growth_streak()
    test_sort_industry()
    test_full_flow()
