"""
FinPack WebUI - 全球市場看盤模擬器
Flask 應用程式進入點
"""
import pandas as pd
from flask import Flask, render_template, jsonify, request
from utils.market import get_market_loader, get_usd_twd_rate
from utils.stock_cache import get_stock_cache

app = Flask(__name__)

# ===== 初始化階段：預載入所有股票資料 =====
print("🚀 FinPack WebUI 啟動中...")
print("📊 正在預載入股票資料...")
stock_cache = get_stock_cache()  # 這會自動載入或抓取所有股票資料
print(f"✅ 股票資料就緒 ({len(stock_cache.get_all_tickers())} 檔股票)")

# 市場數據加載器
market_loader = get_market_loader()


@app.route('/')
def index():
    """首頁 - 顯示看盤介面"""
    return render_template('index.html')


@app.route('/api/market-data')
def get_market_data():
    """
    API: 獲取市場K線數據
    
    Query Parameters:
        period: 時間範圍 (3mo, 6mo, 1y, 2y, 5y)
        
    Returns:
        {
            "global": [...],  # 國際加權指數 K線數據
            "nasdaq": [...],  # NASDAQ K線數據
            "twii": [...],    # 台灣加權指數 K線數據
        }
    """
    period = request.args.get('period', '1y')
    
    # 驗證 period 參數
    valid_periods = ['1mo', '3mo', '6mo', '1y', '2y', '5y', 'max']
    if period not in valid_periods:
        period = '1y'
    
    try:
        # 獲取所有市場數據
        data = market_loader.get_all_market_data(period)
        data['period'] = period
        
        return jsonify(data)
        
    except Exception as e:
        return jsonify({
            'error': str(e),
            'global': [],
            'nasdaq': [],
            'twii': []
        }), 500


@app.route('/api/exchange-rate')
def get_exchange_rate():
    """
    API: 獲取美元兌台幣匯率
    
    Returns:
        {"rate": 32.0}
    """
    rate = get_usd_twd_rate()
    return jsonify({'rate': rate})


@app.route('/api/kline/<symbol>')
def get_kline(symbol):
    """
    API: 獲取指定股票/指數的K線數據
    
    Path Parameters:
        symbol: 股票/指數代碼 (如 ^GSPC, ^TWII, AAPL)
        
    Query Parameters:
        period: 時間範圍 (1y, 2y, 5y, max)
        
    Returns:
        [{time, open, high, low, close, volume, turnover}, ...]
    """
    period = request.args.get('period', '1y')
    
    try:
        data = market_loader.get_weighted_kline(symbol, period)
        return jsonify({
            'symbol': symbol,
            'data': data,
            'count': len(data)
        })
    except Exception as e:
        return jsonify({
            'error': str(e),
            'symbol': symbol,
            'data': []
        }), 500


@app.route('/api/date-info/<date>')
def get_date_info(date):
    """
    API: 獲取指定日期的市場資訊
    
    Path Parameters:
        date: 日期 (格式: YYYY-MM-DD)
        
    Returns:
        {
            "date": "2024-01-15",
            "us": {"open": ..., "close": ...},
            "tw": {"open": ..., "close": ...}
        }
    """
    try:
        us_data = market_loader.get_weighted_kline('^GSPC', '2y')
        tw_data = market_loader.get_weighted_kline('^TWII', '2y')
        
        us_match = next((d for d in us_data if d['time'] == date), None)
        tw_match = next((d for d in tw_data if d['time'] == date), None)
        
        return jsonify({
            'date': date,
            'us': us_match,
            'tw': tw_match
        })
        
    except Exception as e:
        return jsonify({
            'error': str(e),
            'date': date
        }), 500


# ===== 股票 Sharpe 資料 API =====

@app.route('/api/stocks')
def get_stocks():
    """
    API: 獲取所有股票清單
    
    Query Parameters:
        country: 篩選國家 (US/TW)
        industry: 篩選產業
        
    Returns:
        {
            "count": 50,
            "stocks": [
                {"ticker": "AAPL", "country": "US", "industry": "Tech"},
                ...
            ]
        }
    """
    country = request.args.get('country')
    industry = request.args.get('industry')
    
    if country:
        tickers = stock_cache.get_tickers_by_country(country.upper())
    elif industry:
        tickers = stock_cache.get_tickers_by_industry(industry)
    else:
        tickers = stock_cache.get_all_tickers()
    
    stocks = []
    for ticker in tickers:
        info = stock_cache.get_stock_info(ticker)
        stocks.append({
            'ticker': ticker,
            'country': info.get('country', ''),
            'industry': info.get('industry', ''),
            'provider': info.get('provider', '')
        })
    
    return jsonify({
        'count': len(stocks),
        'stocks': stocks
    })


