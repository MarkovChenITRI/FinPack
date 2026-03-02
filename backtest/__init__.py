"""
FinPackV2 回測模組（BTC-USD SMC 版）

主要入口：
    from backtest.smc_config import load_smc_config
    from backtest.smc_engine import SmcEngine

保留的參考模板（股票多資產策略）：
    backtest/engine.py    - 多資產回測引擎設計模式
    backtest/runner.py    - pipeline 架構模式
    backtest/config.py    - 條件配置系統模式
    backtest/report.py    - 報告格式化模式
    backtest/benchmark.py - 基準比較模式
"""
# SMC 策略（BTC-USD 主要使用）
from .smc_config import load_smc_config, DEFAULT_SMC_CONFIG, SMC_CONDITION_OPTIONS, SmcConfigError
from .smc_engine import SmcEngine, SmcBacktestResult, SmcTrade, SmcPosition
