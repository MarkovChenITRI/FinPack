"""
Web 路由模組（BTC-USD SMC 版）
"""
from .market import market_bp
from .backtest import backtest_bp

__all__ = ['market_bp', 'backtest_bp']