@app.route('/api/stocks/industries')
def get_industries():
    """
    API: 獲取所有產業清單
    
    Returns:
        {"industries": ["Tech", "Finance", ...]}
    """
    return jsonify({
        'industries': stock_cache.get_industries()
    })


@app.route('/api/stocks/<ticker>/sharpe')
def get_stock_sharpe(ticker):
    """
    API: 獲取單一股票的 Sharpe 時間序列
    
    Path Parameters:
        ticker: 股票代碼
        
    Returns:
        {
            "ticker": "AAPL",
            "info": {"country": "US", "industry": "Tech"},
            "data": [{"date": "2024-01-15", "sharpe": 1.5}, ...]
        }
    """
    sharpe = stock_cache.get_stock_sharpe(ticker)
    info = stock_cache.get_stock_info(ticker)
    
    if sharpe.empty:
        return jsonify({
            'error': f'No data for {ticker}',
            'ticker': ticker
        }), 404
    
    data = [
        {'date': str(idx)[:10], 'sharpe': round(val, 3) if not pd.isna(val) else None}
        for idx, val in sharpe.items()
    ]
    
    return jsonify({
        'ticker': ticker,
        'info': info,
        'data': data,
        'count': len(data)
    })


@app.route('/api/sharpe/summary')
def get_sharpe_summary():
    """
    API: 獲取 Sharpe 摘要（按國家分組）
    
    Query Parameters:
        date: 指定日期 (YYYY-MM-DD)，預設為最新日期
        
    Returns:
        {
            "date": "2024-01-15",
            "US": {"count": 30, "mean": 1.2, "max": 2.5, "top3": [...]},
            "TW": {"count": 20, "mean": 0.8, "max": 1.8, "top3": [...]}
        }
    """
    date = request.args.get('date')
    summary = stock_cache.get_daily_sharpe_summary(date)
    
    return jsonify(summary)


@app.route('/api/sharpe/matrix')
def get_sharpe_matrix():
    """
    API: 獲取 Sharpe 矩陣
    
    Query Parameters:
        start: 開始日期 (YYYY-MM-DD)
        end: 結束日期 (YYYY-MM-DD)
        country: 篩選國家 (US/TW)
        
    Returns:
        {
            "dates": ["2024-01-01", ...],
            "tickers": ["AAPL", "GOOGL", ...],
            "data": [[1.2, 0.8, ...], ...]
        }
    """
    start = request.args.get('start')
    end = request.args.get('end')
    country = request.args.get('country')
    
    matrix = stock_cache.get_sharpe_matrix(start, end)
    
    if matrix.empty:
        return jsonify({
            'error': 'No data available',
            'dates': [],
            'tickers': [],
            'data': []
        })
    
    # 按國家篩選
    if country:
        tickers = stock_cache.get_tickers_by_country(country.upper())
        matrix = matrix[[c for c in matrix.columns if c in tickers]]
    
    # 轉換為 JSON 格式
    dates = [str(d)[:10] for d in matrix.index]
    tickers = list(matrix.columns)
    data = matrix.fillna(0).round(3).values.tolist()
    
    return jsonify({
        'dates': dates,
        'tickers': tickers,
        'data': data
    })


