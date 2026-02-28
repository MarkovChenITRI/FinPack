"""
回測 API 路由

提供後端回測功能，前端只負責 UI 和參數設定

路由：
- POST /api/backtest/run      執行回測
- GET  /api/backtest/config   取得可用條件選項
"""
import logging
from flask import Blueprint, jsonify, request

from core.currency import usd

from backtest.config import CONDITION_OPTIONS, DEFAULT_CONFIG, load_config, ConfigError
from backtest.runner import run_backtest

logger = logging.getLogger(__name__)

backtest_bp = Blueprint('backtest', __name__)


# =============================================================================
# API 路由
# =============================================================================

@backtest_bp.route('/backtest/config')
def get_backtest_config():
    """取得可用的回測條件選項"""
    return jsonify({
        'options': CONDITION_OPTIONS,
        'defaults': DEFAULT_CONFIG
    })


@backtest_bp.route('/backtest/run', methods=['POST'])
def run_backtest_route():
    """
    執行回測

    Request JSON:
    {
        "initial_capital": 1000000,
        "amount_per_stock": 100000,
        "max_positions": 10,
        "market": "us",
        "start_date": "2020-01-01",  // 固定起始日（必填）
        "end_date": null,            // 結束日（null = 系統今日最近交易日）
        "rebalance_freq": "weekly",
        "buy_conditions": {...},
        "sell_conditions": {...},
        "rebalance_strategy": {...}
    }

    Response:
    {
        "success": true,
        "result": {
            "metrics": {...},
            "equity_curve": [...],
            "trades": [...],
            "current_holdings": [...]
        }
    }
    """
    logger.info('[API] run_backtest() 被呼叫')

    # 1. 載入並驗證配置（ConfigError → 400）
    try:
        config = load_config(request.json or {})
    except ConfigError as e:
        return jsonify({'success': False, 'error': str(e)}), 400

    logger.info('[API] 收到前端回測請求: market=%s, start=%s, end=%s, rebalance=%s',
                config['market'], config['start_date'], config['end_date'], config['rebalance_freq'])

    # 2. 執行共用 pipeline
    try:
        ctx = run_backtest(config, source='API')
    except RuntimeError as e:
        status = 503 if '尚未載入' in str(e) else 400
        return jsonify({'success': False, 'error': str(e)}), status
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception:
        logger.exception('回測執行失敗')
        return jsonify({'success': False, 'error': '回測執行失敗，請查看伺服器日誌'}), 500

    result = ctx['result']
    engine = ctx['engine']
    close_df = ctx['close_df']
    stock_info = ctx['stock_info']
    end_dt = ctx['end_dt']
    elapsed = ctx['elapsed']
    benchmark_curve = ctx['benchmark_curve']
    benchmark_name = ctx['benchmark_name']

    # 3. 建立當前持倉（API 特有格式，純數值供 JSON 序列化）
    from core import container
    current_holdings = _get_current_holdings(
        engine, close_df, stock_info, container.fx, end_dt
    )

    # 4. 格式化 JSON 回應
    response = {
        'success': True,
        'result': {
            'metrics': {
                'initial_capital': result.initial_capital.amount,
                'final_equity': result.final_equity.amount,
                'total_return': round(result.total_return * 100, 2),
                'annualized_return': round(result.annualized_return * 100, 2),
                'total_trades': result.total_trades,
                'win_trades': result.win_trades,
                'loss_trades': result.loss_trades,
                'win_rate': round(result.win_rate * 100, 2),
                'max_drawdown': round(result.max_drawdown * 100, 2),
                'sharpe_ratio': round(result.sharpe_ratio, 2),
            },
            'equity_curve': result.equity_curve,
            'benchmark_curve': benchmark_curve,
            'benchmark_name': benchmark_name,
            'trades': result.trades,  # 已經是 dict list
            'current_holdings': current_holdings,
            'cash': engine.cash.amount,
            'date_range': {
                'start': ctx['start_dt'].strftime('%Y-%m-%d'),
                'end': end_dt.strftime('%Y-%m-%d'),
                'trading_days': len(result.equity_curve)
            },
            'elapsed_seconds': round(elapsed, 2)
        }
    }

    return jsonify(response)


# =============================================================================
# 輔助函數
# =============================================================================

def _get_current_holdings(engine, close_df, stock_info, fx, end_dt):
    """取得當前持倉詳情（純數值，供 JSON 序列化）"""
    date_index = close_df.index
    actual_end_idx = date_index.searchsorted(end_dt, side='right') - 1
    end_date_str = close_df.index[actual_end_idx].strftime('%Y-%m-%d')

    holdings = []
    for symbol, pos in engine.positions.items():
        country = stock_info.get(symbol, {}).get('country', 'US')
        current_price = close_df.iloc[actual_end_idx].get(symbol, pos.avg_cost.amount)

        # 計算市值
        if country == 'TW':
            market_value = pos.shares * current_price
        else:
            market_value = fx.to_twd(usd(pos.shares * current_price), end_date_str).amount

        # 計算損益
        cost_in_twd = pos.cost_basis.amount
        pnl_pct = (market_value - cost_in_twd) / cost_in_twd if cost_in_twd > 0 else 0

        holdings.append({
            'symbol': symbol,
            'shares': pos.shares,
            'avg_cost': pos.avg_cost.amount,
            'avg_cost_currency': pos.avg_cost.currency.name,
            'current_price': current_price,
            'market_value': round(market_value, 0),
            'pnl_pct': round(pnl_pct * 100, 2),
            'buy_date': pos.buy_date,
            'industry': stock_info.get(symbol, {}).get('industry', 'Unknown'),
            'country': country,
        })

    holdings.sort(key=lambda x: x['buy_date'], reverse=True)
    return holdings
