"""
回測執行 pipeline（CLI 和 API 共用）

供 run.py 和 web/routes/backtest.py 呼叫。
依賴：core.container（全域 singleton）
"""
import logging
import pandas as pd
from datetime import datetime
from typing import Tuple

from core import container, build_close_df, filter_by_market, Indicators
from core.currency import twd, FX
from backtest.engine import BacktestEngine
from backtest.benchmark import calculate_benchmark_curve
from backtest.log_utils import log_backtest_input, log_backtest_result

logger = logging.getLogger(__name__)


def prepare_backtest_data(config: dict) -> Tuple[pd.DataFrame, dict, Indicators]:
    """
    建立 close_df、stock_info、indicators

    Args:
        config: load_config() 產生的完整配置

    Returns:
        (close_df, stock_info, indicators)

    Raises:
        RuntimeError: 資料容器未就緒或市場無資料
    """
    if not container.initialized:
        raise RuntimeError('資料容器尚未載入完成')

    close_df = build_close_df(container.aligned_data)
    if close_df.empty:
        raise RuntimeError('無可用股價資料')

    stock_info = container.stock_info
    market = config['market']
    if market != 'global':
        close_df, stock_info = filter_by_market(close_df, stock_info, market)
        if close_df.empty:
            raise RuntimeError(f'{market} 市場無可用資料')

    indicators = Indicators(close_df, stock_info)
    return close_df, stock_info, indicators


def resolve_date_range(
    config: dict, date_index: pd.DatetimeIndex
) -> Tuple[pd.Timestamp, pd.Timestamp]:
    """
    從 config 解析 start_dt / end_dt

    Args:
        config: load_config() 產生的完整配置
        date_index: close_df.index

    Returns:
        (start_dt, end_dt)

    Raises:
        ValueError: 日期不合法或超出可用範圍
    """
    end_date_str = config.get('end_date')
    # .date() 去除時間部分，避免 tz-aware date_index 比較時 TypeError
    end_dt_raw = (
        pd.Timestamp(datetime.today().date())
        if not end_date_str
        else pd.Timestamp(end_date_str)
    )
    end_idx = date_index.searchsorted(end_dt_raw, side='right') - 1
    if end_idx < 0:
        raise ValueError(f'結束日期 {end_dt_raw.date()} 早於所有可用資料')
    end_dt = date_index[end_idx]

    start_dt_raw = pd.Timestamp(config['start_date'])
    start_idx = date_index.searchsorted(start_dt_raw, side='left')
    if start_idx >= len(date_index):
        raise ValueError(f'開始日期 {start_dt_raw.date()} 晚於所有可用資料')
    start_dt = date_index[start_idx]

    if start_dt >= end_dt:
        raise ValueError(
            f'開始日期 {start_dt.date()} 必須早於結束日期 {end_dt.date()}'
        )

    return start_dt, end_dt


def run_backtest(config: dict, source: str = '') -> dict:
    """
    完整回測執行 pipeline（CLI 和 API 共用）

    Args:
        config: load_config() 產生的完整配置（已驗證）
        source: 呼叫來源 'CLI' 或 'API'（用於 log）

    Returns:
        {
            'result':          BacktestResult,
            'engine':          BacktestEngine,
            'close_df':        pd.DataFrame,
            'stock_info':      dict,
            'start_dt':        pd.Timestamp,
            'end_dt':          pd.Timestamp,
            'elapsed':         float,
            'benchmark_curve': list,
            'benchmark_name':  str,
        }

    Raises:
        RuntimeError: 資料容器未就緒或市場無資料
        ValueError: 日期範圍不合法
    """
    start_time = datetime.now()

    # 1. 資料準備
    close_df, stock_info, indicators = prepare_backtest_data(config)

    # 2. 日期解析
    start_dt, end_dt = resolve_date_range(config, close_df.index)

    # 3. 記錄輸入
    log_backtest_input(config, close_df, stock_info, start_dt, end_dt, source=source)

    # 4. 轉換 config：initial_capital / amount_per_stock → Money（engine 使用 Money 類型）
    engine_config = dict(config)
    engine_config['initial_capital'] = twd(config['initial_capital'])
    engine_config['amount_per_stock'] = twd(config['amount_per_stock'])

    # 5. 匯率服務
    fx = container.fx or FX(use_cache=True)

    # 6. 執行回測
    logger.info('[RUN] 執行回測: %s ~ %s', start_dt.date(), end_dt.date())
    engine = BacktestEngine(close_df, indicators, stock_info, engine_config, fx)
    result = engine.run(start_date=start_dt, end_date=end_dt)

    # 7. Benchmark 曲線
    trading_dates = [p['date'] for p in result.equity_curve]
    benchmark_curve, benchmark_name = calculate_benchmark_curve(
        container, config['market'], trading_dates, config['initial_capital']
    )

    elapsed = (datetime.now() - start_time).total_seconds()

    # 8. 記錄輸出（不含 holdings 詳情，由呼叫方自行記錄）
    log_backtest_result(result, engine.cash.amount, [], elapsed, source=source)

    return {
        'result': result,
        'engine': engine,
        'close_df': close_df,
        'stock_info': stock_info,
        'start_dt': start_dt,
        'end_dt': end_dt,
        'elapsed': elapsed,
        'benchmark_curve': benchmark_curve,
        'benchmark_name': benchmark_name,
    }
