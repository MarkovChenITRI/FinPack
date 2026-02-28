"""
回測 API 路由

提供後端回測功能，前端只負責 UI 和參數設定

路由：
- POST /api/backtest/run      執行回測
- GET  /api/backtest/config   取得可用條件選項
"""
import sys
import logging
import pandas as pd
from datetime import datetime
from flask import Blueprint, jsonify, request

from core import container
from core.indicator import Indicators
from core.currency import twd, FX
from core.config import FEES
from backtest import BacktestEngine

logger = logging.getLogger(__name__)

backtest_bp = Blueprint('backtest', __name__)


# =============================================================================
# 條件選項定義（前端下拉選單用）
# =============================================================================

CONDITION_OPTIONS = {
    'buy_conditions': {
        'sharpe_rank': {
            'name': 'Sharpe 排名',
            'description': '買入 Sharpe 排名前 N 名的股票',
            'params': {'top_n': {'type': 'int', 'default': 15, 'min': 1, 'max': 50}},
            'category': 'sharpe'
        },
        'sharpe_threshold': {
            'name': 'Sharpe 門檻',
            'description': '買入 Sharpe 值高於門檻的股票',
            'params': {'threshold': {'type': 'float', 'default': 1.0, 'min': -2, 'max': 5}},
            'category': 'sharpe'
        },
        'sharpe_streak': {
            'name': 'Sharpe 連續達標',
            'description': '連續 N 天在 Sharpe 前 M 名',
            'params': {
                'days': {'type': 'int', 'default': 3, 'min': 1, 'max': 10},
                'top_n': {'type': 'int', 'default': 10, 'min': 1, 'max': 30}
            },
            'category': 'sharpe'
        },
        'growth_rank': {
            'name': 'Growth 排名',
            'description': '買入排名上升最多的前 N 名',
            'params': {'top_n': {'type': 'int', 'default': 7, 'min': 1, 'max': 30}},
            'category': 'growth'
        },
        'growth_streak': {
            'name': 'Growth 連續達標',
            'description': '連續 N 天排名在前 P%',
            'params': {
                'days': {'type': 'int', 'default': 2, 'min': 1, 'max': 10},
                'percentile': {'type': 'int', 'default': 30, 'min': 10, 'max': 100}
            },
            'category': 'growth'
        },
        'sort_sharpe': {
            'name': '依 Sharpe 排序',
            'description': '買入時優先選擇 Sharpe 較高者',
            'params': {},
            'category': 'sort'
        },
        'sort_industry': {
            'name': '依產業分散',
            'description': '每個產業最多買入 N 檔',
            'params': {'per_industry': {'type': 'int', 'default': 2, 'min': 1, 'max': 5}},
            'category': 'sort'
        }
    },
    'sell_conditions': {
        'sharpe_fail': {
            'name': 'Sharpe 失敗',
            'description': '連續 N 期未進入前 K 名則賣出',
            'params': {
                'periods': {'type': 'int', 'default': 2, 'min': 1, 'max': 10},
                'top_n': {'type': 'int', 'default': 15, 'min': 5, 'max': 50}
            }
        },
        'growth_fail': {
            'name': 'Growth 失敗',
            'description': '連續 N 天 Growth 平均為負則賣出',
            'params': {
                'days': {'type': 'int', 'default': 5, 'min': 1, 'max': 20},
                'threshold': {'type': 'float', 'default': 0, 'min': -10, 'max': 10}
            }
        },
        'not_selected': {
            'name': '未被選中',
            'description': '連續 N 期未被選入候選名單則賣出',
            'params': {'periods': {'type': 'int', 'default': 3, 'min': 1, 'max': 10}}
        },
        'drawdown': {
            'name': '回撤止損',
            'description': '從最高點回撤超過 N% 則賣出',
            'params': {'threshold': {'type': 'float', 'default': 0.40, 'min': 0.05, 'max': 0.80}}
        },
        'weakness': {
            'name': '持續弱勢',
            'description': '連續 N 期排名低於 K 名則賣出',
            'params': {
                'rank_k': {'type': 'int', 'default': 20, 'min': 10, 'max': 50},
                'periods': {'type': 'int', 'default': 3, 'min': 1, 'max': 10}
            }
        }
    },
    'rebalance_strategies': {
        'immediate': {
            'name': '立即執行',
            'description': '有買賣訊號立即執行',
            'params': {}
        },
        'batch': {
            'name': '分批進場',
            'description': '每次只投入現金的固定比例',
            'params': {'batch_ratio': {'type': 'float', 'default': 0.20, 'min': 0.05, 'max': 1.0}}
        },
        'delayed': {
            'name': '延遲確認',
            'description': 'Top-N 平均 Sharpe 高於門檻才買入',
            'params': {
                'top_n': {'type': 'int', 'default': 5, 'min': 1, 'max': 20},
                'sharpe_threshold': {'type': 'float', 'default': 0, 'min': -2, 'max': 5}
            }
        },
        'concentrated': {
            'name': '集中投資',
            'description': 'Top-K 領先次群超過門檻才買入',
            'params': {
                'concentrate_top_k': {'type': 'int', 'default': 3, 'min': 1, 'max': 10},
                'lead_margin': {'type': 'float', 'default': 0.30, 'min': 0.0, 'max': 2.0}
            }
        },
        'none': {
            'name': '不再平衡',
            'description': '買入後持有，不主動再平衡',
            'params': {}
        }
    }
}


