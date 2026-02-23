"""
API 路由層

僅提供資料，不執行回測/模擬計算
"""
from flask import Flask
from .market import market_bp
from .stock import stock_bp


def register_blueprints(app: Flask):
    """註冊所有 Blueprint"""
    app.register_blueprint(market_bp, url_prefix='/api')
    app.register_blueprint(stock_bp, url_prefix='/api')
    print("  ✓ market_bp → /api/market-data, /api/kline/<symbol>")
    print("  ✓ stock_bp → /api/stocks, /api/industry/data, /api/backtest/prices")