@app.route('/api/industry/data')
def get_industry_data():
    """
    API: 獲取完整的產業分析資料（供前端快取使用）
    
    一次性返回所有日期的 Sharpe 和 Slope 矩陣，讓前端可以即時計算 Top 15
    
    Query Parameters:
        period: 時間範圍 (3mo, 6mo, 1y)，預設 1y
        
    Returns:
        {
            "dates": ["2024-01-01", ...],
            "tickers": ["AAPL", "GOOGL", ...],
            "stockInfo": {"AAPL": {"country": "US", "industry": "Tech"}, ...},
            "sharpe": [[1.2, 0.8, ...], ...],  # 每日每股的 Sharpe
            "slope": [[0.01, -0.02, ...], ...]  # 每日每股的 Slope
        }
    """
    import pandas as pd
    from datetime import datetime, timedelta
    
    period = request.args.get('period', '1y')
    
    # 計算時間範圍
    end_date = datetime.now()
    period_days = {'3mo': 90, '6mo': 180, '1y': 365, '2y': 730, '5y': 1825, '6y': 2190}
    days = period_days.get(period, 365)
    start_date = end_date - timedelta(days=days)
    
    # 取得矩陣
    sharpe_matrix = stock_cache.sharpe_matrix
    slope_matrix = stock_cache.slope_matrix
    
    if sharpe_matrix is None or sharpe_matrix.empty:
        return jsonify({
            'error': 'No data available',
            'dates': [],
            'tickers': [],
            'stockInfo': {},
            'sharpe': [],
            'slope': []
        })
    
    # 過濾時間範圍
    sharpe_filtered = sharpe_matrix[sharpe_matrix.index >= start_date.strftime('%Y-%m-%d')]
    slope_filtered = slope_matrix[slope_matrix.index >= start_date.strftime('%Y-%m-%d')] if slope_matrix is not None else pd.DataFrame()
    
    # 取得共同的 tickers
    tickers = list(sharpe_filtered.columns)
    
    # 取得股票資訊
    stock_info = {}
    for ticker in tickers:
        info = stock_cache.get_stock_info(ticker)
        stock_info[ticker] = {
            'country': info.get('country', ''),
            'industry': info.get('industry', '未分類')
        }
    
    # 轉換為 JSON 格式（將 NaN 替換為 None，確保 JSON 相容）
    import math
    dates = [str(d)[:10] for d in sharpe_filtered.index]
    
    def clean_nan(matrix):
        """將 NaN 替換為 None（JSON null）"""
        result = []
        for row in matrix.values.tolist():
            clean_row = []
            for val in row:
                if val is None or (isinstance(val, float) and math.isnan(val)):
                    clean_row.append(None)
                else:
                    clean_row.append(round(val, 4) if isinstance(val, float) else val)
            result.append(clean_row)
        return result
    
    sharpe_data = clean_nan(sharpe_filtered)
    slope_data = clean_nan(slope_filtered) if not slope_filtered.empty else []
    
    return jsonify({
        'dates': dates,
        'tickers': tickers,
        'stockInfo': stock_info,
        'sharpe': sharpe_data,
        'slope': slope_data
    })


@app.route('/api/stock-price/<ticker>')
def get_stock_price(ticker):
    """
    API: 取得股票在特定日期的價格
    
    Path Parameters:
        ticker: 股票代碼
        
    Query Parameters:
        date: 日期 (YYYY-MM-DD)
        
    Returns:
        {
            "ticker": "AAPL",
            "date": "2026-02-04",
            "open": 100.0,
            "high": 105.0,
            "low": 98.0,
            "close": 103.0,
            "country": "US",
            "industry": "Tech"
        }
    """
    date = request.args.get('date')
    if not date:
        return jsonify({'error': '請提供 date 參數'}), 400
    
    result = stock_cache.get_stock_price(ticker, date)
    
    if 'error' in result:
        return jsonify(result), 404
    
    return jsonify(result)


@app.route('/api/backtest/prices')
def get_backtest_prices():
    """
    API: 獲取回測用的股票價格矩陣
    
    Query Parameters:
        start_date: 開始日期 (YYYY-MM-DD)
        end_date: 結束日期 (YYYY-MM-DD)
        
    Returns:
        {
            "dates": ["2024-01-01", ...],
            "tickers": ["AAPL", "2330.TW", ...],
            "prices": {
                "AAPL": {"2024-01-01": {"open": 100, "high": 105, "low": 98, "close": 103}, ...},
                ...
            },
            "stockInfo": {"AAPL": {"country": "US", "industry": "Tech"}, ...}
        }
    """
    import math
    from datetime import datetime, timedelta
    
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    if not start_date or not end_date:
        return jsonify({'error': '請提供 start_date 和 end_date 參數'}), 400
    
    # 取得所有交易日（使用 sharpe_matrix 的日期索引）
    if stock_cache.sharpe_matrix is None:
        return jsonify({'error': '尚未載入資料'}), 500
    
    all_dates = [str(d)[:10] for d in stock_cache.sharpe_matrix.index]
    
    # 過濾日期範圍
    dates = [d for d in all_dates if start_date <= d <= end_date]
    
    if len(dates) == 0:
        return jsonify({'error': '指定日期範圍內無資料'}), 404
    
    # 取得所有 tickers
    tickers = stock_cache.get_all_tickers()
    
    # 建立價格資料（含缺失填充）
    prices = {}
    stock_info = {}
    
    for ticker in tickers:
        info = stock_cache.get_stock_info(ticker)
        stock_info[ticker] = {
            'country': info.get('country', ''),
            'industry': info.get('industry', '未分類')
        }
        
        # 取得該股票的價格資料
        ticker_prices = {}
        ohlcv = stock_cache.get_stock_ohlcv(ticker)
        last_known_price = None  # 追蹤上一個已知價格
        
        if ohlcv is not None and not ohlcv.empty:
            for date in dates:
                if date in ohlcv.index:
                    row = ohlcv.loc[date]
                    close_val = row.get('Close', float('nan'))
                    
                    # 檢查 close 是否有效
                    if not math.isnan(close_val):
                        ticker_prices[date] = {
                            'open': round(row.get('Open', 0), 2) if not math.isnan(row.get('Open', float('nan'))) else round(close_val, 2),
                            'high': round(row.get('High', 0), 2) if not math.isnan(row.get('High', float('nan'))) else round(close_val, 2),
                            'low': round(row.get('Low', 0), 2) if not math.isnan(row.get('Low', float('nan'))) else round(close_val, 2),
                            'close': round(close_val, 2)
                        }
                        last_known_price = round(close_val, 2)
                    elif last_known_price is not None:
                        # 使用上一個已知價格填充缺失
                        ticker_prices[date] = {
                            'open': last_known_price,
                            'high': last_known_price,
                            'low': last_known_price,
                            'close': last_known_price,
                            'filled': True  # 標記為填充資料
                        }
                elif last_known_price is not None:
                    # 該日期完全沒有資料，使用上一個已知價格填充
                    ticker_prices[date] = {
                        'open': last_known_price,
                        'high': last_known_price,
                        'low': last_known_price,
                        'close': last_known_price,
                        'filled': True  # 標記為填充資料
                    }
        
        if ticker_prices:
            prices[ticker] = ticker_prices
    
    return jsonify({
        'dates': dates,
        'tickers': list(prices.keys()),
        'prices': prices,
        'stockInfo': stock_info
    })


