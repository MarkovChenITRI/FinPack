"""
utils - 後端工具模組

模組列表：
    stock_cache  核心數據快取 (見 stock_cache.py)
    market       大盤指數數據 (見 market.py)

資料流：
    yfinance → stock_cache.raw_data → aligned_data → sharpe_matrix/slope_matrix
                                      ↓
                               market.py (大盤 K 線)
"""
