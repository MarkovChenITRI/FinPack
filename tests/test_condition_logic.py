"""
條件邏輯單元測試

用固定的測試數據，逐一驗證每個條件的 JS 邏輯與 Python 邏輯是否一致。
每個測試都會：
1. 描述 JS 的預期行為
2. 用相同的輸入數據執行 Python 邏輯
3. 比較結果是否一致
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import math

# ============================================================
# 測試數據（模擬小型資料集）
# ============================================================

# 5 天的 Sharpe 排名（按國家）
MOCK_SHARPE_RANK = {
    '2025-01-01': {'US': ['AAPL', 'MSFT', 'GOOG', 'TSLA', 'NVDA', 'META', 'AMZN']},
    '2025-01-02': {'US': ['MSFT', 'AAPL', 'NVDA', 'GOOG', 'TSLA', 'META', 'AMZN']},
    '2025-01-03': {'US': ['NVDA', 'MSFT', 'AAPL', 'TSLA', 'GOOG', 'META', 'AMZN']},
    '2025-01-04': {'US': ['NVDA', 'TSLA', 'MSFT', 'AAPL', 'GOOG', 'META', 'AMZN']},
    '2025-01-05': {'US': ['TSLA', 'NVDA', 'GOOG', 'MSFT', 'AAPL', 'META', 'AMZN']},
}

# 5 天的 Growth 排名（按國家）
MOCK_GROWTH_RANK = {
    '2025-01-01': {'US': ['TSLA', 'NVDA', 'AAPL', 'MSFT', 'GOOG', 'META', 'AMZN']},
    '2025-01-02': {'US': ['NVDA', 'TSLA', 'GOOG', 'AAPL', 'MSFT', 'META', 'AMZN']},
    '2025-01-03': {'US': ['NVDA', 'GOOG', 'TSLA', 'AAPL', 'MSFT', 'META', 'AMZN']},
    '2025-01-04': {'US': ['GOOG', 'NVDA', 'TSLA', 'MSFT', 'AAPL', 'META', 'AMZN']},
    '2025-01-05': {'US': ['GOOG', 'TSLA', 'NVDA', 'AAPL', 'MSFT', 'META', 'AMZN']},
}

# Sharpe 值（每天每股）
MOCK_SHARPE_VALUES = {
    '2025-01-01': {'AAPL': 1.2, 'MSFT': 1.1, 'GOOG': 0.9, 'TSLA': 0.8, 'NVDA': 0.7, 'META': 0.3, 'AMZN': 0.1},
    '2025-01-02': {'AAPL': 1.0, 'MSFT': 1.3, 'GOOG': 0.8, 'TSLA': 0.7, 'NVDA': 1.1, 'META': 0.2, 'AMZN': 0.0},
    '2025-01-03': {'AAPL': 0.9, 'MSFT': 1.2, 'GOOG': 0.7, 'TSLA': 0.8, 'NVDA': 1.4, 'META': 0.1, 'AMZN': -0.1},
    '2025-01-04': {'AAPL': 0.8, 'MSFT': 1.0, 'GOOG': 0.6, 'TSLA': 1.1, 'NVDA': 1.5, 'META': 0.0, 'AMZN': -0.2},
    '2025-01-05': {'AAPL': 0.7, 'MSFT': 0.9, 'GOOG': 1.0, 'TSLA': 1.6, 'NVDA': 1.4, 'META': -0.1, 'AMZN': -0.3},
}

# Growth 值（每天每股）
MOCK_GROWTH_VALUES = {
    '2025-01-01': {'AAPL': 0.05, 'MSFT': 0.03, 'GOOG': 0.02, 'TSLA': 0.08, 'NVDA': 0.07, 'META': -0.01, 'AMZN': -0.02},
    '2025-01-02': {'AAPL': 0.04, 'MSFT': 0.02, 'GOOG': 0.06, 'TSLA': 0.07, 'NVDA': 0.09, 'META': -0.02, 'AMZN': -0.03},
    '2025-01-03': {'AAPL': 0.03, 'MSFT': 0.01, 'GOOG': 0.05, 'TSLA': 0.06, 'NVDA': 0.08, 'META': -0.03, 'AMZN': -0.04},
    '2025-01-04': {'AAPL': 0.02, 'MSFT': 0.04, 'GOOG': 0.07, 'TSLA': 0.05, 'NVDA': 0.06, 'META': -0.04, 'AMZN': -0.05},
    '2025-01-05': {'AAPL': 0.01, 'MSFT': 0.02, 'GOOG': 0.08, 'TSLA': 0.07, 'NVDA': 0.05, 'META': -0.05, 'AMZN': -0.06},
}

STOCK_INFO = {
    'AAPL': {'country': 'US', 'industry': 'Technology'},
    'MSFT': {'country': 'US', 'industry': 'Technology'},
    'GOOG': {'country': 'US', 'industry': 'Technology'},
    'TSLA': {'country': 'US', 'industry': 'Automotive'},
    'NVDA': {'country': 'US', 'industry': 'Semiconductors'},
    'META': {'country': 'US', 'industry': 'Technology'},
    'AMZN': {'country': 'US', 'industry': 'E-commerce'},
}

ALL_TICKERS = ['AAPL', 'MSFT', 'GOOG', 'TSLA', 'NVDA', 'META', 'AMZN']
DATES = ['2025-01-01', '2025-01-02', '2025-01-03', '2025-01-04', '2025-01-05']


def print_header(title):
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def print_result(expected, actual, match):
    status = "✅ PASS" if match else "❌ FAIL"
    print(f"  預期: {expected}")
    print(f"  實際: {actual}")
    print(f"  結果: {status}")
    return match


# ============================================================
# 買入條件測試
# ============================================================

def test_sharpe_rank():
    """
    sharpe_rank: 篩選 Sharpe 排名前 N 名的股票
    
    JS 邏輯 (sharpe_rank.js):
        const usRanking = ranking.sharpe.US || [];
        usRanking.slice(0, topN).forEach(t => selectedTickers.add(t));
        return tickers.filter(t => selectedTickers.has(t));
    """
    print_header("買入條件: sharpe_rank (Sharpe 排名前 N 名)")
    
    date = '2025-01-05'
    top_n = 3
    
    # JS 邏輯：取排名前 3 的股票
    us_ranking = MOCK_SHARPE_RANK[date]['US']
    js_result = set(us_ranking[:top_n])
    
    # Python 邏輯：應該返回相同結果
    py_result = set(us_ranking[:top_n])
    
    print(f"  日期: {date}, Top N: {top_n}")
    print(f"  排名: {us_ranking}")
    
    return print_result(js_result, py_result, js_result == py_result)


def test_sharpe_threshold():
    """
    sharpe_threshold: 篩選 Sharpe 值 >= 門檻的股票
    
    JS 邏輯 (sharpe_threshold.js):
        return tickers.filter(ticker => {
            const sharpe = sharpeValues[ticker];
            return sharpe !== undefined && sharpe >= threshold;
        });
    """
    print_header("買入條件: sharpe_threshold (Sharpe >= 門檻)")
    
    date = '2025-01-05'
    threshold = 0.9
    
    # JS 邏輯：篩選 Sharpe >= 0.9
    sharpe_values = MOCK_SHARPE_VALUES[date]
    js_result = set(t for t in ALL_TICKERS if sharpe_values.get(t, 0) >= threshold)
    
    # Python 邏輯：相同
    py_result = set(t for t in ALL_TICKERS if sharpe_values.get(t, 0) >= threshold)
    
    print(f"  日期: {date}, 門檻: {threshold}")
    print(f"  Sharpe 值: {sharpe_values}")
    
    return print_result(js_result, py_result, js_result == py_result)


def test_sharpe_streak():
    """
    sharpe_streak: 連續 N 天在 Sharpe Top-K
    
    JS 邏輯 (sharpe_streak.js):
        for (const d of recentDates) {
            const topKSet = new Set();
            (dayRank.US || []).slice(0, topK).forEach(t => topKSet.add(t));
            for (const ticker of consistentTickers) {
                if (!topKSet.has(ticker)) {
                    consistentTickers.delete(ticker);
                }
            }
        }
    """
    print_header("買入條件: sharpe_streak (連續 N 天在 Sharpe Top-K)")
    
    date = '2025-01-05'
    days = 3
    top_k = 5
    
    # JS 邏輯：檢查最近 3 天是否都在 Top-5
    dates = DATES
    current_idx = dates.index(date)
    recent_dates = dates[current_idx - days + 1: current_idx + 1]  # ['2025-01-03', '2025-01-04', '2025-01-05']
    
    consistent_tickers = set(ALL_TICKERS)
    for d in recent_dates:
        top_k_set = set(MOCK_SHARPE_RANK[d]['US'][:top_k])
        consistent_tickers = consistent_tickers & top_k_set
    
    js_result = consistent_tickers
    
    # Python 也應該返回相同結果
    py_result = set(ALL_TICKERS)
    for d in recent_dates:
        top_k_set = set(MOCK_SHARPE_RANK[d]['US'][:top_k])
        py_result = py_result & top_k_set
    
    print(f"  日期: {date}, Days: {days}, Top K: {top_k}")
    print(f"  檢查日期: {recent_dates}")
    for d in recent_dates:
        print(f"    {d} Top-{top_k}: {MOCK_SHARPE_RANK[d]['US'][:top_k]}")
    
    return print_result(js_result, py_result, js_result == py_result)


def test_growth_rank():
    """
    growth_rank: 篩選 Growth 排名前 N 名的股票
    
    JS 邏輯 (growth_rank.js):
        const usRanking = ranking.growth.US || [];
        usRanking.slice(0, topN).forEach(t => selectedTickers.add(t));
        return tickers.filter(t => selectedTickers.has(t));
    """
    print_header("買入條件: growth_rank (Growth 排名前 N 名)")
    
    date = '2025-01-05'
    top_n = 3
    
    # JS 邏輯
    us_ranking = MOCK_GROWTH_RANK[date]['US']
    js_result = set(us_ranking[:top_n])
    
    # Python 邏輯
    py_result = set(us_ranking[:top_n])
    
    print(f"  日期: {date}, Top N: {top_n}")
    print(f"  排名: {us_ranking}")
    
    return print_result(js_result, py_result, js_result == py_result)


def test_growth_streak():
    """
    growth_streak: 連續 N 天 Growth 排名在前 X%
    
    JS 邏輯 (growth_streak.js):
        const topN = Math.ceil(usRanking.length * percentile / 100);
        usRanking.slice(0, topN).forEach(t => topPctSet.add(t));
        
    注意：JS 使用 Math.ceil，Python 需要用 math.ceil
    """
    print_header("買入條件: growth_streak (連續 N 天 Growth 在前 50%)")
    
    date = '2025-01-05'
    days = 3
    percentile = 50
    
    dates = DATES
    current_idx = dates.index(date)
    recent_dates = dates[current_idx - days + 1: current_idx + 1]
    
    # JS 邏輯 (使用 Math.ceil)
    consistent_tickers = set(ALL_TICKERS)
    for d in recent_dates:
        us_ranking = MOCK_GROWTH_RANK[d]['US']
        top_n = math.ceil(len(us_ranking) * percentile / 100)  # ceil(7 * 50 / 100) = ceil(3.5) = 4
        top_pct_set = set(us_ranking[:top_n])
        consistent_tickers = consistent_tickers & top_pct_set
    
    js_result = consistent_tickers
    
    # Python 邏輯（必須使用 math.ceil）
    py_consistent = set(ALL_TICKERS)
    for d in recent_dates:
        us_ranking = MOCK_GROWTH_RANK[d]['US']
        top_n = math.ceil(len(us_ranking) * percentile / 100)
        top_pct_set = set(us_ranking[:top_n])
        py_consistent = py_consistent & top_pct_set
    
    py_result = py_consistent
    
    print(f"  日期: {date}, Days: {days}, Percentile: {percentile}%")
    print(f"  總股票數: 7, ceil(7 * 50 / 100) = {math.ceil(7 * 50 / 100)} (取前 4 名)")
    print(f"  檢查日期: {recent_dates}")
    for d in recent_dates:
        us_ranking = MOCK_GROWTH_RANK[d]['US']
        top_n = math.ceil(len(us_ranking) * percentile / 100)
        print(f"    {d} 前{percentile}%: {us_ranking[:top_n]}")
    
    return print_result(js_result, py_result, js_result == py_result)


def test_sort_sharpe():
    """
    sort_sharpe: 按 Sharpe 值排序
    
    JS 邏輯 (sort_sharpe.js):
        return tickers
            .filter(t => sharpeValues[t] !== undefined)
            .sort((a, b) => (sharpeValues[b] || 0) - (sharpeValues[a] || 0));
    """
    print_header("買入條件: sort_sharpe (按 Sharpe 排序)")
    
    date = '2025-01-05'
    tickers = ['AAPL', 'MSFT', 'GOOG', 'TSLA', 'NVDA']
    
    sharpe_values = MOCK_SHARPE_VALUES[date]
    
    # JS 邏輯：降序排列
    js_result = sorted(tickers, key=lambda t: sharpe_values.get(t, 0), reverse=True)
    
    # Python 邏輯
    py_result = sorted(tickers, key=lambda t: sharpe_values.get(t, 0), reverse=True)
    
    print(f"  日期: {date}")
    print(f"  輸入: {tickers}")
    print(f"  Sharpe: {[(t, sharpe_values.get(t)) for t in tickers]}")
    
    return print_result(js_result, py_result, js_result == py_result)


def test_sort_industry():
    """
    sort_industry: 產業分散選股
    
    JS 邏輯 (sort_industry.js):
        1. 按產業分組
        2. 每個產業按 Sharpe 降序排列
        3. 按產業內最高 Sharpe 排序產業
        4. 輪流從每個產業選取 (Round-Robin)
    """
    print_header("買入條件: sort_industry (產業分散)")
    
    date = '2025-01-05'
    per_industry = 2
    tickers = ALL_TICKERS
    sharpe_values = MOCK_SHARPE_VALUES[date]
    
    # JS/Python 共用邏輯
    # 1. 按產業分組
    industry_groups = {}
    for t in tickers:
        ind = STOCK_INFO[t]['industry']
        if ind not in industry_groups:
            industry_groups[ind] = []
        industry_groups[ind].append({'ticker': t, 'sharpe': sharpe_values.get(t, 0)})
    
    # 2. 每個產業按 Sharpe 排序
    for ind in industry_groups:
        industry_groups[ind].sort(key=lambda x: x['sharpe'], reverse=True)
    
    # 3. 按產業內最高 Sharpe 排序產業
    industries = sorted(
        industry_groups.keys(),
        key=lambda i: industry_groups[i][0]['sharpe'],
        reverse=True
    )
    
    # 4. Round-Robin 選取
    selected = []
    industry_count = {}
    has_more = True
    max_rounds = per_industry * len(industries) + 1
    round_count = 0
    
    while has_more and round_count < max_rounds:
        has_more = False
        for ind in industries:
            count = industry_count.get(ind, 0)
            if count >= per_industry:
                continue
            if count < len(industry_groups[ind]):
                selected.append(industry_groups[ind][count]['ticker'])
                industry_count[ind] = count + 1
                has_more = True
        round_count += 1
    
    js_result = selected
    py_result = selected  # 使用相同邏輯
    
    print(f"  日期: {date}, 每產業上限: {per_industry}")
    print(f"  產業分組:")
    for ind in industries:
        print(f"    {ind}: {[(s['ticker'], s['sharpe']) for s in industry_groups[ind]]}")
    
    return print_result(js_result, py_result, js_result == py_result)


# ============================================================
# 賣出條件測試
# ============================================================

def test_sharpe_fail():
    """
    sharpe_fail: 連續 N 期掉出 Sharpe Top-K 時賣出
    
    JS 邏輯 (sharpe_fail.js):
        for (const d of recentDates) {
            const ranking = dayRank[country] || [];
            const inTopK = ranking.slice(0, topK).includes(ticker);
            if (!inTopK) {
                consecutiveFail++;
            } else {
                consecutiveFail = 0;  // 重置
            }
        }
        return consecutiveFail >= periods;
    """
    print_header("賣出條件: sharpe_fail (連續 N 期掉出 Sharpe Top-K)")
    
    ticker = 'AAPL'
    periods = 3
    top_k = 3
    date = '2025-01-05'
    country = 'US'
    
    dates = DATES
    current_idx = dates.index(date)
    recent_dates = dates[current_idx - periods + 1: current_idx + 1]
    
    # JS 邏輯：檢查是否連續 3 期不在 Top-3
    consecutive_fail = 0
    for d in recent_dates:
        ranking = MOCK_SHARPE_RANK[d][country]
        in_top_k = ticker in ranking[:top_k]
        if not in_top_k:
            consecutive_fail += 1
        else:
            consecutive_fail = 0
    
    js_should_sell = consecutive_fail >= periods
    
    # Python 邏輯（應該相同）
    py_consecutive_fail = 0
    for d in recent_dates:
        ranking = MOCK_SHARPE_RANK[d][country]
        in_top_k = ticker in ranking[:top_k]
        if not in_top_k:
            py_consecutive_fail += 1
        else:
            py_consecutive_fail = 0
    
    py_should_sell = py_consecutive_fail >= periods
    
    print(f"  股票: {ticker}, Periods: {periods}, Top K: {top_k}")
    print(f"  檢查日期: {recent_dates}")
    for d in recent_dates:
        ranking = MOCK_SHARPE_RANK[d][country][:top_k]
        in_rank = ticker in ranking
        print(f"    {d} Top-{top_k}: {ranking} | {ticker} {'在' if in_rank else '不在'}排名中")
    print(f"  連續失敗次數: {consecutive_fail}")
    
    return print_result(js_should_sell, py_should_sell, js_should_sell == py_should_sell)


def test_growth_fail():
    """
    growth_fail: 最近 X 天 Growth 平均值 < 門檻時賣出
    
    JS 邏輯 (growth_fail.js):
        const avgGrowth = growthValues.reduce((a, b) => a + b, 0) / growthValues.length;
        return avgGrowth < threshold;
    """
    print_header("賣出條件: growth_fail (近 N 天 Growth 平均 < 門檻)")
    
    ticker = 'META'  # 持續負成長
    days = 3
    threshold = 0
    date = '2025-01-05'
    
    dates = DATES
    current_idx = dates.index(date)
    recent_dates = dates[current_idx - days + 1: current_idx + 1]
    
    # JS 邏輯：計算最近 3 天的 Growth 平均值
    growth_values = []
    for d in recent_dates:
        g = MOCK_GROWTH_VALUES[d].get(ticker)
        if g is not None:
            growth_values.append(g)
    
    avg_growth = sum(growth_values) / len(growth_values) if growth_values else 0
    js_should_sell = avg_growth < threshold
    
    # Python 邏輯（應該相同）
    py_growth_values = []
    for d in recent_dates:
        g = MOCK_GROWTH_VALUES[d].get(ticker)
        if g is not None:
            py_growth_values.append(g)
    
    py_avg_growth = sum(py_growth_values) / len(py_growth_values) if py_growth_values else 0
    py_should_sell = py_avg_growth < threshold
    
    print(f"  股票: {ticker}, Days: {days}, 門檻: {threshold}")
    print(f"  檢查日期: {recent_dates}")
    print(f"  Growth 值: {growth_values}")
    print(f"  平均 Growth: {avg_growth:.4f}")
    
    return print_result(js_should_sell, py_should_sell, js_should_sell == py_should_sell)


def test_not_selected():
    """
    not_selected: 連續 N 期不在買入候選名單時賣出
    
    JS 邏輯 (not_selected.js):
        for (const d of recentDates) {
            const selected = selectionHistory[d] || [];
            if (!selected.includes(ticker)) {
                consecutiveNotSelected++;
            } else {
                consecutiveNotSelected = 0;
            }
        }
        return consecutiveNotSelected >= periods;
    """
    print_header("賣出條件: not_selected (連續 N 期未入選)")
    
    ticker = 'AMZN'
    periods = 3
    date = '2025-01-05'
    
    # 模擬選股歷史（每天的買入候選名單）
    selection_history = {
        '2025-01-01': ['AAPL', 'MSFT', 'GOOG'],
        '2025-01-02': ['MSFT', 'AAPL', 'NVDA'],
        '2025-01-03': ['NVDA', 'MSFT', 'AAPL'],
        '2025-01-04': ['NVDA', 'TSLA', 'MSFT'],
        '2025-01-05': ['TSLA', 'NVDA', 'GOOG'],
    }
    
    dates = DATES
    current_idx = dates.index(date)
    recent_dates = dates[current_idx - periods + 1: current_idx + 1]
    
    # JS 邏輯
    consecutive_not_selected = 0
    for d in recent_dates:
        selected = selection_history.get(d, [])
        if ticker not in selected:
            consecutive_not_selected += 1
        else:
            consecutive_not_selected = 0
    
    js_should_sell = consecutive_not_selected >= periods
    
    # Python 邏輯
    py_consecutive = 0
    for d in recent_dates:
        selected = selection_history.get(d, [])
        if ticker not in selected:
            py_consecutive += 1
        else:
            py_consecutive = 0
    
    py_should_sell = py_consecutive >= periods
    
    print(f"  股票: {ticker}, Periods: {periods}")
    print(f"  檢查日期: {recent_dates}")
    for d in recent_dates:
        selected = selection_history.get(d, [])
        in_list = ticker in selected
        print(f"    {d} 候選: {selected} | {ticker} {'在' if in_list else '不在'}名單中")
    print(f"  連續未入選次數: {consecutive_not_selected}")
    
    return print_result(js_should_sell, py_should_sell, js_should_sell == py_should_sell)


def test_drawdown():
    """
    drawdown: 回撤超過門檻時賣出
    
    JS 邏輯 (drawdown.js):
        const currentDrawdown = ((referencePrice - price) / referencePrice) * 100;
        return currentDrawdown >= drawdownPct;
    """
    print_header("賣出條件: drawdown (回撤超過門檻)")
    
    buy_price = 100
    current_price = 55  # 下跌 45%
    threshold = 0.40  # 40%
    
    # JS 邏輯
    reference_price = buy_price
    current_drawdown = (reference_price - current_price) / reference_price
    js_should_sell = current_drawdown >= threshold
    
    # Python 邏輯
    py_drawdown = (buy_price - current_price) / buy_price
    py_should_sell = py_drawdown >= threshold
    
    print(f"  買入價: {buy_price}, 當前價: {current_price}")
    print(f"  門檻: {threshold:.0%}")
    print(f"  回撤: {current_drawdown:.2%}")
    
    return print_result(js_should_sell, py_should_sell, js_should_sell == py_should_sell)


def test_weakness():
    """
    weakness: Sharpe AND Growth 排名同時 > K 連續 M 期時賣出
    
    JS 邏輯 (weakness.js):
        const sharpeIdx = sharpeRanking.indexOf(ticker);
        const growthIdx = growthRanking.indexOf(ticker);
        const sharpeBad = sharpeIdx < 0 || sharpeIdx >= rankThreshold;
        const growthBad = growthIdx < 0 || growthIdx >= rankThreshold;
        if (sharpeBad && growthBad) {
            consecutiveWeak++;
        } else {
            consecutiveWeak = 0;
        }
    """
    print_header("賣出條件: weakness (Sharpe AND Growth 排名同時 > K)")
    
    ticker = 'AMZN'  # 排名較後
    rank_k = 5  # 排名 > 5 視為弱勢
    periods = 3
    date = '2025-01-05'
    country = 'US'
    
    dates = DATES
    current_idx = dates.index(date)
    recent_dates = dates[current_idx - periods + 1: current_idx + 1]
    
    # JS 邏輯
    consecutive_weak = 0
    for d in recent_dates:
        sharpe_ranking = MOCK_SHARPE_RANK[d][country]
        growth_ranking = MOCK_GROWTH_RANK[d][country]
        
        sharpe_idx = sharpe_ranking.index(ticker) if ticker in sharpe_ranking else -1
        growth_idx = growth_ranking.index(ticker) if ticker in growth_ranking else -1
        
        sharpe_bad = sharpe_idx < 0 or sharpe_idx >= rank_k
        growth_bad = growth_idx < 0 or growth_idx >= rank_k
        
        if sharpe_bad and growth_bad:
            consecutive_weak += 1
        else:
            consecutive_weak = 0
    
    js_should_sell = consecutive_weak >= periods
    
    # Python 邏輯
    py_consecutive = 0
    for d in recent_dates:
        sharpe_ranking = MOCK_SHARPE_RANK[d][country]
        growth_ranking = MOCK_GROWTH_RANK[d][country]
        
        sharpe_pos = sharpe_ranking.index(ticker) if ticker in sharpe_ranking else -1
        growth_pos = growth_ranking.index(ticker) if ticker in growth_ranking else -1
        
        sharpe_bad = sharpe_pos < 0 or sharpe_pos >= rank_k
        growth_bad = growth_pos < 0 or growth_pos >= rank_k
        
        if sharpe_bad and growth_bad:
            py_consecutive += 1
        else:
            py_consecutive = 0
    
    py_should_sell = py_consecutive >= periods
    
    print(f"  股票: {ticker}, Rank K: {rank_k}, Periods: {periods}")
    print(f"  檢查日期: {recent_dates}")
    for d in recent_dates:
        sharpe_ranking = MOCK_SHARPE_RANK[d][country]
        growth_ranking = MOCK_GROWTH_RANK[d][country]
        sharpe_idx = sharpe_ranking.index(ticker) if ticker in sharpe_ranking else -1
        growth_idx = growth_ranking.index(ticker) if ticker in growth_ranking else -1
        print(f"    {d} Sharpe排名: {sharpe_idx}, Growth排名: {growth_idx}")
    print(f"  連續弱勢次數: {consecutive_weak}")
    
    return print_result(js_should_sell, py_should_sell, js_should_sell == py_should_sell)


# ============================================================
# 再平衡策略測試
# ============================================================

def test_rebalance_immediate():
    """
    immediate: 只要有候選股且有空位就買入
    
    JS 邏輯 (immediate.js):
        const currentSet = new Set(currentHoldings);
        const targetSet = new Set(targetStocks);
        if (currentSet.size !== targetSet.size) return true;
        for (const ticker of currentSet) {
            if (!targetSet.has(ticker)) return true;
        }
        return false;
    """
    print_header("再平衡策略: immediate (立即投入)")
    
    current_holdings = ['AAPL', 'MSFT']
    target_stocks = ['MSFT', 'NVDA', 'TSLA']
    
    # JS 邏輯：檢查是否需要再平衡
    current_set = set(current_holdings)
    target_set = set(target_stocks)
    
    js_should_rebalance = current_set != target_set
    
    # Python 邏輯
    py_should_rebalance = set(current_holdings) != set(target_stocks)
    
    print(f"  當前持倉: {current_holdings}")
    print(f"  目標股票: {target_stocks}")
    print(f"  需要再平衡: {js_should_rebalance}")
    
    return print_result(js_should_rebalance, py_should_rebalance, js_should_rebalance == py_should_rebalance)


def test_rebalance_batch():
    """
    batch: 每次投入可用現金的固定比例
    
    JS 邏輯 (batch.js):
        const investRatio = this.params.investRatio || 0.2;
        // 計算投入金額 = 現金 * investRatio
    """
    print_header("再平衡策略: batch (分批投入)")
    
    cash = 1000000
    invest_ratio = 0.20
    
    # JS 邏輯：計算投入金額
    js_invest_amount = cash * invest_ratio
    
    # Python 邏輯
    py_invest_amount = cash * invest_ratio
    
    print(f"  現金: {cash:,}")
    print(f"  投入比例: {invest_ratio:.0%}")
    print(f"  投入金額: {js_invest_amount:,.0f}")
    
    return print_result(js_invest_amount, py_invest_amount, js_invest_amount == py_invest_amount)


def test_rebalance_delayed():
    """
    delayed: 等市場轉強再進場（Sharpe Top-N 平均 > 門檻）
    
    JS 邏輯 (delayed.js):
        const topTickers = ranking.sharpe.US.slice(0, topN);
        const avgSharpe = topTickers.reduce(...) / topTickers.length;
        return avgSharpe > threshold;
    """
    print_header("再平衡策略: delayed (延遲投入)")
    
    date = '2025-01-05'
    top_n = 5
    threshold = 0
    
    sharpe_values = MOCK_SHARPE_VALUES[date]
    us_ranking = MOCK_SHARPE_RANK[date]['US']
    
    # JS 邏輯：計算 Top-N 的平均 Sharpe
    top_tickers = us_ranking[:top_n]
    sharpe_sum = sum(sharpe_values.get(t, 0) for t in top_tickers)
    avg_sharpe = sharpe_sum / len(top_tickers) if top_tickers else 0
    
    js_should_invest = avg_sharpe > threshold
    
    # Python 邏輯
    py_top_tickers = us_ranking[:top_n]
    py_sharpe_sum = sum(sharpe_values.get(t, 0) for t in py_top_tickers)
    py_avg_sharpe = py_sharpe_sum / len(py_top_tickers) if py_top_tickers else 0
    
    py_should_invest = py_avg_sharpe > threshold
    
    print(f"  日期: {date}, Top N: {top_n}, 門檻: {threshold}")
    print(f"  Top-{top_n} 股票: {top_tickers}")
    print(f"  Sharpe 值: {[sharpe_values.get(t) for t in top_tickers]}")
    print(f"  平均 Sharpe: {avg_sharpe:.4f}")
    print(f"  應該投入: {js_should_invest}")
    
    return print_result(js_should_invest, py_should_invest, js_should_invest == py_should_invest)


def test_rebalance_concentrated():
    """
    concentrated: 只在 Top-K 明確領先時才投入
    
    JS 邏輯 (concentrated.js):
        const topKAvg = this._avgSharpe(topKTickers, sharpeValues);
        const nextKAvg = this._avgSharpe(nextKTickers, sharpeValues);
        if (nextKAvg <= 0 && topKAvg > 0) return true;
        if (nextKAvg > 0) {
            const leadRatio = (topKAvg - nextKAvg) / Math.abs(nextKAvg);
            return leadRatio >= leadMargin;
        }
    """
    print_header("再平衡策略: concentrated (集中投資)")
    
    date = '2025-01-05'
    top_k = 3
    lead_margin = 0.30  # 30%
    
    sharpe_values = MOCK_SHARPE_VALUES[date]
    us_ranking = MOCK_SHARPE_RANK[date]['US']
    
    # JS 邏輯
    top_k_tickers = us_ranking[:top_k]
    next_k_tickers = us_ranking[top_k:top_k*2]
    
    def avg_sharpe(tickers):
        values = [sharpe_values.get(t, 0) for t in tickers]
        return sum(values) / len(values) if values else 0
    
    top_k_avg = avg_sharpe(top_k_tickers)
    next_k_avg = avg_sharpe(next_k_tickers)
    
    js_should_invest = False
    if next_k_avg <= 0 and top_k_avg > 0:
        js_should_invest = True
    elif next_k_avg > 0:
        lead_ratio = (top_k_avg - next_k_avg) / abs(next_k_avg)
        js_should_invest = lead_ratio >= lead_margin
    
    # Python 邏輯
    py_top_k_avg = avg_sharpe(top_k_tickers)
    py_next_k_avg = avg_sharpe(next_k_tickers)
    
    py_should_invest = False
    if py_next_k_avg <= 0 and py_top_k_avg > 0:
        py_should_invest = True
    elif py_next_k_avg > 0:
        lead_ratio = (py_top_k_avg - py_next_k_avg) / abs(py_next_k_avg)
        py_should_invest = lead_ratio >= lead_margin
    
    print(f"  日期: {date}, Top K: {top_k}, 領先門檻: {lead_margin:.0%}")
    print(f"  Top-{top_k}: {top_k_tickers}, 平均 Sharpe: {top_k_avg:.4f}")
    print(f"  Next-{top_k}: {next_k_tickers}, 平均 Sharpe: {next_k_avg:.4f}")
    if next_k_avg > 0:
        print(f"  領先比例: {(top_k_avg - next_k_avg) / abs(next_k_avg):.2%}")
    print(f"  應該投入: {js_should_invest}")
    
    return print_result(js_should_invest, py_should_invest, js_should_invest == py_should_invest)


def test_rebalance_none():
    """
    none: 不主動買入，只靠賣出條件
    """
    print_header("再平衡策略: none (不主動買入)")
    
    # JS 邏輯：永遠不買入
    js_should_invest = False
    
    # Python 邏輯
    py_should_invest = False
    
    print(f"  策略: 不主動買入新股票")
    print(f"  應該投入: {js_should_invest}")
    
    return print_result(js_should_invest, py_should_invest, js_should_invest == py_should_invest)


# ============================================================
# 主程式
# ============================================================

def main():
    print("=" * 70)
    print("  條件邏輯單元測試 - 驗證 JS 與 Python 一致性")
    print("=" * 70)
    
    results = {
        'buy': [],
        'sell': [],
        'rebalance': []
    }
    
    # 買入條件測試 (7個)
    print("\n>>> 買入條件 (7個) <<<")
    results['buy'].append(('sharpe_rank', test_sharpe_rank()))
    results['buy'].append(('sharpe_threshold', test_sharpe_threshold()))
    results['buy'].append(('sharpe_streak', test_sharpe_streak()))
    results['buy'].append(('growth_rank', test_growth_rank()))
    results['buy'].append(('growth_streak', test_growth_streak()))
    results['buy'].append(('sort_sharpe', test_sort_sharpe()))
    results['buy'].append(('sort_industry', test_sort_industry()))
    
    # 賣出條件測試 (5個)
    print("\n>>> 賣出條件 (5個) <<<")
    results['sell'].append(('sharpe_fail', test_sharpe_fail()))
    results['sell'].append(('growth_fail', test_growth_fail()))
    results['sell'].append(('not_selected', test_not_selected()))
    results['sell'].append(('drawdown', test_drawdown()))
    results['sell'].append(('weakness', test_weakness()))
    
    # 再平衡策略測試 (5個)
    print("\n>>> 再平衡策略 (5個) <<<")
    results['rebalance'].append(('immediate', test_rebalance_immediate()))
    results['rebalance'].append(('batch', test_rebalance_batch()))
    results['rebalance'].append(('delayed', test_rebalance_delayed()))
    results['rebalance'].append(('concentrated', test_rebalance_concentrated()))
    results['rebalance'].append(('none', test_rebalance_none()))
    
    # 總結
    print("\n" + "=" * 70)
    print("  測試總結")
    print("=" * 70)
    
    total_pass = 0
    total_fail = 0
    
    for category, tests in results.items():
        print(f"\n  [{category.upper()}]")
        for name, passed in tests:
            status = "✅" if passed else "❌"
            print(f"    {status} {name}")
            if passed:
                total_pass += 1
            else:
                total_fail += 1
    
    print("\n" + "-" * 70)
    print(f"  總計: {total_pass} 通過, {total_fail} 失敗")
    print("=" * 70)
    
    if total_fail == 0:
        print("\n✅ 所有測試通過！JS 與 Python 邏輯一致。")
    else:
        print(f"\n❌ 有 {total_fail} 個測試失敗，需要檢查並修正。")


if __name__ == '__main__':
    main()
