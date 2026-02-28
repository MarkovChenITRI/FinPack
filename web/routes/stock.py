"""
股票數據 API 路由

路由：
- GET /api/stocks                股票清單
- GET /api/stocks/industries     產業清單
- GET /api/stocks/<ticker>/sharpe 單一股票 Sharpe
- GET /api/sharpe/summary        Sharpe 摘要
- GET /api/sharpe/matrix         Sharpe 矩陣
- GET /api/industry/data         產業分析資料 (含排名)
- GET /api/industry/top          Sharpe Top N 分析
- GET /api/industry/slope-top    排名變化 Top N 分析
- GET /api/stock-price/<ticker>  股票價格查詢
- POST /api/cache/refresh        重新抓取資料
- GET /api/backtest/prices       回測用價格數據
"""
import logging
import math
import pandas as pd
from datetime import datetime, timedelta
from flask import Blueprint, jsonify, request

from core import container, compute_daily_ranks_by_country

logger = logging.getLogger(__name__)

stock_bp = Blueprint('stock', __name__)

PERIOD_DAYS = {'3mo': 90, '6mo': 180, '1y': 365, '2y': 730, '5y': 1825, '6y': 2190}


def get_container():
    """取得資料容器實例"""
    return container


def clean_nan(matrix):
    """將 NaN/Inf 替換為 None（JSON null）"""
    result = []
    for row in matrix.values.tolist():
        clean_row = []
        for val in row:
            if val is None:
                clean_row.append(None)
            elif isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
                clean_row.append(None)
            else:
                clean_row.append(round(val, 4) if isinstance(val, float) else val)
        result.append(clean_row)
    return result


@stock_bp.route('/stocks')
def get_stocks():
    """API: 獲取所有股票清單"""
    country = request.args.get('country')
    industry = request.args.get('industry')
    
    if country:
        tickers = container.get_tickers_by_country(country.upper())
    elif industry:
        tickers = container.get_tickers_by_industry(industry)
    else:
        tickers = container.get_all_tickers()
    
    stocks = []
    for ticker in tickers:
        info = container.get_stock_info(ticker)
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


@stock_bp.route('/stocks/industries')
def get_industries():
    """API: 獲取所有產業清單"""
    return jsonify({
        'industries': container.get_industries()
    })


@stock_bp.route('/stocks/<ticker>/sharpe')
def get_stock_sharpe(ticker):
    """API: 獲取單一股票的 Sharpe 時間序列"""
    sharpe = container.get_stock_sharpe(ticker)
    info = container.get_stock_info(ticker)
    
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


@stock_bp.route('/sharpe/summary')
def get_sharpe_summary():
    """API: 獲取 Sharpe 摘要（按國家分組）"""
    date = request.args.get('date')
    summary = container.get_daily_sharpe_summary(date)
    return jsonify(summary)


@stock_bp.route('/sharpe/matrix')
def get_sharpe_matrix():
    """API: 獲取 Sharpe 矩陣"""
    start = request.args.get('start')
    end = request.args.get('end')
    country = request.args.get('country')
    
    matrix = container.get_sharpe_matrix(start, end)
    
    if matrix.empty:
        return jsonify({
            'error': 'No data available',
            'dates': [],
            'tickers': [],
            'data': []
        })
    
    if country:
        tickers = container.get_tickers_by_country(country.upper())
        matrix = matrix[[c for c in matrix.columns if c in tickers]]
    
    dates = [str(d)[:10] for d in matrix.index]
    tickers = list(matrix.columns)
    data = matrix.fillna(0).round(3).values.tolist()
    
    return jsonify({
        'dates': dates,
        'tickers': tickers,
        'data': data
    })