# =============================================================================
# 預設值
# =============================================================================

DEFAULT_CONFIG = {
    'initial_capital': 1_000_000,
    'amount_per_stock': 100_000,
    'max_positions': 10,
    'market': 'us',
    'backtest_months': 6,
    'rebalance_freq': 'weekly',
    'buy_conditions': {
        'sharpe_rank': {'enabled': True, 'top_n': 15},
        'sharpe_threshold': {'enabled': True, 'threshold': 1.0},
        'sharpe_streak': {'enabled': False, 'days': 3, 'top_n': 10},
        'growth_streak': {'enabled': True, 'days': 2, 'percentile': 30},
        'growth_rank': {'enabled': False, 'top_n': 7},
        'sort_sharpe': {'enabled': True},
        'sort_industry': {'enabled': False, 'per_industry': 2},
    },
    'sell_conditions': {
        'sharpe_fail': {'enabled': True, 'periods': 2, 'top_n': 15},
        'growth_fail': {'enabled': False, 'days': 5, 'threshold': 0},
        'not_selected': {'enabled': False, 'periods': 3},
        'drawdown': {'enabled': True, 'threshold': 0.40},
        'weakness': {'enabled': False, 'rank_k': 20, 'periods': 3},
    },
    'rebalance_strategy': {
        'type': 'delayed',
        'top_n': 5,
        'sharpe_threshold': 0,
        'batch_ratio': 0.20,
        'concentrate_top_k': 3,
        'lead_margin': 0.30,
    }
}


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
def run_backtest():
    """
    執行回測
    
    Request JSON:
    {
        "initial_capital": 1000000,
        "amount_per_stock": 100000,
        "max_positions": 10,
        "market": "us",
        "start_date": "2025-01-01",  // 可選，預設使用 backtest_months
        "end_date": "2025-06-01",    // 可選，預設使用最新日期
        "backtest_months": 6,        // 若無 start_date 則用此計算
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
    try:
        # 立即印出，確認函數被呼叫
        print("\n🔔 [BACKTEST API] run_backtest() 被呼叫!", flush=True)
        
        start_time = datetime.now()
        params = request.json or {}
        
        # ========== 印出前端傳入的參數 ==========
        print("\n" + "="*60, flush=True)
        print("📥 [API] 收到前端回測請求", flush=True)
        print("="*60, flush=True)
        print(f"🔧 基本參數:", flush=True)
        print(f"   初始資金: ${params.get('initial_capital', 1000000):,}", flush=True)
        print(f"   每檔投入: ${params.get('amount_per_stock', 100000):,}", flush=True)
        print(f"   最大持倉: {params.get('max_positions', 10)}", flush=True)
        print(f"   市場: {params.get('market', 'us')}", flush=True)
        print(f"   再平衡頻率: {params.get('rebalance_freq', 'weekly')}", flush=True)
        print(f"   日期範圍: {params.get('start_date')} ~ {params.get('end_date')}", flush=True)
        
        print(f"\n📈 買入條件:", flush=True)
        buy_conds = params.get('buy_conditions', {})
        for key, val in buy_conds.items():
            if val.get('enabled', True):
                print(f"   ✓ {key}: {val}", flush=True)
        
        print(f"\n📉 賣出條件:", flush=True)
        sell_conds = params.get('sell_conditions', {})
        for key, val in sell_conds.items():
            if val.get('enabled', True):
                print(f"   ✓ {key}: {val}", flush=True)
        
        print(f"\n🔄 再平衡策略:", flush=True)
        rebal = params.get('rebalance_strategy', {})
        print(f"   {rebal}", flush=True)
        print("="*60, flush=True)
        
        # 合併預設值
        config = _merge_config(params)
        logger.info(f"回測參數: {config}")
        
        # 檢查資料容器
        if not container.initialized:
            return jsonify({'success': False, 'error': '資料尚未載入完成'}), 503
        
        # 建立收盤價 DataFrame
        close_df = _build_close_df(container.aligned_data)
        if close_df.empty:
            return jsonify({'success': False, 'error': '無可用的股價資料'}), 400
        
        # 市場過濾
        market = config.get('market', 'global')
        if market != 'global':
            close_df, stock_info = _filter_by_market(
                close_df, container.stock_info, market
            )
        else:
            stock_info = container.stock_info
        
        if close_df.empty:
            return jsonify({'success': False, 'error': f'{market} 市場無可用資料'}), 400
        
        # 建立指標計算器
        indicators = Indicators(close_df, stock_info)
        
        # 解析日期
        date_index = close_df.index
        end_date = params.get('end_date')
        start_date = params.get('start_date')
        
        if end_date:
            end_dt = pd.to_datetime(end_date)
            # 確保不超過資料範圍
            if end_dt > date_index[-1]:
                end_dt = date_index[-1]
        else:
            end_dt = date_index[-1]
        
        if start_date:
            start_dt = pd.to_datetime(start_date)
        else:
            months = config.get('backtest_months', 6)
            start_dt = end_dt - pd.DateOffset(months=months)
        
        # 確保不早於資料範圍
        if start_dt < date_index[0]:
            start_dt = date_index[0]
        
        # 準備回測配置（轉換金額為 Money 類型）
        engine_config = {
            'initial_capital': twd(config['initial_capital']),
            'amount_per_stock': twd(config['amount_per_stock']),
            'max_positions': config['max_positions'],
            'rebalance_freq': config['rebalance_freq'],
            'buy_conditions': config['buy_conditions'],
            'sell_conditions': config['sell_conditions'],
            'rebalance_strategy': config['rebalance_strategy'],
        }
        
        # 匯率服務
        fx = container.fx or FX(use_cache=True)
        
        # 執行回測
        print(f"\n🚀 [RUN] 執行回測: {start_dt.date()} ~ {end_dt.date()}", flush=True)
        logger.info(f"執行回測: {start_dt.date()} ~ {end_dt.date()}")
        engine = BacktestEngine(close_df, indicators, stock_info, engine_config, fx)
        result = engine.run(start_date=start_dt, end_date=end_dt)
        
        # 取得當前持倉
        current_holdings = _get_current_holdings(
            engine, close_df, stock_info, fx, end_dt
        )
        
        # 計算 benchmark 曲線（使用策略的日期來對齊）
        trading_dates = [p['date'] for p in result.equity_curve]
        benchmark_curve, benchmark_name = _calculate_benchmark_curve(
            container, market, trading_dates, config['initial_capital']
        )
        
        elapsed = (datetime.now() - start_time).total_seconds()
        
        # ========== 印出回測結果 ==========
        print("\n" + "="*60, flush=True)
        print("📊 [RESULT] 回測結果", flush=True)
        print("="*60, flush=True)
        print(f"💰 績效指標:", flush=True)
        print(f"   初始資金: ${result.initial_capital.amount:,.0f}", flush=True)
        print(f"   最終權益: ${result.final_equity.amount:,.0f}", flush=True)
        print(f"   總報酬率: {result.total_return * 100:.2f}%", flush=True)
        print(f"   年化報酬: {result.annualized_return * 100:.2f}%", flush=True)
        print(f"   最大回撤: {result.max_drawdown * 100:.2f}%", flush=True)
        print(f"   夏普比率: {result.sharpe_ratio:.2f}", flush=True)
        print(f"\n📈 交易統計:", flush=True)
        print(f"   總交易數: {result.total_trades}", flush=True)
        print(f"   獲利交易: {result.win_trades}", flush=True)
        print(f"   虧損交易: {result.loss_trades}", flush=True)
        print(f"   勝率: {result.win_rate * 100:.1f}%", flush=True)
        print(f"\n💼 當前持倉: {len(current_holdings)} 檔", flush=True)
        for h in current_holdings[:5]:  # 只顯示前5檔
            print(f"   {h['symbol']}: {h['shares']}股 @ ${h['current_price']:.2f} (損益: {h['pnl_pct']:.1f}%)", flush=True)
        if len(current_holdings) > 5:
            print(f"   ... 等共 {len(current_holdings)} 檔", flush=True)
        print(f"\n⏱️  執行時間: {elapsed:.2f} 秒", flush=True)
        print("="*60 + "\n", flush=True)
        
        # 格式化回應
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
                    'start': start_dt.strftime('%Y-%m-%d'),
                    'end': end_dt.strftime('%Y-%m-%d'),
                    'trading_days': len(result.equity_curve)
                },
                'elapsed_seconds': round(elapsed, 2)
            }
        }
        
        return jsonify(response)
    
    except Exception as e:
        logger.exception("回測執行失敗")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


# =============================================================================
# 輔助函數
# =============================================================================

def _merge_config(params: dict) -> dict:
    """合併使用者參數與預設值"""
    config = DEFAULT_CONFIG.copy()
    
    # 基本參數
    for key in ['initial_capital', 'amount_per_stock', 'max_positions', 
                'market', 'backtest_months', 'rebalance_freq']:
        if key in params:
            config[key] = params[key]
    
    # 買入條件（深度合併）
    if 'buy_conditions' in params:
        config['buy_conditions'] = _merge_conditions(
            DEFAULT_CONFIG['buy_conditions'], 
            params['buy_conditions']
        )
    
    # 賣出條件
    if 'sell_conditions' in params:
        config['sell_conditions'] = _merge_conditions(
            DEFAULT_CONFIG['sell_conditions'],
            params['sell_conditions']
        )
    
    # 再平衡策略
    if 'rebalance_strategy' in params:
        config['rebalance_strategy'] = {
            **DEFAULT_CONFIG['rebalance_strategy'],
            **params['rebalance_strategy']
        }
    
    return config


def _merge_conditions(defaults: dict, user: dict) -> dict:
    """合併條件設定（保留預設的 enabled 狀態，更新參數）"""
    result = {}
    for key, default_val in defaults.items():
        if key in user:
            result[key] = {**default_val, **user[key]}
        else:
            result[key] = default_val.copy()
    return result


def _build_close_df(aligned_data: dict) -> pd.DataFrame:
    """從對齊資料建立收盤價 DataFrame"""
    close_dict = {}
    for ticker, df in aligned_data.items():
        if 'Close' in df.columns:
            close_dict[ticker] = df['Close']
    
    if not close_dict:
        return pd.DataFrame()
    
    return pd.DataFrame(close_dict).sort_index()


def _filter_by_market(close_df: pd.DataFrame, stock_info: dict, market: str):
    """依市場過濾"""
    country_map = {'us': 'US', 'tw': 'TW'}
    target_country = country_map.get(market)
    
    if not target_country:
        return close_df, stock_info
    
    filtered_tickers = [
        t for t in close_df.columns
        if stock_info.get(t, {}).get('country') == target_country
    ]
    
    filtered_info = {
        t: info for t, info in stock_info.items()
        if info.get('country') == target_country
    }
    
    return close_df[filtered_tickers], filtered_info


def _calculate_benchmark_curve(container, market: str, trading_dates: list, initial_capital: float) -> tuple:
    """
    計算 benchmark 權益曲線（考慮匯率）
    
    使用策略的交易日期來取 benchmark 價格，確保 x 軸對齊。
    初始資金為 TWD，所以 US 市場需要考慮匯率變動。
    
    計算邏輯（以 TWD 計價）：
    - us: 初始資金換成 USD 買 NASDAQ，每天用當天匯率換回 TWD
    - tw: 初始資金直接買 TWII，無匯率問題
    - global: 50% 買 NASDAQ（含匯率）+ 50% 買 TWII
    
    Args:
        container: 資料容器
        market: 'us' | 'tw' | 'global'
        trading_dates: 策略的交易日期列表（用於對齊）
        initial_capital: 初始資金（TWD）
        
    Returns:
        (benchmark_curve, benchmark_name): 權益曲線 list 與指數名稱
    """
    if not trading_dates:
        return [], ''
    
    fx = container.fx or FX(use_cache=True)
    
    if market == 'global':
        # 國際加權指數 = 50% NASDAQ + 50% TWII
        name = '國際加權指數'
        nasdaq_data = container.market_loader.get_weighted_kline('^IXIC', '6y', container.aligned_data)
        twii_data = container.market_loader.get_weighted_kline('^TWII', '6y', container.aligned_data)
        
        if not nasdaq_data or not twii_data:
            print(f"⚠️ [BENCHMARK] 找不到 {name} 指數資料", flush=True)
            return [], name
        
        nasdaq_map = {d['time']: d['close'] for d in nasdaq_data}
        twii_map = {d['time']: d['close'] for d in twii_data}
        
        benchmark_curve = []
        first_nasdaq = None
        first_twii = None
        first_fx = None
        
        for date in trading_dates:
            nasdaq_price = nasdaq_map.get(date)
            twii_price = twii_map.get(date)
            if nasdaq_price and twii_price:
                current_fx = fx.rate(date)
                if first_nasdaq is None:
                    first_nasdaq = nasdaq_price
                    first_twii = twii_price
                    first_fx = current_fx
                
                # 50% 投資 NASDAQ（含匯率變動）+ 50% 投資 TWII
                us_equity = 0.5 * initial_capital * (nasdaq_price / first_nasdaq) * (current_fx / first_fx)
                tw_equity = 0.5 * initial_capital * (twii_price / first_twii)
                total_equity = us_equity + tw_equity
                
                benchmark_curve.append({
                    'date': date,
                    'equity': round(total_equity, 2)
                })
                
    elif market == 'tw':
        # 台灣加權指數（無匯率問題）
        name = '台灣加權指數'
        kline_data = container.market_loader.get_weighted_kline('^TWII', '6y', container.aligned_data)
        
        if not kline_data:
            print(f"⚠️ [BENCHMARK] 找不到 {name} 指數資料", flush=True)
            return [], name
        
        price_map = {d['time']: d['close'] for d in kline_data}
        benchmark_curve = []
        first_price = None
        
        for date in trading_dates:
            price = price_map.get(date)
            if price:
                if first_price is None:
                    first_price = price
                equity = initial_capital * (price / first_price)
                benchmark_curve.append({
                    'date': date,
                    'equity': round(equity, 2)
                })
                
    else:  # us
        # NASDAQ（需考慮匯率：TWD → USD → 買指數 → 賣指數 → TWD）
        name = 'NASDAQ'
        kline_data = container.market_loader.get_weighted_kline('^IXIC', '6y', container.aligned_data)
        
        if not kline_data:
            print(f"⚠️ [BENCHMARK] 找不到 {name} 指數資料", flush=True)
            return [], name
        
        price_map = {d['time']: d['close'] for d in kline_data}
        benchmark_curve = []
        first_price = None
        first_fx = None
        
        for date in trading_dates:
            price = price_map.get(date)
            if price:
                current_fx = fx.rate(date)
                if first_price is None:
                    first_price = price
                    first_fx = current_fx
                
                # 權益 = 初始資金 * (指數漲幅) * (匯率變動)
                # 匯率上升(TWD貶值) → 換回 TWD 更多
                equity = initial_capital * (price / first_price) * (current_fx / first_fx)
                benchmark_curve.append({
                    'date': date,
                    'equity': round(equity, 2)
                })
    
    print(f"✅ [BENCHMARK] {name} 曲線計算完成: {len(benchmark_curve)} 筆", flush=True)
    return benchmark_curve, name


def _get_current_holdings(engine, close_df, stock_info, fx, end_dt):
    """取得當前持倉詳情"""
    from core.currency import twd, usd
    
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
