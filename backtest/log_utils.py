"""
回測日誌工具函數

供 run.py（CLI）與 web/routes/backtest.py（API）共用，確保兩端的日誌格式
完全一致，便於 diff run.log 與 main.log 找出參數或結果差異。

【holdings 格式約定】
  log_backtest_result 的 holdings 參數中，pnl_pct 必須為百分比（如 15.2 代表 15.2%）。
  run.py 持倉的 pnl_pct 為小數（0.152），呼叫前需先 * 100。
"""
import logging

logger = logging.getLogger(__name__)

_SEP = '=' * 64


def log_backtest_input(
    config: dict,
    close_df,
    stock_info: dict,
    start_dt,
    end_dt,
    source: str = '',
) -> None:
    """
    記錄回測輸入參數（結構化格式）

    Args:
        config:     已合併的回測配置（merge_config 結果，initial_capital 為 int/float）
        close_df:   收盤價 DataFrame
        stock_info: 股票資訊 dict
        start_dt:   回測開始日期
        end_dt:     回測結束日期
        source:     呼叫來源標識，'CLI' 或 'API'
    """
    logger.info(_SEP)
    logger.info('BACKTEST INPUT [%s]', source)
    logger.info(_SEP)
    logger.info('  initial_capital      = %s TWD', f'{config["initial_capital"]:,}')
    logger.info('  amount_per_stock     = %s TWD', f'{config["amount_per_stock"]:,}')
    logger.info('  max_positions        = %s', config['max_positions'])
    logger.info('  market               = %s', config['market'])
    logger.info('  start_date (config)  = %s', config.get('start_date', 'N/A'))
    logger.info('  end_date (config)    = %s', config.get('end_date') or '(None → 今日最近交易日)')
    logger.info('  date_range (actual)  = %s ~ %s', start_dt.date(), end_dt.date())
    logger.info('  rebalance_freq       = %s', config['rebalance_freq'])
    fees = config.get('fees', {})
    logger.info('  fees.us              = rate=%.4f  min_fee=%s', fees.get('us', {}).get('rate', 0), fees.get('us', {}).get('min_fee', 0))
    logger.info('  fees.tw              = rate=%.4f  min_fee=%s', fees.get('tw', {}).get('rate', 0), fees.get('tw', {}).get('min_fee', 0))
    logger.info(
        '  close_df_shape       = %d tickers x %d dates',
        len(close_df.columns), len(close_df),
    )
    logger.info('  stock_info_count     = %d', len(stock_info))

    logger.info('  buy_conditions:')
    for key, val in config.get('buy_conditions', {}).items():
        if isinstance(val, dict):
            params = '  '.join(f'{k}={v}' for k, v in sorted(val.items()))
            logger.info('    %-24s %s', key, params)
        else:
            logger.info('    %-24s %s', key, val)

    logger.info('  sell_conditions:')
    for key, val in config.get('sell_conditions', {}).items():
        if isinstance(val, dict):
            params = '  '.join(f'{k}={v}' for k, v in sorted(val.items()))
            logger.info('    %-24s %s', key, params)
        else:
            logger.info('    %-24s %s', key, val)

    rebal = config.get('rebalance_strategy', {})
    if isinstance(rebal, dict):
        params = '  '.join(f'{k}={v}' for k, v in sorted(rebal.items()))
        logger.info('  rebalance_strategy   = %s', params)
    else:
        logger.info('  rebalance_strategy   = %s', rebal)

    logger.info(_SEP)


def log_backtest_result(
    result,
    cash_twd: float,
    holdings: list,
    elapsed: float,
    source: str = '',
) -> None:
    """
    記錄回測結果（結構化格式）

    Args:
        result:   BacktestResult 物件
        cash_twd: 剩餘現金（TWD float）
        holdings: 持倉列表，每筆 dict 含 symbol, shares, buy_date,
                  pnl_pct（百分比，如 15.2 代表 15.2%）
        elapsed:  執行時間（秒）
        source:   呼叫來源標識，'CLI' 或 'API'
    """
    logger.info(_SEP)
    logger.info('BACKTEST RESULT [%s]', source)
    logger.info(_SEP)
    logger.info('  initial_capital      = %15s TWD', f'{result.initial_capital.amount:,.0f}')
    logger.info('  final_equity         = %15s TWD', f'{result.final_equity.amount:,.0f}')
    logger.info('  total_return         = %+10.2f%%', result.total_return * 100)
    logger.info('  annualized_return    = %+10.2f%%', result.annualized_return * 100)
    logger.info('  max_drawdown         = %+10.2f%%', result.max_drawdown * 100)
    logger.info('  sharpe_ratio         = %10.4f', result.sharpe_ratio)
    logger.info('  total_trades         = %d', result.total_trades)
    logger.info('  win_trades           = %d', result.win_trades)
    logger.info('  loss_trades          = %d', result.loss_trades)
    logger.info('  win_rate             = %10.1f%%', result.win_rate * 100)
    logger.info('  cash                 = %15s TWD', f'{cash_twd:,.0f}')
    logger.info('  holdings_count       = %d', len(holdings))

    sorted_holdings = sorted(holdings, key=lambda x: x.get('buy_date', ''), reverse=True)
    for h in sorted_holdings:
        symbol   = h.get('symbol', '?')
        shares   = h.get('shares', 0)
        buy_date = h.get('buy_date', 'N/A')
        pnl      = h.get('pnl_pct', 0)
        logger.info('    %-8s shares=%-6s buy=%s  pnl=%+.2f%%', symbol, shares, buy_date, pnl)

    logger.info('  elapsed              = %.2f 秒', elapsed)
    logger.info(_SEP)