@stock_bp.route('/industry/data')
def get_industry_data():
    """API: 獲取完整的產業分析資料"""
    period = request.args.get('period', '1y')
    logger.info('[API] /api/industry/data 請求: period=%s', period)
    
    # 計算時間範圍
    end_date = datetime.now()
    days = PERIOD_DAYS.get(period, 365)
    start_date = end_date - timedelta(days=days)

    sharpe_matrix = container.sharpe_matrix
    growth_matrix = container.growth_matrix
    
    if sharpe_matrix is None or sharpe_matrix.empty:
        return jsonify({
            'error': 'No data available',
            'dates': [],
            'tickers': [],
            'stockInfo': {},
            'sharpe': [],
            'growth': [],
            'sharpeRank': {},
            'growthRank': {}
        })
    
    # 過濾時間範圍
    sharpe_filtered = sharpe_matrix[sharpe_matrix.index >= start_date.strftime('%Y-%m-%d')]
    growth_filtered = growth_matrix[growth_matrix.index >= start_date.strftime('%Y-%m-%d')] if growth_matrix is not None else pd.DataFrame()
    
    tickers = list(sharpe_filtered.columns)
    
    # 取得股票資訊
    stock_info = {}
    for ticker in tickers:
        info = container.get_stock_info(ticker)
        stock_info[ticker] = {
            'country': info.get('country', ''),
            'industry': info.get('industry', '未分類')
        }
    
    dates = [str(d)[:10] for d in sharpe_filtered.index]
    sharpe_data = clean_nan(sharpe_filtered)
    growth_data = clean_nan(growth_filtered) if not growth_filtered.empty else []
    
    # 預計算每日排名
    sharpe_rank = compute_daily_ranks_by_country(sharpe_filtered, stock_info)
    growth_rank = compute_daily_ranks_by_country(growth_filtered, stock_info) if not growth_filtered.empty else {}
    
    logger.info('[API] /api/industry/data 返回: %d 天, %d 檔股票', len(dates), len(tickers))
    
    return jsonify({
        'dates': dates,
        'tickers': tickers,
        'stockInfo': stock_info,
        'sharpe': sharpe_data,
        'growth': growth_data,
        'sharpeRank': sharpe_rank,
        'growthRank': growth_rank
    })


@stock_bp.route('/stock-price/<ticker>')
def get_stock_price(ticker):
    """API: 取得股票在特定日期的價格"""
    date = request.args.get('date')
    
    if not date:
        return jsonify({'error': '請提供 date 參數'}), 400
    
    result = container.get_stock_price(ticker, date)
    
    if 'error' in result:
        return jsonify(result), 404
    
    return jsonify(result)


@stock_bp.route('/backtest/prices')
def get_backtest_prices():
    """API: 獲取回測用的股票價格數據"""
    period = request.args.get('period', '2y')
    
    # 計算時間範圍
    end_date = datetime.now()
    days = PERIOD_DAYS.get(period, 730)
    start_date = end_date - timedelta(days=days)
    
    tickers = container.get_all_tickers()
    
    # 收集每支股票的價格數據
    prices = {}
    for ticker in tickers:
        try:
            kline = container.get_kline(ticker, period)
            if kline:
                prices[ticker] = {d['time']: d['close'] for d in kline}
        except:
            continue
    
    # 加入指數數據供 benchmark 使用
    for symbol in ['^IXIC', '^TWII', '^GSPC']:
        try:
            kline = container.get_kline(symbol, period)
            if kline:
                prices[symbol] = {d['time']: d['close'] for d in kline}
        except:
            continue
    
    # 獲取所有日期
    all_dates = set()
    for ticker_prices in prices.values():
        all_dates.update(ticker_prices.keys())
    
    dates = sorted([d for d in all_dates if d >= start_date.strftime('%Y-%m-%d')])
    
    return jsonify({
        'dates': dates,
        'tickers': list(prices.keys()),
        'prices': prices
    })


@stock_bp.route('/industry/top')
def get_industry_top():
    """API: 獲取 Sharpe Top N 的產業分布分析"""
    country = request.args.get('country')
    top_n = request.args.get('top', 15, type=int)
    date = request.args.get('date')
    
    if country:
        country = country.upper()
    
    result = _get_top_analysis(container, container.sharpe_matrix, country, top_n, 'sharpe', date)
    return jsonify(result)


@stock_bp.route('/industry/slope-top')
def get_industry_slope_top():
    """API: 獲取排名變化 Top N 的產業分布分析"""
    country = request.args.get('country')
    top_n = request.args.get('top', 15, type=int)
    date = request.args.get('date')
    
    if country:
        country = country.upper()
    
    result = _get_growth_analysis_with_sharpe_filter(container, country, top_n, date)
    return jsonify(result)


@stock_bp.route('/cache/refresh', methods=['POST'])
def refresh_cache():
    """API: 強制重新抓取股票資料"""
    container.load_or_fetch(force_refresh=True)
    
    return jsonify({
        'status': 'success',
        'count': len(container.get_all_tickers()),
        'last_update': str(container.last_update)
    })


# ===== 分析函數 =====

