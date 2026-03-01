"""
FinPack 回測入口點 (CLI)

Usage:
    python run.py --debug

處理流程與 main.py (API) 完全一致。
日誌輸出至 run.log（同時顯示於終端機）。
"""
# ===== 最優先：設定日誌系統（必須在 from core import ... 之前）=====
import logging
from log_setup import setup_logging
setup_logging('run.log')

# ===== 其他 import =====
import argparse

from core.currency import twd, usd

from backtest import format_backtest_report
from backtest.report import format_backtest_line_message
from backtest.config import load_config
from backtest.runner import run_backtest

logger = logging.getLogger('run')


def run_backtest_cli(use_cache: bool = False) -> str:
    """
    執行 CLI 回測並返回格式化文字報告

    Args:
        use_cache: 是否使用快取資料（--debug 模式）

    Returns:
        str: 格式化的回測結果
    """
    # 1. 載入並驗證配置（使用 DEFAULT_CONFIG 全部預設值）
    config = load_config({})

    # 2. 執行共用 pipeline
    ctx = run_backtest(config, source='CLI')

    result = ctx['result']
    engine = ctx['engine']
    close_df = ctx['close_df']
    stock_info = ctx['stock_info']
    end_dt = ctx['end_dt']
    elapsed = ctx['elapsed']

    # 3. 建立當前持倉（CLI 特有格式，含 Money 物件）
    from core import container
    date_index = close_df.index
    actual_end_idx = date_index.searchsorted(end_dt, side='right') - 1
    end_date_str = close_df.index[actual_end_idx].strftime('%Y-%m-%d')
    fx = container.fx

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

        # 計算損益百分比（小數）
        cost_in_twd = pos.cost_basis  # Money (TWD)
        pnl_pct = (
            (market_value.amount - cost_in_twd.amount) / cost_in_twd.amount
            if cost_in_twd.amount > 0 else 0
        )

        current_holdings.append({
            'symbol': symbol,
            'shares': pos.shares,
            'avg_cost': pos.avg_cost,          # Money
            'current_price': price_money,       # Money
            'market_value': market_value,       # Money (TWD)
            'pnl_pct': pnl_pct,                # 小數，如 0.152 = 15.2%
            'buy_date': pos.buy_date,
            'industry': stock_info.get(symbol, {}).get('industry', 'Unknown'),
            'country': country,
        })

    current_holdings.sort(key=lambda x: x['buy_date'], reverse=True)
    
    # 4. LINE 訊息（印出供外部程式擷取或傳送）
    line_msg, has_recent_trades = format_backtest_line_message(
        result=result,
        current_holdings=current_holdings,
        start_dt=ctx['start_dt'],
        end_dt=end_dt,
    )
    print(line_msg)
    print(f'has_recent_trades: {has_recent_trades}')

    # 5. 格式化完整文字報告（CLI 輸出）
    return format_backtest_report(
        result=result,
        cash=engine.cash,                           # Money (TWD)
        current_holdings=current_holdings,
        initial_capital=twd(config['initial_capital']),
        amount_per_stock=twd(config['amount_per_stock']),
        max_positions=config['max_positions'],
        start_dt=ctx['start_dt'],
        end_dt=end_dt,
        elapsed=elapsed
    )


def main():
    """CLI 入口點"""
    parser = argparse.ArgumentParser(description='FinPack 回測系統')
    parser.add_argument('--debug', action='store_true', help='啟用除錯模式（使用快取資料）')
    args = parser.parse_args()

    result = run_backtest_cli(use_cache=args.debug)
    print(result)


if __name__ == '__main__':
    main()
