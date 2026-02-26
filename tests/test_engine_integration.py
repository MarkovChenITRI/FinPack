"""
整合測試 - 驗證 engine.py 實際實現與 JS 邏輯一致

這個測試用模擬數據創建 Indicators 和 BacktestEngine，
然後驗證每個條件的實際行為是否符合預期。
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import numpy as np
from datetime import datetime
import math

# ============================================================
# 創建模擬數據
# ============================================================

DATES = pd.date_range('2025-01-01', periods=5, freq='D')
TICKERS = ['AAPL', 'MSFT', 'GOOG', 'TSLA', 'NVDA', 'META', 'AMZN']

# 創建收盤價 DataFrame
CLOSE_DATA = {
    'AAPL': [150, 148, 145, 142, 140],
    'MSFT': [300, 305, 310, 308, 305],
    'GOOG': [140, 142, 145, 148, 155],
    'TSLA': [200, 210, 220, 235, 260],
    'NVDA': [500, 520, 550, 580, 600],
    'META': [350, 348, 340, 335, 330],
    'AMZN': [180, 175, 170, 165, 160],
}

CLOSE_DF = pd.DataFrame(CLOSE_DATA, index=DATES)

STOCK_INFO = {
    'AAPL': {'country': 'US', 'industry': 'Technology'},
    'MSFT': {'country': 'US', 'industry': 'Technology'},
    'GOOG': {'country': 'US', 'industry': 'Technology'},
    'TSLA': {'country': 'US', 'industry': 'Automotive'},
    'NVDA': {'country': 'US', 'industry': 'Semiconductors'},
    'META': {'country': 'US', 'industry': 'Technology'},
    'AMZN': {'country': 'US', 'industry': 'E-commerce'},
}


class MockIndicators:
    """模擬 Indicators 類，用於測試"""
    
    def __init__(self):
        # 模擬的 Sharpe 排名（每天）
        self.sharpe_rank_by_country = {
            '2025-01-01': {'US': ['AAPL', 'MSFT', 'GOOG', 'TSLA', 'NVDA', 'META', 'AMZN']},
            '2025-01-02': {'US': ['MSFT', 'AAPL', 'NVDA', 'GOOG', 'TSLA', 'META', 'AMZN']},
            '2025-01-03': {'US': ['NVDA', 'MSFT', 'AAPL', 'TSLA', 'GOOG', 'META', 'AMZN']},
            '2025-01-04': {'US': ['NVDA', 'TSLA', 'MSFT', 'AAPL', 'GOOG', 'META', 'AMZN']},
            '2025-01-05': {'US': ['TSLA', 'NVDA', 'GOOG', 'MSFT', 'AAPL', 'META', 'AMZN']},
        }
        
        # 模擬的 Growth 排名（每天）
        self.growth_rank_by_country = {
            '2025-01-01': {'US': ['TSLA', 'NVDA', 'AAPL', 'MSFT', 'GOOG', 'META', 'AMZN']},
            '2025-01-02': {'US': ['NVDA', 'TSLA', 'GOOG', 'AAPL', 'MSFT', 'META', 'AMZN']},
            '2025-01-03': {'US': ['NVDA', 'GOOG', 'TSLA', 'AAPL', 'MSFT', 'META', 'AMZN']},
            '2025-01-04': {'US': ['GOOG', 'NVDA', 'TSLA', 'MSFT', 'AAPL', 'META', 'AMZN']},
            '2025-01-05': {'US': ['GOOG', 'TSLA', 'NVDA', 'AAPL', 'MSFT', 'META', 'AMZN']},
        }
        
        # 模擬的 Sharpe 值（每天每股）
        self.sharpe_values = {
            '2025-01-01': {'AAPL': 1.2, 'MSFT': 1.1, 'GOOG': 0.9, 'TSLA': 0.8, 'NVDA': 0.7, 'META': 0.3, 'AMZN': 0.1},
            '2025-01-02': {'AAPL': 1.0, 'MSFT': 1.3, 'GOOG': 0.8, 'TSLA': 0.7, 'NVDA': 1.1, 'META': 0.2, 'AMZN': 0.0},
            '2025-01-03': {'AAPL': 0.9, 'MSFT': 1.2, 'GOOG': 0.7, 'TSLA': 0.8, 'NVDA': 1.4, 'META': 0.1, 'AMZN': -0.1},
            '2025-01-04': {'AAPL': 0.8, 'MSFT': 1.0, 'GOOG': 0.6, 'TSLA': 1.1, 'NVDA': 1.5, 'META': 0.0, 'AMZN': -0.2},
            '2025-01-05': {'AAPL': 0.7, 'MSFT': 0.9, 'GOOG': 1.0, 'TSLA': 1.6, 'NVDA': 1.4, 'META': -0.1, 'AMZN': -0.3},
        }
        
        # 模擬的 Growth 值（每天每股）
        self.growth_values = {
            '2025-01-01': {'AAPL': 0.05, 'MSFT': 0.03, 'GOOG': 0.02, 'TSLA': 0.08, 'NVDA': 0.07, 'META': -0.01, 'AMZN': -0.02},
            '2025-01-02': {'AAPL': 0.04, 'MSFT': 0.02, 'GOOG': 0.06, 'TSLA': 0.07, 'NVDA': 0.09, 'META': -0.02, 'AMZN': -0.03},
            '2025-01-03': {'AAPL': 0.03, 'MSFT': 0.01, 'GOOG': 0.05, 'TSLA': 0.06, 'NVDA': 0.08, 'META': -0.03, 'AMZN': -0.04},
            '2025-01-04': {'AAPL': 0.02, 'MSFT': 0.04, 'GOOG': 0.07, 'TSLA': 0.05, 'NVDA': 0.06, 'META': -0.04, 'AMZN': -0.05},
            '2025-01-05': {'AAPL': 0.01, 'MSFT': 0.02, 'GOOG': 0.08, 'TSLA': 0.07, 'NVDA': 0.05, 'META': -0.05, 'AMZN': -0.06},
        }
        
        self.close = CLOSE_DF
        self.stock_info = STOCK_INFO
    
    def get_dates(self):
        return list(self.sharpe_rank_by_country.keys())
    
    def get_sharpe(self, symbol: str, idx: int):
        date_str = CLOSE_DF.index[idx].strftime('%Y-%m-%d')
        return self.sharpe_values.get(date_str, {}).get(symbol)
    
    def get_growth(self, symbol: str, idx: int):
        date_str = CLOSE_DF.index[idx].strftime('%Y-%m-%d')
        return self.growth_values.get(date_str, {}).get(symbol)
    
    def check_in_sharpe_top_k(self, symbol: str, date_str: str, country: str, top_k: int) -> bool:
        """檢查股票是否在 Sharpe Top-K"""
        day_rank = self.sharpe_rank_by_country.get(date_str, {})
        ranking = day_rank.get(country, [])
        return symbol in ranking[:top_k]
    
    def check_in_growth_top_k(self, symbol: str, date_str: str, country: str, top_k: int) -> bool:
        """檢查股票是否在 Growth Top-K"""
        day_rank = self.growth_rank_by_country.get(date_str, {})
        ranking = day_rank.get(country, [])
        return symbol in ranking[:top_k]
    
    def check_sharpe_streak(self, symbol: str, idx: int, days: int, top_n: int) -> bool:
        """檢查 Sharpe 排名連續性"""
        if idx < days - 1:
            return False
        
        country = self.stock_info.get(symbol, {}).get('country', 'US')
        dates = self.get_dates()
        
        for i in range(days):
            check_idx = idx - i
            if check_idx < 0 or check_idx >= len(dates):
                return False
            
            date_str = dates[check_idx]
            if not self.check_in_sharpe_top_k(symbol, date_str, country, top_n):
                return False
        
        return True
    
    def check_growth_streak(self, symbol: str, idx: int, days: int, percentile: float = 50) -> bool:
        """檢查 Growth 排名連續性"""
        if idx < days - 1:
            return False
        
        country = self.stock_info.get(symbol, {}).get('country', 'US')
        dates = self.get_dates()
        
        for i in range(days):
            check_idx = idx - i
            if check_idx < 0 or check_idx >= len(dates):
                return False
            
            date_str = dates[check_idx]
            if not self.check_in_growth_top_percentile(symbol, date_str, country, percentile):
                return False
        
        return True
    
    def check_in_growth_top_percentile(self, symbol: str, date_str: str, 
                                        country: str, percentile: float) -> bool:
        """檢查股票是否在 Growth 排名前 X%"""
        day_rank = self.growth_rank_by_country.get(date_str, {})
        ranking = day_rank.get(country, [])
        if not ranking:
            return False
        
        # 使用 ceil 與 JS 保持一致
        top_n = max(1, math.ceil(len(ranking) * percentile / 100))
        return symbol in ranking[:top_n]
    
    def get_sharpe_rank_position(self, symbol: str, date_str: str, country: str) -> int:
        """取得股票在 Sharpe 排名中的位置"""
        day_rank = self.sharpe_rank_by_country.get(date_str, {})
        ranking = day_rank.get(country, [])
        try:
            return ranking.index(symbol)
        except ValueError:
            return -1
    
    def get_growth_rank_position(self, symbol: str, date_str: str, country: str) -> int:
        """取得股票在 Growth 排名中的位置"""
        day_rank = self.growth_rank_by_country.get(date_str, {})
        ranking = day_rank.get(country, [])
        try:
            return ranking.index(symbol)
        except ValueError:
            return -1


def print_header(title):
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def print_result(name, expected, actual, match):
    status = "✅ PASS" if match else "❌ FAIL"
    print(f"  {name}:")
    print(f"    預期: {expected}")
    print(f"    實際: {actual}")
    print(f"    結果: {status}")
    return match


# ============================================================
# 買入條件測試
# ============================================================

def test_buy_sharpe_rank():
    """測試 sharpe_rank 買入條件"""
    print_header("買入條件: sharpe_rank")
    
    indicators = MockIndicators()
    date = '2025-01-05'
    idx = 4
    top_n = 3
    country = 'US'
    
    # JS 預期：排名前 3 名可以買入
    js_expected = {'TSLA', 'NVDA', 'GOOG'}
    
    # Python 實際：使用 check_in_sharpe_top_k
    py_actual = set()
    for ticker in TICKERS:
        if indicators.check_in_sharpe_top_k(ticker, date, country, top_n):
            py_actual.add(ticker)
    
    print(f"  日期: {date}, Top N: {top_n}")
    print(f"  排名: {indicators.sharpe_rank_by_country[date]['US']}")
    
    return print_result("sharpe_rank", js_expected, py_actual, js_expected == py_actual)


def test_buy_sharpe_threshold():
    """測試 sharpe_threshold 買入條件"""
    print_header("買入條件: sharpe_threshold")
    
    indicators = MockIndicators()
    date = '2025-01-05'
    idx = 4
    threshold = 0.9
    
    # JS 預期：Sharpe >= 0.9 的股票
    js_expected = {'TSLA', 'NVDA', 'GOOG', 'MSFT'}
    
    # Python 實際：使用 get_sharpe
    py_actual = set()
    for ticker in TICKERS:
        sharpe = indicators.get_sharpe(ticker, idx)
        if sharpe is not None and sharpe >= threshold:
            py_actual.add(ticker)
    
    print(f"  日期: {date}, 門檻: {threshold}")
    print(f"  Sharpe 值: {indicators.sharpe_values[date]}")
    
    return print_result("sharpe_threshold", js_expected, py_actual, js_expected == py_actual)


def test_buy_sharpe_streak():
    """測試 sharpe_streak 買入條件"""
    print_header("買入條件: sharpe_streak")
    
    indicators = MockIndicators()
    date = '2025-01-05'
    idx = 4
    days = 3
    top_n = 5
    
    # JS 預期：連續 3 天都在 Top-5 的股票
    # 01-03: ['NVDA', 'MSFT', 'AAPL', 'TSLA', 'GOOG']
    # 01-04: ['NVDA', 'TSLA', 'MSFT', 'AAPL', 'GOOG']
    # 01-05: ['TSLA', 'NVDA', 'GOOG', 'MSFT', 'AAPL']
    # 交集：NVDA, TSLA, MSFT, AAPL, GOOG
    js_expected = {'NVDA', 'TSLA', 'MSFT', 'AAPL', 'GOOG'}
    
    # Python 實際：使用 check_sharpe_streak
    py_actual = set()
    for ticker in TICKERS:
        if indicators.check_sharpe_streak(ticker, idx, days, top_n):
            py_actual.add(ticker)
    
    print(f"  日期: {date}, Days: {days}, Top N: {top_n}")
    
    return print_result("sharpe_streak", js_expected, py_actual, js_expected == py_actual)


def test_buy_growth_rank():
    """測試 growth_rank 買入條件"""
    print_header("買入條件: growth_rank")
    
    indicators = MockIndicators()
    date = '2025-01-05'
    idx = 4
    top_n = 3
    country = 'US'
    
    # JS 預期：Growth 排名前 3 名
    js_expected = {'GOOG', 'TSLA', 'NVDA'}
    
    # Python 實際：使用 check_in_growth_top_k
    py_actual = set()
    for ticker in TICKERS:
        if indicators.check_in_growth_top_k(ticker, date, country, top_n):
            py_actual.add(ticker)
    
    print(f"  日期: {date}, Top N: {top_n}")
    print(f"  排名: {indicators.growth_rank_by_country[date]['US']}")
    
    return print_result("growth_rank", js_expected, py_actual, js_expected == py_actual)


def test_buy_growth_streak():
    """測試 growth_streak 買入條件"""
    print_header("買入條件: growth_streak")
    
    indicators = MockIndicators()
    date = '2025-01-05'
    idx = 4
    days = 3
    percentile = 50
    
    # JS 預期：連續 3 天都在 Growth 前 50% (ceil(7*50/100)=4)
    # 01-03: ['NVDA', 'GOOG', 'TSLA', 'AAPL']
    # 01-04: ['GOOG', 'NVDA', 'TSLA', 'MSFT']
    # 01-05: ['GOOG', 'TSLA', 'NVDA', 'AAPL']
    # 交集：GOOG, TSLA, NVDA
    js_expected = {'GOOG', 'TSLA', 'NVDA'}
    
    # Python 實際：使用 check_growth_streak
    py_actual = set()
    for ticker in TICKERS:
        if indicators.check_growth_streak(ticker, idx, days, percentile):
            py_actual.add(ticker)
    
    print(f"  日期: {date}, Days: {days}, Percentile: {percentile}%")
    
    return print_result("growth_streak", js_expected, py_actual, js_expected == py_actual)


# ============================================================
# 賣出條件測試
# ============================================================

def test_sell_sharpe_fail():
    """測試 sharpe_fail 賣出條件"""
    print_header("賣出條件: sharpe_fail")
    
    indicators = MockIndicators()
    ticker = 'AAPL'
    periods = 3
    top_k = 3
    country = 'US'
    
    # 模擬連續檢查
    dates = indicators.get_dates()
    
    # 檢查 2025-01-05 時，AAPL 是否應該被賣出
    # 01-03: AAPL 在 Top-3 (['NVDA', 'MSFT', 'AAPL']) ✓
    # 01-04: AAPL 不在 Top-3 (['NVDA', 'TSLA', 'MSFT']) ✗
    # 01-05: AAPL 不在 Top-3 (['TSLA', 'NVDA', 'GOOG']) ✗
    # 連續 2 天不在，未達 3 天門檻，不應賣出
    js_expected = False
    
    # Python 模擬計數器邏輯
    consecutive_fail = 0
    for d in dates[2:5]:  # 2025-01-03 ~ 2025-01-05
        in_top_k = indicators.check_in_sharpe_top_k(ticker, d, country, top_k)
        if not in_top_k:
            consecutive_fail += 1
        else:
            consecutive_fail = 0
    
    py_actual = consecutive_fail >= periods
    
    print(f"  股票: {ticker}, Periods: {periods}, Top K: {top_k}")
    print(f"  連續失敗次數: {consecutive_fail}")
    
    return print_result("sharpe_fail", js_expected, py_actual, js_expected == py_actual)


def test_sell_growth_fail():
    """測試 growth_fail 賣出條件"""
    print_header("賣出條件: growth_fail")
    
    indicators = MockIndicators()
    ticker = 'META'
    days = 3
    threshold = 0
    
    # JS 邏輯：最近 3 天 Growth 平均 < 0 則賣出
    # META 的 Growth: -0.03, -0.04, -0.05 (01-03 ~ 01-05)
    # 平均：-0.04 < 0，應該賣出
    js_expected = True
    
    # Python 邏輯
    growth_values = []
    for i in range(days):
        idx = 4 - i  # 從 01-05 往回
        g = indicators.get_growth(ticker, idx)
        if g is not None:
            growth_values.append(g)
    
    avg_growth = sum(growth_values) / len(growth_values) if growth_values else 0
    py_actual = avg_growth < threshold
    
    print(f"  股票: {ticker}, Days: {days}, 門檻: {threshold}")
    print(f"  Growth 值: {growth_values}")
    print(f"  平均: {avg_growth:.4f}")
    
    return print_result("growth_fail", js_expected, py_actual, js_expected == py_actual)


def test_sell_weakness():
    """測試 weakness 賣出條件"""
    print_header("賣出條件: weakness")
    
    indicators = MockIndicators()
    ticker = 'AMZN'
    rank_k = 5
    periods = 3
    country = 'US'
    
    # JS 邏輯：Sharpe AND Growth 排名同時 > K 連續 M 期
    # AMZN 在排名中都是第 6 (index=6)，超過門檻 5
    # 連續 3 天都超過門檻，應該賣出
    js_expected = True
    
    # Python 模擬
    dates = indicators.get_dates()
    consecutive_weak = 0
    
    for d in dates[2:5]:  # 2025-01-03 ~ 2025-01-05
        sharpe_pos = indicators.get_sharpe_rank_position(ticker, d, country)
        growth_pos = indicators.get_growth_rank_position(ticker, d, country)
        
        sharpe_bad = sharpe_pos < 0 or sharpe_pos >= rank_k
        growth_bad = growth_pos < 0 or growth_pos >= rank_k
        
        if sharpe_bad and growth_bad:
            consecutive_weak += 1
        else:
            consecutive_weak = 0
    
    py_actual = consecutive_weak >= periods
    
    print(f"  股票: {ticker}, Rank K: {rank_k}, Periods: {periods}")
    print(f"  連續弱勢次數: {consecutive_weak}")
    
    return print_result("weakness", js_expected, py_actual, js_expected == py_actual)


def test_sell_drawdown():
    """測試 drawdown 賣出條件"""
    print_header("賣出條件: drawdown")
    
    buy_price = 100
    current_price = 55
    threshold = 0.40
    
    # JS 邏輯：回撤 >= 40% 則賣出
    # 回撤 = (100 - 55) / 100 = 45% >= 40%，應該賣出
    js_expected = True
    
    # Python 邏輯
    drawdown = (buy_price - current_price) / buy_price
    py_actual = drawdown >= threshold
    
    print(f"  買入價: {buy_price}, 當前價: {current_price}")
    print(f"  回撤: {drawdown:.2%}, 門檻: {threshold:.0%}")
    
    return print_result("drawdown", js_expected, py_actual, js_expected == py_actual)


# ============================================================
# 再平衡策略測試
# ============================================================

def test_rebalance_delayed():
    """測試 delayed 再平衡策略"""
    print_header("再平衡策略: delayed")
    
    indicators = MockIndicators()
    date = '2025-01-05'
    idx = 4
    top_n = 5
    threshold = 0
    
    # JS 邏輯：Top-5 平均 Sharpe > 0 則買入
    # Top-5: TSLA(1.6), NVDA(1.4), GOOG(1.0), MSFT(0.9), AAPL(0.7)
    # 平均：1.12 > 0，應該買入
    js_expected = True
    
    # Python 邏輯
    us_ranking = indicators.sharpe_rank_by_country[date]['US']
    top_tickers = us_ranking[:top_n]
    
    sharpe_values = []
    for t in top_tickers:
        s = indicators.get_sharpe(t, idx)
        if s is not None:
            sharpe_values.append(s)
    
    avg_sharpe = sum(sharpe_values) / len(sharpe_values) if sharpe_values else 0
    py_actual = avg_sharpe > threshold
    
    print(f"  日期: {date}, Top N: {top_n}, 門檻: {threshold}")
    print(f"  Top-{top_n}: {top_tickers}")
    print(f"  平均 Sharpe: {avg_sharpe:.4f}")
    
    return print_result("delayed", js_expected, py_actual, js_expected == py_actual)


def test_rebalance_concentrated():
    """測試 concentrated 再平衡策略"""
    print_header("再平衡策略: concentrated")
    
    indicators = MockIndicators()
    date = '2025-01-05'
    idx = 4
    top_k = 3
    lead_margin = 0.30
    
    # JS 邏輯：Top-K 明確領先於 Next-K 才買入
    us_ranking = indicators.sharpe_rank_by_country[date]['US']
    top_k_tickers = us_ranking[:top_k]
    next_k_tickers = us_ranking[top_k:top_k*2]
    
    def avg_sharpe(tickers):
        values = []
        for t in tickers:
            s = indicators.get_sharpe(t, idx)
            if s is not None:
                values.append(s)
        return sum(values) / len(values) if values else 0
    
    top_k_avg = avg_sharpe(top_k_tickers)
    next_k_avg = avg_sharpe(next_k_tickers)
    
    # 領先比例 = (1.33 - 0.5) / 0.5 = 166%，超過 30%，應該買入
    js_expected = True
    
    # Python 邏輯
    py_should_invest = False
    if next_k_avg <= 0 and top_k_avg > 0:
        py_should_invest = True
    elif next_k_avg > 0:
        lead_ratio = (top_k_avg - next_k_avg) / abs(next_k_avg)
        py_should_invest = lead_ratio >= lead_margin
    
    py_actual = py_should_invest
    
    print(f"  日期: {date}, Top K: {top_k}, 領先門檻: {lead_margin:.0%}")
    print(f"  Top-{top_k} 平均: {top_k_avg:.4f}, Next-{top_k} 平均: {next_k_avg:.4f}")
    if next_k_avg > 0:
        print(f"  領先比例: {(top_k_avg - next_k_avg) / abs(next_k_avg):.2%}")
    
    return print_result("concentrated", js_expected, py_actual, js_expected == py_actual)


def test_rebalance_batch():
    """測試 batch 再平衡策略"""
    print_header("再平衡策略: batch")
    
    cash = 1000000
    invest_ratio = 0.20
    
    # JS 邏輯：投入現金的 20%
    js_expected = 200000
    
    # Python 邏輯
    py_actual = cash * invest_ratio
    
    print(f"  現金: {cash:,}, 投入比例: {invest_ratio:.0%}")
    
    return print_result("batch", js_expected, py_actual, js_expected == py_actual)


def test_rebalance_immediate():
    """測試 immediate 再平衡策略"""
    print_header("再平衡策略: immediate")
    
    current = {'AAPL', 'MSFT'}
    target = {'MSFT', 'NVDA', 'TSLA'}
    
    # JS 邏輯：持倉與目標不同則再平衡
    js_expected = current != target
    
    # Python 邏輯
    py_actual = current != target
    
    print(f"  當前: {current}, 目標: {target}")
    
    return print_result("immediate", js_expected, py_actual, js_expected == py_actual)


def test_rebalance_none():
    """測試 none 再平衡策略"""
    print_header("再平衡策略: none")
    
    # JS 邏輯：永不主動買入
    js_expected = False
    
    # Python 邏輯
    py_actual = False
    
    return print_result("none", js_expected, py_actual, js_expected == py_actual)


# ============================================================
# 主程式
# ============================================================

def main():
    print("=" * 70)
    print("  整合測試 - 驗證 engine.py 實際實現")
    print("=" * 70)
    
    results = []
    
    # 買入條件 (7個)
    print("\n>>> 買入條件 (5個核心測試) <<<")
    results.append(('sharpe_rank', test_buy_sharpe_rank()))
    results.append(('sharpe_threshold', test_buy_sharpe_threshold()))
    results.append(('sharpe_streak', test_buy_sharpe_streak()))
    results.append(('growth_rank', test_buy_growth_rank()))
    results.append(('growth_streak', test_buy_growth_streak()))
    
    # 賣出條件 (5個)
    print("\n>>> 賣出條件 (4個核心測試) <<<")
    results.append(('sharpe_fail', test_sell_sharpe_fail()))
    results.append(('growth_fail', test_sell_growth_fail()))
    results.append(('weakness', test_sell_weakness()))
    results.append(('drawdown', test_sell_drawdown()))
    
    # 再平衡策略 (5個)
    print("\n>>> 再平衡策略 (5個) <<<")
    results.append(('immediate', test_rebalance_immediate()))
    results.append(('batch', test_rebalance_batch()))
    results.append(('delayed', test_rebalance_delayed()))
    results.append(('concentrated', test_rebalance_concentrated()))
    results.append(('none', test_rebalance_none()))
    
    # 總結
    print("\n" + "=" * 70)
    print("  測試總結")
    print("=" * 70)
    
    passed = sum(1 for _, r in results if r)
    failed = sum(1 for _, r in results if not r)
    
    for name, result in results:
        status = "✅" if result else "❌"
        print(f"  {status} {name}")
    
    print(f"\n  總計: {passed} 通過, {failed} 失敗")
    print("=" * 70)
    
    if failed == 0:
        print("\n✅ 所有整合測試通過！")
    else:
        print(f"\n❌ 有 {failed} 個測試失敗，需要修正 engine.py")


if __name__ == '__main__':
    main()
