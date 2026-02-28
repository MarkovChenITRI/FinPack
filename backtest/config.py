"""
回測配置模組

定義回測的預設參數與條件選項，供 run.py 和 main.py 共用

唯一 config 源：所有回測參數預設值只存在此檔案。
透過 load_config() 統一載入、驗證、填補子條件參數。
"""
import copy
import pandas as pd


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
            'description': '回撤超過 N% 則賣出（from_highest=True 從最高點起算）',
            'params': {
                'threshold': {'type': 'float', 'default': 0.40, 'min': 0.05, 'max': 0.80},
                'from_highest': {'type': 'bool', 'default': False}
            }
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
# 預設值（數值型，不含 Money 類型）
# =============================================================================

DEFAULT_CONFIG = {
    'initial_capital': 1_000_000,
    'amount_per_stock': 100_000,
    'max_positions': 10,
    'market': 'us',
    'start_date': '2024-01-01',
    'end_date': None,
    'rebalance_freq': 'weekly',
    'fees': {
        'us': {'rate': 0.003, 'min_fee': 15},
        'tw': {'rate': 0.006, 'min_fee': 0},
    },
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
        'drawdown': {'enabled': True, 'threshold': 0.40, 'from_highest': False},
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
# 例外類別
# =============================================================================

class ConfigError(ValueError):
    """Config 驗證失敗：參數不合法、缺少必填欄位、或型別錯誤"""


# =============================================================================
# 工具：填補子條件參數
# =============================================================================

def _fill_condition_params(result: dict) -> None:
    """
    確保所有已啟用條件的子參數都存在（從 CONDITION_OPTIONS 填入預設值）

    此函數在 merge 後執行，保證 engine 可以用 cond['param'] 直接存取，
    不需要 .get(param, fallback)。
    """
    # buy_conditions
    for cond_name, cond_val in result.get('buy_conditions', {}).items():
        option = CONDITION_OPTIONS['buy_conditions'].get(cond_name)
        if option is None:
            continue
        for param_name, param_spec in option['params'].items():
            if param_name not in cond_val:
                cond_val[param_name] = param_spec['default']

    # sell_conditions
    for cond_name, cond_val in result.get('sell_conditions', {}).items():
        option = CONDITION_OPTIONS['sell_conditions'].get(cond_name)
        if option is None:
            continue
        for param_name, param_spec in option['params'].items():
            if param_name not in cond_val:
                cond_val[param_name] = param_spec['default']

    # rebalance_strategy：依 type 填入對應策略的所有參數
    strategy = result.get('rebalance_strategy', {})
    strategy_type = strategy.get('type')
    if strategy_type:
        option = CONDITION_OPTIONS['rebalance_strategies'].get(strategy_type)
        if option:
            for param_name, param_spec in option['params'].items():
                if param_name not in strategy:
                    strategy[param_name] = param_spec['default']


# =============================================================================
# 主函數：load_config
# =============================================================================

def load_config(user_params: dict = None) -> dict:
    """
    載入並驗證回測配置

    從 DEFAULT_CONFIG 深拷貝預設值，合併使用者參數，填補子條件參數，
    最後驗證所有欄位。任何不合法參數均拋出 ConfigError。

    Args:
        user_params: 使用者提供的參數（可省略任何欄位，缺省使用 DEFAULT_CONFIG 預設值）

    Returns:
        dict: 完整、已驗證的配置

    Raises:
        ConfigError: 參數不合法
    """
    user_params = user_params or {}
    result = copy.deepcopy(DEFAULT_CONFIG)

    # ── 合併簡單值 ──────────────────────────────────────────────────────────
    for key in ['initial_capital', 'amount_per_stock', 'max_positions',
                'market', 'start_date', 'end_date', 'rebalance_freq', 'fees']:
        if key in user_params:
            result[key] = user_params[key]

    # ── 合併巢狀字典 ─────────────────────────────────────────────────────────
    for key in ['buy_conditions', 'sell_conditions', 'rebalance_strategy']:
        if key not in user_params:
            continue
        user = user_params[key]
        default_val = DEFAULT_CONFIG.get(key, {})
        if isinstance(user, dict) and isinstance(default_val, dict):
            for cond_key, cond_val in user.items():
                if cond_key in default_val and isinstance(cond_val, dict):
                    result[key][cond_key] = {**default_val[cond_key], **cond_val}
                else:
                    result[key][cond_key] = cond_val

    # ── 填補子條件參數（保證 engine 無需 .get() 備援）──────────────────────
    _fill_condition_params(result)

    # ── 驗證 ─────────────────────────────────────────────────────────────────
    _validate_config(result)

    return result


def _validate_config(config: dict) -> None:
    """
    驗證配置完整性與合法性。
    任何違規均拋出 ConfigError（不修改 config）。
    """
    # initial_capital
    v = config.get('initial_capital')
    if not isinstance(v, (int, float)) or v <= 0:
        raise ConfigError(f'initial_capital 必須是正數，收到: {v!r}')

    # amount_per_stock
    v = config.get('amount_per_stock')
    if not isinstance(v, (int, float)) or v <= 0:
        raise ConfigError(f'amount_per_stock 必須是正數，收到: {v!r}')

    # max_positions
    v = config.get('max_positions')
    if not isinstance(v, int) or not (1 <= v <= 100):
        raise ConfigError(f'max_positions 必須是 1–100 的整數，收到: {v!r}')

    # market
    v = config.get('market')
    valid_markets = {'us', 'tw', 'global'}
    if v not in valid_markets:
        raise ConfigError(f'market 必須是 {valid_markets} 之一，收到: {v!r}')

    # rebalance_freq
    v = config.get('rebalance_freq')
    valid_freqs = {'daily', 'weekly', 'monthly'}
    if v not in valid_freqs:
        raise ConfigError(f'rebalance_freq 必須是 {valid_freqs} 之一，收到: {v!r}')

    # start_date
    v = config.get('start_date')
    if not isinstance(v, str):
        raise ConfigError(f'start_date 必須是字串，收到: {v!r}')
    try:
        pd.Timestamp(v)
    except Exception:
        raise ConfigError(f'start_date 無法解析為日期: {v!r}')

    # end_date（可為 None）
    v = config.get('end_date')
    if v is not None:
        if not isinstance(v, str):
            raise ConfigError(f'end_date 必須是字串或 None，收到: {v!r}')
        try:
            pd.Timestamp(v)
        except Exception:
            raise ConfigError(f'end_date 無法解析為日期: {v!r}')

    # fees
    fees = config.get('fees')
    if not isinstance(fees, dict):
        raise ConfigError(f'fees 必須是 dict，收到: {fees!r}')
    for market_key in ('us', 'tw'):
        if market_key not in fees:
            raise ConfigError(f'fees 缺少 {market_key!r} 欄位')
        mf = fees[market_key]
        if not isinstance(mf, dict):
            raise ConfigError(f'fees[{market_key!r}] 必須是 dict，收到: {mf!r}')
        rate = mf.get('rate')
        if not isinstance(rate, (int, float)) or not (0 <= rate <= 1):
            raise ConfigError(f'fees[{market_key!r}][rate] 必須在 0–1 之間，收到: {rate!r}')
        min_fee = mf.get('min_fee')
        if not isinstance(min_fee, (int, float)) or min_fee < 0:
            raise ConfigError(f'fees[{market_key!r}][min_fee] 必須 ≥ 0，收到: {min_fee!r}')

    # rebalance_strategy.type
    strategy = config.get('rebalance_strategy', {})
    stype = strategy.get('type')
    valid_types = {'immediate', 'batch', 'delayed', 'concentrated', 'none'}
    if stype not in valid_types:
        raise ConfigError(f'rebalance_strategy.type 必須是 {valid_types} 之一，收到: {stype!r}')


# =============================================================================
# 向後相容別名
# =============================================================================

merge_config = load_config
