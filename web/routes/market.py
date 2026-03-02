"""
市場數據 API 路由（BTC-USD 版）

路由：
- GET /api/kline/btc       BTC-USD K 線數據
- GET /api/market-status   市場狀態（最新 BTC 收盤）
- GET /api/btc/signals     SMC 預計算信號（JSON）
"""
import logging
from datetime import datetime
from flask import Blueprint, jsonify, request

from core import container, smc_service
from core.data import fetch_btc_ohlcv

logger = logging.getLogger(__name__)

market_bp = Blueprint('market', __name__)

PERIOD_DAYS = {
    '1mo': 30, '3mo': 90, '6mo': 180,
    '1y': 365, '2y': 730, '5y': 1825,
}


@market_bp.route('/kline/btc')
def get_btc_kline():
    """
    API: 取得 BTC-USD K 線數據

    Query Parameters:
        period:    '1mo' | '3mo' | '6mo' | '1y' | '2y' | '5y'
        timeframe: '1d' | '4h' | '1h'（預設 1d）
    """
    period    = request.args.get('period', '1y')
    timeframe = request.args.get('timeframe', '1d')

    try:
        df = container.get_ohlcv(timeframe)

        # 根據 period 裁切
        if period in PERIOD_DAYS:
            from datetime import timedelta
            cutoff = datetime.now() - timedelta(days=PERIOD_DAYS[period])
            import pandas as pd
            df = df[df.index >= pd.Timestamp(cutoff)]

        kline = [
            {
                'time':   str(idx)[:10],
                'open':   round(float(row['Open']), 2),
                'high':   round(float(row['High']), 2),
                'low':    round(float(row['Low']), 2),
                'close':  round(float(row['Close']), 2),
                'volume': int(row['Volume']) if row['Volume'] == row['Volume'] else 0,
            }
            for idx, row in df.iterrows()
        ]

        return jsonify({
            'symbol':    'BTC-USD',
            'timeframe': timeframe,
            'period':    period,
            'data':      kline,
            'count':     len(kline),
        })

    except Exception as e:
        logger.error('[API] /kline/btc 失敗: %s', e)
        return jsonify({'error': str(e), 'data': []}), 500


@market_bp.route('/market-status')
def get_market_status():
    """API: BTC-USD 市場狀態"""
    try:
        latest_close = container.latest_close
        return jsonify({
            'symbol':       'BTC-USD',
            'latest_close': round(latest_close, 2),
            'today':        datetime.now().strftime('%Y-%m-%d'),
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@market_bp.route('/btc/signals')
def get_btc_signals():
    """
    API: 取得 BTC-USD 預計算 SMC 信號

    Query Parameters:
        timeframe: '1d' | '4h' | '1h'（預設 1d）

    若指定 timeframe 尚未預計算，嘗試即時計算。
    """
    timeframe = request.args.get('timeframe', '1d')
    if timeframe not in ('1d', '4h', '1h'):
        return jsonify({'error': f'unsupported timeframe: {timeframe}'}), 400

    # 已快取則直接回傳
    if smc_service.is_ready(timeframe):
        return jsonify(smc_service.get_signals(timeframe))

    # 即時計算（4h/1h 首次請求時）
    ohlcv = container.get_ohlcv(timeframe)
    if ohlcv.empty:
        return jsonify({'error': f'無法取得 {timeframe} 資料'}), 503

    try:
        smc_service.precompute(ohlcv, timeframe)
        return jsonify(smc_service.get_signals(timeframe))
    except Exception as e:
        logger.exception('[API] /btc/signals 計算失敗')
        return jsonify({'error': str(e)}), 500
