"""
SMC 回測 API 路由（BTC-USD 版）

路由：
- POST /api/backtest/run     執行 BTC-USD SMC 策略回測
- GET  /api/backtest/config  取得可用條件選項與預設值
"""
import logging
import time
import pandas as pd
from flask import Blueprint, jsonify, request

from core import container
from backtest.smc_config import SMC_CONDITION_OPTIONS, DEFAULT_SMC_CONFIG, load_smc_config, SmcConfigError
from backtest.smc_engine import SmcEngine

logger = logging.getLogger(__name__)

backtest_bp = Blueprint('backtest', __name__)


@backtest_bp.route('/backtest/config')
def get_backtest_config():
    """取得 SMC 可用條件選項與預設值"""
    logger.info('[API] GET /backtest/config')
    return jsonify({
        'options':  SMC_CONDITION_OPTIONS,
        'defaults': DEFAULT_SMC_CONFIG,
    })


@backtest_bp.route('/backtest/run', methods=['POST'])
def run_backtest_route():
    """
    執行 BTC-USD SMC 策略回測

    Request JSON（所有欄位可省略，缺省使用 DEFAULT_SMC_CONFIG）：
    {
        "initial_capital": 10000,
        "leverage":        1,
        "risk_per_trade":  0.02,
        "timeframe":       "1d",
        "start_date":      "2022-01-01",
        "end_date":        null,
        "allow_long":      true,
        "allow_short":     false,
        "entry_conditions": {...},
        "exit_conditions":  {...}
    }
    """
    t0 = time.perf_counter()
    raw = request.json or {}
    logger.info(
        '[API] POST /backtest/run | capital=%.0f leverage=%sx tf=%s %s~%s long=%s short=%s',
        raw.get('initial_capital', DEFAULT_SMC_CONFIG['initial_capital']),
        raw.get('leverage',        DEFAULT_SMC_CONFIG['leverage']),
        raw.get('timeframe',       DEFAULT_SMC_CONFIG['timeframe']),
        raw.get('start_date',      DEFAULT_SMC_CONFIG['start_date']),
        raw.get('end_date')        or 'latest',
        raw.get('allow_long',      DEFAULT_SMC_CONFIG['allow_long']),
        raw.get('allow_short',     DEFAULT_SMC_CONFIG['allow_short']),
    )

    # 1. 解析與驗證配置（唯一來源：DEFAULT_SMC_CONFIG 合併使用者覆蓋）
    try:
        config = load_smc_config(raw)
    except SmcConfigError as e:
        logger.warning('[API] 配置驗證失敗: %s', e)
        return jsonify({'success': False, 'error': str(e)}), 400

    # 2. 取得 OHLCV 資料
    timeframe = config['timeframe']
    ohlcv = container.get_ohlcv(timeframe)
    if ohlcv.empty:
        logger.error('[API] 無法取得 %s OHLCV', timeframe)
        return jsonify({'success': False, 'error': f'無法取得 BTC-USD {timeframe} 資料'}), 503

    logger.info('[API] 使用 %s OHLCV，共 %d 根K線', timeframe, len(ohlcv))

    # 3. 執行回測（後端引擎）
    try:
        engine = SmcEngine(ohlcv, config)
        result = engine.run(
            start_date = config['start_date'],
            end_date   = config.get('end_date'),
        )
    except Exception as e:
        logger.exception('[API] SMC 回測引擎異常')
        return jsonify({'success': False, 'error': str(e)}), 500

    # 4. BTC Buy & Hold 基準
    start_ts = min(
        ohlcv.index.searchsorted(pd.Timestamp(config['start_date'])),
        len(ohlcv) - 1
    )
    bh_start  = float(ohlcv['Close'].iloc[start_ts])
    bh_end    = float(ohlcv['Close'].iloc[-1])
    bh_return = (bh_end - bh_start) / bh_start

    metrics = result.to_dict()
    metrics['benchmark_return']     = f"{bh_return:.2%}"
    metrics['benchmark_return_raw'] = bh_return
    metrics['alpha']                = f"{result.total_return - bh_return:+.2%}"

    elapsed = time.perf_counter() - t0
    logger.info(
        '[API] 回測完成 | 耗時=%.2fs 交易=%d 勝率=%s 報酬=%s alpha=%s',
        elapsed,
        result.total_trades,
        f"{result.win_rate:.1%}",
        f"{result.total_return:.2%}",
        metrics['alpha'],
    )

    return jsonify({
        'success': True,
        'result': {
            'metrics':      metrics,
            'equity_curve': result.equity_curve,
            'trades':       result.trades,
        }
    })