@app.route('/api/cache/refresh', methods=['POST'])
def refresh_cache():
    """
    API: 強制重新抓取股票資料
    
    Returns:
        {"status": "success", "count": 50}
    """
    global stock_cache
    from utils.stock_cache import refresh_stock_cache
    
    stock_cache = refresh_stock_cache()
    
    return jsonify({
        'status': 'success',
        'count': len(stock_cache.get_all_tickers()),
        'last_update': str(stock_cache.last_update)
    })


# ===== 產業 Top 分析 API =====

@app.route('/api/industry/top')
def get_industry_top():
    """
    API: 獲取 Sharpe Top N 的產業分布分析
    
    Query Parameters:
        country: 篩選國家 (US/TW)，不填則全市場
        top: Top N 數量，預設 15
        date: 指定日期 (YYYY-MM-DD)，不填則使用最新日期
        
    Returns:
        {
            "date": "2024-01-15",
            "industries": [
                {"name": "半導體", "total": 5, "US": 3, "TW": 2, "stocks": ["NVDA", ...]},
                ...
            ],
            "top_stocks": [{"ticker": "NVDA", "sharpe": 2.5, "country": "US", "industry": "半導體"}, ...]
        }
    """
    from utils.stock_cache import get_industry_top_analysis
    
    country = request.args.get('country')
    top_n = request.args.get('top', 15, type=int)
    date = request.args.get('date')  # 新增 date 參數
    
    if country:
        country = country.upper()
    
    result = get_industry_top_analysis(stock_cache, country=country, top_n=top_n, date=date)
    
    return jsonify(result)


@app.route('/api/industry/slope-top')
def get_industry_slope_top():
    """
    API: 獲取 Sharpe Slope (增長率) Top N 的產業分布分析
    
    Query Parameters:
        country: 篩選國家 (US/TW)，不填則全市場
        top: Top N 數量，預設 15
        date: 指定日期 (YYYY-MM-DD)，不填則使用最新日期
        
    Returns:
        {
            "date": "2024-01-15",
            "industries": [
                {"name": "半導體", "total": 5, "US": 3, "TW": 2, "stocks": ["NVDA", ...]},
                ...
            ],
            "top_stocks": [{"ticker": "NVDA", "slope": 0.005, "country": "US", "industry": "半導體"}, ...]
        }
    """
    from utils.stock_cache import get_slope_top_analysis
    
    country = request.args.get('country')
    top_n = request.args.get('top', 15, type=int)
    date = request.args.get('date')  # 新增 date 參數
    
    if country:
        country = country.upper()
    
    result = get_slope_top_analysis(stock_cache, country=country, top_n=top_n, date=date)
    
    return jsonify(result)


if __name__ == '__main__':
    print("🚀 FinPack WebUI 啟動中...")
    print("📊 請在瀏覽器開啟 http://127.0.0.1:5000")
    app.run(debug=True, host='0.0.0.0', port=5000)
