"""
FinPack 回測入口點 (CLI)

Usage:
    python run.py --debug
    
處理流程與 main.py (API) 完全一致。
"""
import argparse
from datetime import datetime

import pandas as pd

from core import (
    container,
    build_close_df,
    filter_by_market,
    Indicators,
    twd, usd, FX, Money,
)

from backtest import (
    BacktestEngine,
    format_backtest_report,
    DEFAULT_CONFIG,
)

# =============================================================================
# CLI 預設值（繼承 DEFAULT_CONFIG，可覆蓋）
# =============================================================================
FRONTEND_DEFAULTS = {
    'initial_capital': twd(DEFAULT_CONFIG['initial_capital']),
    'amount_per_stock': twd(DEFAULT_CONFIG['amount_per_stock']),
    'max_positions': DEFAULT_CONFIG['max_positions'],
    'market': DEFAULT_CONFIG['market'],
    'backtest_months': DEFAULT_CONFIG['backtest_months'],
    'rebalance_freq': DEFAULT_CONFIG['rebalance_freq'],
    'buy_conditions': DEFAULT_CONFIG['buy_conditions'].copy(),
    'sell_conditions': DEFAULT_CONFIG['sell_conditions'].copy(),
    'rebalance_strategy': DEFAULT_CONFIG['rebalance_strategy'].copy(),
}


def run_backtest(use_cache: bool = False) -> str:
    """
    執行回測（使用 DataContainer 確保與 API 一致）
    
    處理流程與 main.py (API) 完全一致：
    1. 使用 DataContainer 載入並對齊資料
    2. 使用 build_close_df 建立收盤價矩陣
    3. 使用 filter_by_market 過濾市場
    4. 計算指標
    5. 執行回測
    
    Args:
        use_cache: 是否使用快取資料（--debug 模式）
    
    Returns:
        str: 格式化的回測結果
    """
    # 從預設值讀取參數
    initial_capital: Money = FRONTEND_DEFAULTS['initial_capital']
    amount_per_stock: Money = FRONTEND_DEFAULTS['amount_per_stock']
    max_positions = FRONTEND_DEFAULTS['max_positions']
    market = FRONTEND_DEFAULTS['market']
    
    # 驗證金額幣別
    assert initial_capital.is_twd(), "初始資金必須為 TWD"
    assert amount_per_stock.is_twd(), "每檔投入金額必須為 TWD"
    
    start_time = datetime.now()
    
    # 1. 使用 container 載入資料（與 API 相同）
    print("[LOAD] 使用全域 container 載入資料...")
    # container 在 import 時已自動初始化
    print(f"[OK] 載入 {len(container.get_all_tickers())} 檔股票 (更新: {container.last_update})")
    print(f"[OK] 對齊完成: {len(container.unified_dates)} 個交易日")
    
    # 2. 建立 close_df（使用共用函數）
    close_df = build_close_df(container.aligned_data)
    
    # 3. 過濾市場（使用共用函數）
    stock_info = container.stock_info
    if market != 'global':
        close_df, stock_info = filter_by_market(close_df, stock_info, market)
        print(f"[OK] 篩選 {market.upper()} 市場: {len(close_df.columns)} 檔股票")
    
    # 4. 計算指標
    print("[CALC] 計算指標...")
    indicators = Indicators(close_df, stock_info)
    _ = indicators.sharpe
    _ = indicators.rank
    _ = indicators.growth
    _ = indicators.sharpe_rank_by_country
    _ = indicators.growth_rank_by_country
    
    # 5. 準備回測配置
    config = {
        'initial_capital': initial_capital,
        'amount_per_stock': amount_per_stock,
        'max_positions': max_positions,
        'rebalance_freq': FRONTEND_DEFAULTS['rebalance_freq'],
        'buy_conditions': FRONTEND_DEFAULTS['buy_conditions'].copy(),
        'sell_conditions': FRONTEND_DEFAULTS['sell_conditions'].copy(),
        'rebalance_strategy': FRONTEND_DEFAULTS['rebalance_strategy'].copy(),
    }
    
    # 6. 解析日期
    date_index = close_df.index
    end_dt = date_index[-1]
    start_dt = end_dt - pd.DateOffset(months=FRONTEND_DEFAULTS['backtest_months'])
    
    # 7. 匯率服務（使用 container 的 FX）
    fx = container.fx or FX(use_cache=use_cache)
    print(f"[FX] {fx}")
    
    # 8. 執行回測
    print(f"[RUN] 執行回測: {start_dt.date()} ~ {end_dt.date()}...")
    engine = BacktestEngine(close_df, indicators, stock_info, config, fx)
    result = engine.run(start_date=start_dt, end_date=end_dt)
    
    # 9. 取得當前持倉（使用 Money 類型計算市值）
    actual_end_idx = date_index.searchsorted(end_dt, side='right') - 1
    end_date_str = close_df.index[actual_end_idx].strftime('%Y-%m-%d')
    
    current_holdings = []
    for symbol, pos in engine.positions.items():
        country = stock_info.get(symbol, {}).get('country', 'US')
        current_price = close_df.iloc[actual_end_idx].get(symbol, pos.avg_cost.amount)
        
        # 計算市值（統一轉換為 TWD）
        if country == 'TW':
            price_money = twd(current_price)
            market_value = twd(pos.shares * current_price)
        else:
            price_money = usd(current_price)
            market_value = fx.to_twd(usd(pos.shares * current_price), end_date_str)
        
        # 計算損益百分比
        cost_in_twd = pos.cost_basis  # Money (TWD)
        pnl_pct = (market_value.amount - cost_in_twd.amount) / cost_in_twd.amount if cost_in_twd.amount > 0 else 0
        
        current_holdings.append({
            'symbol': symbol,
            'shares': pos.shares,
            'avg_cost': pos.avg_cost,  # Money
            'current_price': price_money,  # Money
            'market_value': market_value,  # Money (TWD)
            'pnl_pct': pnl_pct,
            'buy_date': pos.buy_date,
            'industry': stock_info.get(symbol, {}).get('industry', 'Unknown'),
            'country': country,
        })
    
    current_holdings.sort(key=lambda x: x['buy_date'], reverse=True)
    
    elapsed = (datetime.now() - start_time).total_seconds()
    
    # 9. 格式化輸出
    return format_backtest_report(
        result=result,
        cash=engine.cash,  # Money (TWD)
        current_holdings=current_holdings,
        initial_capital=initial_capital,  # Money (TWD)
        amount_per_stock=amount_per_stock,  # Money (TWD)
        max_positions=max_positions,
        start_dt=start_dt,
        end_dt=end_dt,
        elapsed=elapsed
    )


def main():
    """CLI 入口點"""
    parser = argparse.ArgumentParser(description='FinPack 回測系統')
    parser.add_argument('--debug', action='store_true', help='啟用除錯模式（使用快取資料）')
    args = parser.parse_args()
    
    result = run_backtest(use_cache=args.debug)
    print(result)



if __name__ == '__main__':
    main()
