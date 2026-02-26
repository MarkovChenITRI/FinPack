"""
真實數據邏輯比對測試

用實際快取數據測試前後端邏輯是否一致
"""
import logging
import pandas as pd
from datetime import datetime, timedelta

# 設定日誌等級
logging.basicConfig(level=logging.WARNING)

from core.data import smart_load_or_fetch, filter_by_market
from core.align import align_close_prices
from core.indicator import Indicators

print("="*60)
print("載入真實數據...")
print("="*60)

# 載入數據
raw_data, watchlist, stock_info, _ = smart_load_or_fetch(show_progress=False)
filtered_data, filtered_info = filter_by_market(raw_data, stock_info, market='us')
close_df, _ = align_close_prices(filtered_data)
indicators = Indicators(close_df, filtered_info)

# 觸發指標計算
_ = indicators.sharpe
_ = indicators.growth
_ = indicators.sharpe_rank_by_country
_ = indicators.growth_rank_by_country

print(f"載入完成: {len(close_df.columns)} 檔股票, {len(close_df)} 天")

# 選擇測試日期（最後一個交易日）
test_date = close_df.index[-1].strftime('%Y-%m-%d')
test_idx = len(close_df) - 1

print(f"測試日期: {test_date}")
print(f"股票列表: {list(close_df.columns)[:10]}...")

# =============================================================================
# TEST 1: sharpe_rank
# =============================================================================

def test_sharpe_rank_real():
    """用真實數據測試 sharpe_rank"""
    print("\n" + "="*60)
    print("TEST 1: sharpe_rank (真實數據)")
    print("="*60)
    
    top_n = 15
    input_tickers = list(close_df.columns)
    
    # 取得 sharpe_rank_by_country
    day_rank = indicators.sharpe_rank_by_country.get(test_date, {})
    us_ranking = day_rank.get('US', [])
    
    print(f"\n後端 sharpe_rank_by_country[{test_date}]['US']:")
    print(f"  前 15 名: {us_ranking[:15]}")
    print(f"  總數: {len(us_ranking)}")
    
    # === 模擬前端 JS 邏輯 ===
    selected_tickers_js = set(us_ranking[:top_n])
    js_result = [t for t in input_tickers if t in selected_tickers_js]
    
    print(f"\n[前端 JS 邏輯] 結果 ({len(js_result)} 檔):")
    print(f"  {js_result}")
    
    # === 後端 Python 邏輯 ===
    py_result = []
    for symbol in input_tickers:
        country = filtered_info.get(symbol, {}).get('country', 'US')
        if indicators.check_in_sharpe_top_k(symbol, test_date, country, top_n):
            py_result.append(symbol)
    
    print(f"\n[後端 Python 邏輯] 結果 ({len(py_result)} 檔):")
    print(f"  {py_result}")
    
    # 比較
    if set(js_result) == set(py_result):
        print("\n✅ sharpe_rank 邏輯一致!")
    else:
        print("\n❌ sharpe_rank 邏輯不一致!")
        print(f"  JS 有但 Python 沒有: {set(js_result) - set(py_result)}")
        print(f"  Python 有但 JS 沒有: {set(py_result) - set(js_result)}")
    
    return js_result


# =============================================================================
# TEST 2: growth_streak
# =============================================================================

def test_growth_streak_real(input_tickers):
    """用真實數據測試 growth_streak"""
    print("\n" + "="*60)
    print("TEST 2: growth_streak (真實數據)")
    print("="*60)
    
    days = 3
    percentile = 50
    
    print(f"參數: days={days}, percentile={percentile}%")
    print(f"輸入: {input_tickers}")
    
    # 取得日期列表
    all_dates = indicators.get_dates()
    current_idx = all_dates.index(test_date) if test_date in all_dates else -1
    
    if current_idx < days - 1:
        print(f"⚠️ 日期不足以測試 {days} 天連續")
        return input_tickers
    
    recent_dates = all_dates[current_idx - days + 1:current_idx + 1]
    print(f"recent_dates: {recent_dates}")
    
    # === 模擬前端 JS 邏輯 ===
    consistent_js = set(input_tickers)
    
    for d in recent_dates:
        day_rank = indicators.growth_rank_by_country.get(d, {})
        us_ranking = day_rank.get('US', [])
        top_n = max(1, int(len(us_ranking) * percentile / 100))
        top_set = set(us_ranking[:top_n])
        
        print(f"  {d}: total={len(us_ranking)}, top {percentile}%={top_n} 檔")
        
        to_remove = [t for t in consistent_js if t not in top_set]
        for t in to_remove:
            consistent_js.discard(t)
    
    js_result = [t for t in input_tickers if t in consistent_js]
    
    print(f"\n[前端 JS 邏輯] 結果 ({len(js_result)} 檔):")
    print(f"  {js_result}")
    
    # === 後端 Python 邏輯 ===
    py_result = []
    for symbol in input_tickers:
        if indicators.check_growth_streak(symbol, test_idx, days, percentile):
            py_result.append(symbol)
    
    print(f"\n[後端 Python 邏輯] 結果 ({len(py_result)} 檔):")
    print(f"  {py_result}")
    
    # 比較
    if set(js_result) == set(py_result):
        print("\n✅ growth_streak 邏輯一致!")
    else:
        print("\n❌ growth_streak 邏輯不一致!")
        print(f"  JS 有但 Python 沒有: {set(js_result) - set(py_result)}")
        print(f"  Python 有但 JS 沒有: {set(py_result) - set(js_result)}")
        
        # 詳細比較差異原因
        for symbol in (set(js_result) ^ set(py_result)):
            print(f"\n  分析 {symbol}:")
            country = filtered_info.get(symbol, {}).get('country', 'US')
            for d in recent_dates:
                day_rank = indicators.growth_rank_by_country.get(d, {})
                ranking = day_rank.get(country, [])
                top_n = max(1, int(len(ranking) * percentile / 100))
                in_top = symbol in ranking[:top_n]
                pos = ranking.index(symbol) + 1 if symbol in ranking else -1
                print(f"    {d}: 排名 {pos}/{len(ranking)}, top_n={top_n}, 在前{percentile}%: {in_top}")
    
    return js_result


