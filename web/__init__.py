"""
Web 應用模組

提供 Flask Web 應用的路由與市場資料載入

注意：此模組不導入 core 或 backtest，依賴由 main.py 注入
"""
from .market import MarketDataLoader

__all__ = [
    'MarketDataLoader',
]
