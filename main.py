from src.stock import SimulatedMarket, MaxSharpeStrategy, Trader

# 解析參數
topk = 10
max_weight = 1 / topk

# 初始化市場模擬器（只需執行一次）
_market_simulator = SimulatedMarket(
    watchlist_id="118349730",
    session_id="b379eetq1pojcel6olyymmpo1rd41nng",
    fallback_date="max"
)
_market_simulator.build_portfolio_data(
    sharpe_window=252, 
    slope_window=365, 
    ma_period=30
)
print("✅ Market simulator initialized")

# 執行回測（比較不同 rebalance 頻率）
print("🔄 Running backtest...")
traders = [
    Trader(balance=10000, strategy=MaxSharpeStrategy(topk=topk, max_weight=max_weight), rebalance_frequency='daily'),
    Trader(balance=10000, strategy=MaxSharpeStrategy(topk=topk, max_weight=max_weight), rebalance_frequency='weekly'),
    Trader(balance=10000, strategy=MaxSharpeStrategy(topk=topk, max_weight=max_weight), rebalance_frequency='monthly'),
    Trader(balance=10000, strategy=MaxSharpeStrategy(topk=topk, max_weight=max_weight), rebalance_frequency='quarterly'),
    Trader(balance=10000, strategy=MaxSharpeStrategy(topk=topk, max_weight=max_weight), rebalance_frequency='yearly')
]
_market_simulator.run(traders)
print("✅ Backtest completed")

# 生成交易建議
recommendation = _market_simulator.get_trading_recommendation(MaxSharpeStrategy(topk=topk, max_weight=max_weight))
print(recommendation)