"""
回測配置模組

定義回測的預設參數與條件選項，供 run.py 和 main.py 共用
"""

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
# 預設值（數值型，不含 Money 類型）
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


def merge_config(user_params: dict) -> dict:
    """
    合併使用者參數與預設值
    
    Args:
        user_params: 使用者提供的參數
        
    Returns:
        dict: 合併後的完整配置
    """
    import copy
    result = copy.deepcopy(DEFAULT_CONFIG)
    
    # 簡單值直接覆蓋
    for key in ['initial_capital', 'amount_per_stock', 'max_positions', 
                'market', 'backtest_months', 'rebalance_freq',
                'start_date', 'end_date']:
        if key in user_params:
            result[key] = user_params[key]
    
    # 巢狀字典合併
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
    
    return result
