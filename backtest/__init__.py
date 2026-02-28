"""
FinPack 回測模組

回測引擎與報告輸出
"""
from .engine import BacktestEngine, BacktestResult, Trade, Position, TradeType
from .report import format_backtest_report
from .config import DEFAULT_CONFIG, CONDITION_OPTIONS, load_config, merge_config, ConfigError
from .runner import run_backtest, prepare_backtest_data, resolve_date_range
from .benchmark import calculate_benchmark_curve
