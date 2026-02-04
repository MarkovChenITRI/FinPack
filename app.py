"""
FinPack WebUI - 全球市場看盤模擬器
Flask 應用程式進入點
"""
from flask import Flask, render_template, jsonify, request
from utils.market import get_market_loader, get_usd_twd_rate

app = Flask(__name__)

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


if __name__ == '__main__':
    print("🚀 FinPack WebUI 啟動中...")
    print("📊 請在瀏覽器開啟 http://127.0.0.1:5000")
    app.run(debug=True, host='0.0.0.0', port=5000)
