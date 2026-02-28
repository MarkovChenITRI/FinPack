"""
web/market.py — MarketDataLoader 已移至 core/market.py
此檔案保留向下相容的 re-export，web/__init__.py 無需修改
"""
from core.market import MarketDataLoader

__all__ = ['MarketDataLoader']
