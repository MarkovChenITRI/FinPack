"""
市場數據 API 路由

路由：
- GET /api/market-data      市場 K 線數據
- GET /api/kline/<symbol>   單一標的 K 線
- GET /api/exchange-rate    匯率查詢
- GET /api/date-info/<date> 指定日期市場資訊
- GET /api/market-status    市場狀態
"""
from datetime import datetime
from flask import Blueprint, jsonify, request

from core import container

market_bp = Blueprint('market', __name__)


@market_bp.route('/market-data')
def get_market_data():
    """
    API: 獲取市場 K 線數據
    
    Query Parameters:
        period: 時間範圍 (3mo, 6mo, 1y, 2y, 5y)
        
    Returns:
        {
            "global": [...],
            "nasdaq": [...],
            "twii": [...],
            "gold": [...],
            "btc": [...],
            "bonds": [...]
        }
    """
    period = request.args.get('period', '1y')
    valid_periods = ['1mo', '3mo', '6mo', '1y', '2y', '5y', 'max']
    if period not in valid_periods:
        period = '1y'
    
    try:
        data = container.get_market_data(period)
        data['period'] = period
        return jsonify(data)
    except Exception as e:
        return jsonify({
            'error': str(e),
            'global': [],
            'nasdaq': [],
            'twii': []
        }), 500


@market_bp.route('/kline/<symbol>')
def get_kline(symbol):
    """
    API: 獲取指定標的 K 線數據
    
    Path Parameters:
        symbol: 股票/指數代碼
        
    Query Parameters:
        period: 時間範圍 (1y, 2y, 5y, max)
    """
    period = request.args.get('period', '1y')
    
    try:
        data = container.get_kline(symbol, period)
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


@market_bp.route('/exchange-rate')
def get_exchange_rate():
    """
    API: 獲取美元兌台幣匯率
    
    Query Parameters:
        history: 如果為 true，返回歷史匯率數據
        
    Returns:
        無 history: {"rate": 31.44}
        有 history: {"rate": 31.44, "history": {"2024-01-02": 31.5, ...}}
    """
    rate = container.get_exchange_rate()
    
    include_history = request.args.get('history', 'false').lower() == 'true'
    
    if include_history:
        history = container.get_exchange_rate_history()
        return jsonify({
            'rate': rate,
            'history': history,
            'count': len(history)
        })
    
    return jsonify({'rate': rate})


@market_bp.route('/market-status')
def get_market_status():
    """
    API: 獲取市場狀態（根據最新資料日期判斷）
    
    Returns:
        {
            "us_latest_date": "2026-02-21",
            "tw_latest_date": "2026-02-21",
            "today": "2026-02-23"
        }
    """
    today = datetime.now().strftime('%Y-%m-%d')
    
    # 取得美股和台股指數的最新資料日期
    us_data = container.get_kline('^IXIC', '1y')
    tw_data = container.get_kline('^TWII', '1y')
    
    us_latest = us_data[-1]['time'] if us_data else None
    tw_latest = tw_data[-1]['time'] if tw_data else None
    
    return jsonify({
        'us_latest_date': us_latest,
        'tw_latest_date': tw_latest,
        'today': today
    })


@market_bp.route('/date-info/<date>')
def get_date_info(date):
    """
    API: 獲取指定日期的市場資訊
    
    Path Parameters:
        date: 日期 (YYYY-MM-DD)
    """
    try:
        us_data = container.get_kline('^GSPC', '2y')
        tw_data = container.get_kline('^TWII', '2y')
        
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
