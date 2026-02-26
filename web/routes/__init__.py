"""
Web 路由模組

提供 Flask Blueprint 路由
"""
from .stock import stock_bp
from .market import market_bp
from .backtest import backtest_bp

__all__ = ['stock_bp', 'market_bp', 'backtest_bp']