# =============================================================================
# TEST 3: sort_industry
# =============================================================================

def test_sort_industry_real(input_tickers):
    """用真實數據測試 sort_industry"""
    print("\n" + "="*60)
    print("TEST 3: sort_industry (真實數據)")
    print("="*60)
    
    per_industry = 2
    
    print(f"參數: per_industry={per_industry}")
    print(f"輸入 ({len(input_tickers)} 檔): {input_tickers}")
    
    if not input_tickers:
        print("⚠️ 無輸入候選")
        return []
    
    # 取得 sharpe 值
    sharpe_values = {}
    for t in input_tickers:
        sharpe_values[t] = indicators.get_sharpe(t, test_idx)
    
    print(f"\nSharpe 值:")
    for t in input_tickers:
        ind = filtered_info.get(t, {}).get('industry', 'Unknown')
        print(f"  {t}: sharpe={sharpe_values[t]:.4f}, industry={ind}")
    
    # === 模擬前端 JS 邏輯 ===
    industry_groups = {}
    for t in input_tickers:
        ind = filtered_info.get(t, {}).get('industry', 'Unknown')
        if ind not in industry_groups:
            industry_groups[ind] = []
        industry_groups[ind].append({
            'ticker': t,
            'sharpe': sharpe_values[t] if sharpe_values[t] is not None else 0
        })
    
    # 每個產業按 Sharpe 排序
    for ind in industry_groups:
        industry_groups[ind].sort(key=lambda x: x['sharpe'], reverse=True)
    
    # 按產業內最高 Sharpe 排序產業
    industries = sorted(
        industry_groups.keys(),
        key=lambda i: industry_groups[i][0]['sharpe'] if industry_groups[i] else 0,
        reverse=True
    )
    
    print(f"\n產業順序 (按最高 Sharpe):")
    for ind in industries:
        stocks = [f"{s['ticker']}({s['sharpe']:.2f})" for s in industry_groups[ind]]
        print(f"  {ind}: {stocks}")
    
    # Round-Robin 選取
    selected_js = []
    count = {}
    has_more = True
    max_rounds = per_industry * len(industries) + 1
    round_num = 0
    
    while has_more and round_num < max_rounds:
        has_more = False
        for ind in industries:
            c = count.get(ind, 0)
            if c >= per_industry:
                continue
            if c < len(industry_groups[ind]):
                selected_js.append(industry_groups[ind][c]['ticker'])
                count[ind] = c + 1
                has_more = True
        round_num += 1
    
    print(f"\n[前端 JS 邏輯] 選取順序: {selected_js}")
    
    # === 後端 Python 邏輯 (模擬 engine.py _select_stocks 的 sort_industry 部分) ===
    candidates = []
    for symbol in input_tickers:
        candidates.append({
            'symbol': symbol,
            'sharpe': sharpe_values[symbol],
            'industry': filtered_info.get(symbol, {}).get('industry', 'Unknown')
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
    
    # Round-Robin 選取
    selected_py = []
    count_py = {}
    has_more = True
    round_num = 0
    
    while has_more and round_num < max_rounds:
        has_more = False
        for ind in industries_py:
            c = count_py.get(ind, 0)
            if c >= per_industry:
                continue
            if c < len(industry_groups_py[ind]):
                selected_py.append(industry_groups_py[ind][c]['symbol'])
                count_py[ind] = c + 1
                has_more = True
        round_num += 1
    
    print(f"[後端 Python 邏輯] 選取順序: {selected_py}")
    
    # 比較
    if selected_js == selected_py:
        print("\n✅ sort_industry 邏輯一致! (順序也相同)")
    elif set(selected_js) == set(selected_py):
        print("\n⚠️ sort_industry 結果相同但順序不同!")
    else:
        print("\n❌ sort_industry 邏輯不一致!")
        print(f"  JS 有但 Python 沒有: {set(selected_js) - set(selected_py)}")
        print(f"  Python 有但 JS 沒有: {set(selected_py) - set(selected_js)}")
    
    return selected_js


# =============================================================================
# 主程式
# =============================================================================

if __name__ == '__main__':
    # Step 1: sharpe_rank
    step1_result = test_sharpe_rank_real()
    
    # Step 2: growth_streak (用 Step 1 的結果)
    step2_result = test_growth_streak_real(step1_result)
    
    # Step 3: sort_industry (用 Step 2 的結果)
    step3_result = test_sort_industry_real(step2_result)
    
    print("\n" + "="*60)
    print("最終結果")
    print("="*60)
    print(f"候選股票: {step3_result}")