def _get_top_analysis(container, matrix, country, top_n, value_name, target_date=None):
    """通用的 Top 分析邏輯"""
    if matrix is None or matrix.empty:
        return {'date': None, 'industries': [], 'top_stocks': []}
    
    us_tickers = set(container.get_tickers_by_country('US'))
    tw_tickers = set(container.get_tickers_by_country('TW'))
    
    if target_date:
        target_date_str = str(target_date)[:10]
        for date in matrix.index:
            if str(date)[:10] == target_date_str:
                current_row = matrix.loc[date]
                
                if country == 'US':
                    row = current_row[current_row.index.isin(us_tickers)].dropna()
                elif country == 'TW':
                    row = current_row[current_row.index.isin(tw_tickers)].dropna()
                else:
                    us_valid = current_row[current_row.index.isin(us_tickers)].dropna()
                    tw_valid = current_row[current_row.index.isin(tw_tickers)].dropna()
                    row = pd.concat([us_valid, tw_valid])
                
                if not row.empty:
                    return _build_analysis_result(container, row, date, top_n, value_name)
        
        return {'date': target_date_str, 'industries': [], 'top_stocks': []}
    
    # 尋找最新有效日期
    latest_date = None
    row = None
    
    for date in reversed(matrix.index):
        current_row = matrix.loc[date]
        
        if country == 'US':
            valid_data = current_row[current_row.index.isin(us_tickers)].dropna()
            if len(valid_data) >= min(top_n, len(us_tickers)):
                latest_date = date
                row = valid_data
                break
        elif country == 'TW':
            valid_data = current_row[current_row.index.isin(tw_tickers)].dropna()
            if len(valid_data) >= min(top_n, len(tw_tickers)):
                latest_date = date
                row = valid_data
                break
        else:
            us_valid = current_row[current_row.index.isin(us_tickers)].dropna()
            tw_valid = current_row[current_row.index.isin(tw_tickers)].dropna()
            if len(us_valid) > 0 and len(tw_valid) > 0:
                all_valid = pd.concat([us_valid, tw_valid])
                latest_date = date
                row = all_valid
                break
    
    if latest_date is None or row is None or row.empty:
        return {'date': None, 'industries': [], 'top_stocks': []}
    
    return _build_analysis_result(container, row, latest_date, top_n, value_name)


def _build_analysis_result(container, row, date, top_n, value_name):
    """建立分析結果"""
    top_stocks = row.nlargest(top_n)
    
    industry_stats = {}
    top_stock_list = []
    
    for ticker, value in top_stocks.items():
        info = container.get_stock_info(ticker)
        industry = info.get('industry', '未分類')
        stock_country = info.get('country', '')
        
        top_stock_list.append({
            'ticker': ticker,
            value_name: round(value, 6) if value_name == 'slope' else round(value, 3),
            'country': stock_country,
            'industry': industry
        })
        
        if industry not in industry_stats:
            industry_stats[industry] = {
                'total': 0, 'US': 0, 'TW': 0,
                'stocks': [],
                'US_stocks': [],
                'TW_stocks': []
            }
        
        industry_stats[industry]['total'] += 1
        industry_stats[industry]['stocks'].append(ticker)
        
        if stock_country == 'US':
            industry_stats[industry]['US'] += 1
            industry_stats[industry]['US_stocks'].append(ticker)
        elif stock_country == 'TW':
            industry_stats[industry]['TW'] += 1
            industry_stats[industry]['TW_stocks'].append(ticker)
    
    industries = [
        {'name': name, **stats}
        for name, stats in industry_stats.items()
    ]
    industries.sort(key=lambda x: x['total'], reverse=True)
    
    return {
        'date': str(date)[:10],
        'industries': industries,
        'top_stocks': top_stock_list
    }


