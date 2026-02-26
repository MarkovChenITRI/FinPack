"""
FinPack 回測模組

回測引擎與報告輸出
"""
from .engine import BacktestEngine, BacktestResult, Trade, Position, TradeType
from .report import format_backtest_report
from .config import DEFAULT_CONFIG, CONDITION_OPTIONS, merge_config
