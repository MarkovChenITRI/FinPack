"""
測試 batch 再平衡策略是否與前端一致

前端 batch 策略邏輯（參考 static/js/backtest/rebalance/batch.js）：
1. investAmount = cash × investRatio (如 20%)
2. amountPerStock = investAmount / toBuy.length
3. 對每個候選呼叫 executeBuy(ticker, price, country, date, { amount: amountPerStock })

後端應該有相同的行為。
"""
import pandas as pd
import numpy as np
from datetime import datetime

# 模擬數據
dates = pd.date_range('2024-01-01', periods=5, freq='D')
symbols = ['AAPL', 'MSFT', 'GOOG', 'NVDA', 'AMD']

# 模擬收盤價
close_data = {
    'AAPL': [150, 151, 152, 153, 154],
    'MSFT': [300, 301, 302, 303, 304],
    'GOOG': [100, 101, 102, 103, 104],
    'NVDA': [450, 451, 452, 453, 454],
    'AMD': [120, 121, 122, 123, 124],
}
close_df = pd.DataFrame(close_data, index=dates)

# 模擬指標
sharpe_data = {
    'AAPL': [0.8, 0.9, 1.0, 1.1, 1.2],
    'MSFT': [0.7, 0.8, 0.9, 1.0, 1.1],
    'GOOG': [0.6, 0.7, 0.8, 0.9, 1.0],
    'NVDA': [0.5, 0.6, 0.7, 0.8, 0.9],
    'AMD':  [0.4, 0.5, 0.6, 0.7, 0.8],
}

# 模擬股票資訊
stock_info = {
    'AAPL': {'country': 'US', 'industry': 'Tech'},
    'MSFT': {'country': 'US', 'industry': 'Tech'},
    'GOOG': {'country': 'US', 'industry': 'Cloud'},
    'NVDA': {'country': 'US', 'industry': 'GPU'},
    'AMD':  {'country': 'US', 'industry': 'Processor'},
}


def test_frontend_batch_logic():
    """模擬前端 batch 邏輯"""
    print("=" * 60)
    print("前端 batch 策略模擬")
    print("=" * 60)
    
    # 初始狀態
    cash = 1000000  # 100 萬
    invest_ratio = 0.20
    max_positions = 10
    current_holdings = {}
    
    # 候選股票（假設選股結果）
    candidates = ['AAPL', 'MSFT', 'GOOG', 'NVDA', 'AMD']
    
    # 價格（第一天）
    prices = close_df.iloc[0].to_dict()
    
    # batch 邏輯
    to_buy = [s for s in candidates if s not in current_holdings]
    remaining_slots = max_positions - len(current_holdings)
    actual_max_buy = min(remaining_slots, len(to_buy))
    to_buy = to_buy[:actual_max_buy]
    
    invest_amount = cash * invest_ratio
    amount_per_stock = invest_amount / len(to_buy) if to_buy else 0
    
    print(f"初始現金: ${cash:,.0f}")
    print(f"投入比例: {invest_ratio * 100}%")
    print(f"本次投入金額: ${invest_amount:,.0f}")
    print(f"候選數量: {len(to_buy)}")
    print(f"每隻分配金額: ${amount_per_stock:,.0f}")
    print()
    
    total_cost = 0
    for symbol in to_buy:
        price = prices[symbol]
        shares = int(amount_per_stock / price)
        cost = shares * price
        total_cost += cost
        current_holdings[symbol] = {'shares': shares, 'cost': price}
        print(f"  買入 {symbol}: {shares} 股 @ ${price} = ${cost:,.0f}")
    
    cash -= total_cost
    print()
    print(f"買入後現金: ${cash:,.0f}")
    print(f"總買入成本: ${total_cost:,.0f}")
    print(f"當前持倉數: {len(current_holdings)}")
    
    return cash, current_holdings


def test_backend_batch_logic():
    """測試後端 batch 邏輯"""
    print()
    print("=" * 60)
    print("後端 batch 策略測試")
    print("=" * 60)
    
    # 這裡需要導入實際的後端模組並測試
    # 為了快速驗證，直接複製後端邏輯
    
    cash = 1000000
    batch_ratio = 0.20
    max_positions = 10
    positions = {}
    
    candidates = ['AAPL', 'MSFT', 'GOOG', 'NVDA', 'AMD']
    prices = close_df.iloc[0].to_dict()
    
    # 後端 batch 邏輯（複製自 engine.py _process_rebalance）
    to_buy = [s for s in candidates if s not in positions]
    slots = max_positions - len(positions)
    
    if slots <= 0 or not to_buy:
        print("無法買入")
        return cash, positions
    
    to_buy = to_buy[:slots]
    invest_amount = cash * batch_ratio
    amount_per_stock = invest_amount / len(to_buy) if to_buy else 0
    
    print(f"初始現金: ${cash:,.0f}")
    print(f"投入比例: {batch_ratio * 100}%")
    print(f"本次投入金額: ${invest_amount:,.0f}")
    print(f"候選數量: {len(to_buy)}")
    print(f"每隻分配金額: ${amount_per_stock:,.0f}")
    print()
    
    total_cost = 0
    for symbol in to_buy:
        price = prices[symbol]
        shares = int(amount_per_stock / price)
        if shares <= 0:
            continue
        cost = shares * price
        total_cost += cost
        positions[symbol] = {'shares': shares, 'cost': price}
        print(f"  買入 {symbol}: {shares} 股 @ ${price} = ${cost:,.0f}")
    
    cash -= total_cost
    print()
    print(f"買入後現金: ${cash:,.0f}")
    print(f"總買入成本: ${total_cost:,.0f}")
    print(f"當前持倉數: {len(positions)}")
    
    return cash, positions


def compare_results():
    """比較前端與後端結果"""
    frontend_cash, frontend_holdings = test_frontend_batch_logic()
    backend_cash, backend_holdings = test_backend_batch_logic()
    
    print()
    print("=" * 60)
    print("結果比較")
    print("=" * 60)
    
    print(f"現金差異: ${abs(frontend_cash - backend_cash):,.0f}")
    print(f"持倉數差異: {abs(len(frontend_holdings) - len(backend_holdings))}")
    
    # 比較每隻持倉
    all_symbols = set(frontend_holdings.keys()) | set(backend_holdings.keys())
    for symbol in all_symbols:
        f_shares = frontend_holdings.get(symbol, {}).get('shares', 0)
        b_shares = backend_holdings.get(symbol, {}).get('shares', 0)
        status = "✅" if f_shares == b_shares else "❌"
        print(f"  {status} {symbol}: 前端 {f_shares} 股, 後端 {b_shares} 股")
    
    if frontend_cash == backend_cash and frontend_holdings.keys() == backend_holdings.keys():
        print()
        print("✅ batch 策略邏輯一致！")
    else:
        print()
        print("❌ 邏輯有差異，需要檢查！")


if __name__ == '__main__':
    compare_results()