def _get_growth_analysis_with_sharpe_filter(container, country, top_n, target_date=None):
    """帶有 Sharpe 產業過濾的 Growth 分析"""
    sharpe_matrix = container.sharpe_matrix
    growth_matrix = container.growth_matrix
    
    if sharpe_matrix is None or sharpe_matrix.empty or growth_matrix is None or growth_matrix.empty:
        return {'date': None, 'industries': [], 'top_stocks': [], 'sharpe_top_industries': []}
    
    us_tickers = set(container.get_tickers_by_country('US'))
    tw_tickers = set(container.get_tickers_by_country('TW'))
    
    actual_date = None
    sharpe_row = None
    growth_row = None
    
    if target_date:
        target_date_str = str(target_date)[:10]
        for date in sharpe_matrix.index:
            if str(date)[:10] == target_date_str:
                actual_date = date
                sharpe_row = sharpe_matrix.loc[date]
                growth_row = growth_matrix.loc[date] if date in growth_matrix.index else None
                break
    else:
        for date in reversed(sharpe_matrix.index):
            sharpe_current = sharpe_matrix.loc[date]
            growth_current = growth_matrix.loc[date] if date in growth_matrix.index else None
            
            if country == 'US':
                valid_sharpe = sharpe_current[sharpe_current.index.isin(us_tickers)].dropna()
            elif country == 'TW':
                valid_sharpe = sharpe_current[sharpe_current.index.isin(tw_tickers)].dropna()
            else:
                us_valid = sharpe_current[sharpe_current.index.isin(us_tickers)].dropna()
                tw_valid = sharpe_current[sharpe_current.index.isin(tw_tickers)].dropna()
                if len(us_valid) > 0 and len(tw_valid) > 0:
                    valid_sharpe = pd.concat([us_valid, tw_valid])
                else:
                    continue
            
            if len(valid_sharpe) >= min(top_n, 5) and growth_current is not None:
                actual_date = date
                sharpe_row = sharpe_current
                growth_row = growth_current
                break
    
    if actual_date is None or sharpe_row is None or growth_row is None:
        return {'date': target_date if target_date else None, 'industries': [], 'top_stocks': [], 'sharpe_top_industries': []}
    
    if country == 'US':
        valid_sharpe = sharpe_row[sharpe_row.index.isin(us_tickers)].dropna()
        valid_growth = growth_row[growth_row.index.isin(us_tickers)].dropna()
    elif country == 'TW':
        valid_sharpe = sharpe_row[sharpe_row.index.isin(tw_tickers)].dropna()
        valid_growth = growth_row[growth_row.index.isin(tw_tickers)].dropna()
    else:
        us_sharpe = sharpe_row[sharpe_row.index.isin(us_tickers)].dropna()
        tw_sharpe = sharpe_row[sharpe_row.index.isin(tw_tickers)].dropna()
        valid_sharpe = pd.concat([us_sharpe, tw_sharpe])
        
        us_growth = growth_row[growth_row.index.isin(us_tickers)].dropna()
        tw_growth = growth_row[growth_row.index.isin(tw_tickers)].dropna()
        valid_growth = pd.concat([us_growth, tw_growth])
    
    if valid_sharpe.empty or valid_growth.empty:
        return {'date': str(actual_date)[:10], 'industries': [], 'top_stocks': [], 'sharpe_top_industries': []}
    
    # 找出 Sharpe Top 15 的產業
    sharpe_top_stocks = valid_sharpe.nlargest(top_n)
    sharpe_top_industries = set()
    
    for ticker in sharpe_top_stocks.index:
        info = container.get_stock_info(ticker)
        industry = info.get('industry', '未分類')
        sharpe_top_industries.add(industry)
    
    # 篩選屬於這些產業的股票
    industry_tickers = set()
    for ticker in valid_growth.index:
        info = container.get_stock_info(ticker)
        industry = info.get('industry', '未分類')
        if industry in sharpe_top_industries:
            industry_tickers.add(ticker)
    
    filtered_growth = valid_growth[valid_growth.index.isin(industry_tickers)]
    
    if filtered_growth.empty:
        return {
            'date': str(actual_date)[:10],
            'industries': [],
            'top_stocks': [],
            'sharpe_top_industries': list(sharpe_top_industries)
        }
    
    growth_top_stocks = filtered_growth.nlargest(top_n)
    
    industry_stats = {}
    top_stock_list = []
    
    for ticker, value in growth_top_stocks.items():
        info = container.get_stock_info(ticker)
        industry = info.get('industry', '未分類')
        stock_country = info.get('country', '')
        
        top_stock_list.append({
            'ticker': ticker,
            'growth': round(value, 6),
            'country': stock_country,
            'industry': industry
        })
        
        if industry not in industry_stats:
            industry_stats[industry] = {
                'total': 0, 'US': 0, 'TW': 0,
                'stocks': [],
                'US_stocks': [],
                'TW_stocks': []
            }
        
        industry_stats[industry]['total'] += 1
        industry_stats[industry]['stocks'].append(ticker)
        
        if stock_country == 'US':
            industry_stats[industry]['US'] += 1
            industry_stats[industry]['US_stocks'].append(ticker)
        elif stock_country == 'TW':
            industry_stats[industry]['TW'] += 1
            industry_stats[industry]['TW_stocks'].append(ticker)
    
    industries = [
        {'name': name, **stats}
        for name, stats in industry_stats.items()
    ]
    industries.sort(key=lambda x: x['total'], reverse=True)
    
    return {
        'date': str(actual_date)[:10],
        'industries': industries,
        'top_stocks': top_stock_list,
        'sharpe_top_industries': list(sharpe_top_industries)
    }
