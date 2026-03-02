"""
SMC 策略回測配置模組

定義 BTC-USD Smart Money Concepts 策略的預設參數與驗證邏輯。
唯一 config 源：所有 SMC 策略參數預設值只存在此檔案。
"""
import copy
import pandas as pd


# =============================================================================
# 條件選項說明（供 CLI / Web 呈現用）
# =============================================================================

SMC_CONDITION_OPTIONS = {
    'entry': {
        'require_bias': {
            'name': '結構方向過濾',
            'description': '只在符合市場偏向時進場（bullish 做多 / bearish 做空）',
        },
        'require_discount': {
            'name': '折扣/溢價區過濾',
            'description': '做多只在折扣區（< 50%），做空只在溢價區（> 50%）',
        },
        'require_fvg': {
            'name': 'FVG 觸發',
            'description': '價格進入未填補的 FVG 才允許進場',
        },
        'require_ob': {
            'name': 'Order Block 觸發',
            'description': '價格進入有效 OB 才允許進場（優先於 FVG）',
        },
    },
    'exit': {
        'stop_loss_pct': {
            'name': '固定止損百分比',
            'description': '進場後跌破 OB 低點的額外緩衝，例如 0.02 = 2%',
        },
        'take_profit_liquidity': {
            'name': '流動性池止盈',
            'description': '到達最近 buy-side/sell-side 流動性池時止盈',
        },
        'structure_exit': {
            'name': '結構翻轉出場',
            'description': '出現反向 CHOCH 時強制平倉',
        },
        'max_holding_bars': {
            'name': '最大持倉 K 線數',
            'description': '超過此根數仍未出場則強制平倉',
        },
    },
}


# =============================================================================
# 預設值
# =============================================================================

DEFAULT_SMC_CONFIG = {
    # ── 資金管理 ────────────────────────────────────────────────────────────
    'initial_capital': 10_000,        # USD
    'risk_per_trade':  0.02,          # 每筆交易風險 = 總資金的 2%
    'leverage':        1,             # 槓桿倍數（1 = 無槓桿現貨）

    # ── 交易對 & 時間框架 ────────────────────────────────────────────────────
    'symbol':    'BTC-USD',
    'timeframe': '1d',                # '1d' | '4h' | '1h'
    'start_date': '2022-01-01',
    'end_date':   None,               # None = 最後可用日期

    # ── 允許方向 ─────────────────────────────────────────────────────────────
    'allow_long':  True,
    'allow_short': False,             # 預設只做多（現貨）

    # ── SMC 指標參數 ─────────────────────────────────────────────────────────
    'pivot_lookback':     5,          # Pivot 左右確認根數
    'fvg_min_size_atr':   0.1,        # FVG 最小尺寸（ATR 倍數）
    'displacement_atr':   1.5,        # 位移 K 線最小實體（ATR 倍數）
    'lp_tolerance_pct':   0.002,      # 流動性池容忍度（0.2%）

    # ── 進場條件（所有啟用的條件必須同時滿足）────────────────────────────
    'entry_conditions': {
        'require_bias':     {'enabled': True},
        'require_discount': {'enabled': True},
        'require_fvg':      {'enabled': True},
        'require_ob':       {'enabled': True},   # OB 優先，若無 OB 則看 FVG
    },

    # ── 出場條件 ──────────────────────────────────────────────────────────────
    'exit_conditions': {
        'stop_loss_pct':         {'enabled': True,  'pct': 0.02},
        'take_profit_liquidity': {'enabled': True},
        'structure_exit':        {'enabled': True},
        'max_holding_bars':      {'enabled': True,  'bars': 30},
    },

    # ── 手續費 ───────────────────────────────────────────────────────────────
    'fee_rate': 0.001,   # 0.1% per trade
}


# =============================================================================
# 例外類別
# =============================================================================

class SmcConfigError(ValueError):
    """SMC Config 驗證失敗"""


# =============================================================================
# 主函數
# =============================================================================

def load_smc_config(user_params: dict = None) -> dict:
    """
    載入並驗證 SMC 回測配置

    Args:
        user_params: 使用者覆蓋參數（可省略，缺省使用 DEFAULT_SMC_CONFIG）

    Returns:
        完整已驗證配置 dict

    Raises:
        SmcConfigError: 參數不合法
    """
    user_params = user_params or {}
    result      = copy.deepcopy(DEFAULT_SMC_CONFIG)

    # 合併頂層簡單值
    for key in [
        'initial_capital', 'risk_per_trade', 'leverage', 'symbol', 'timeframe',
        'start_date', 'end_date', 'allow_long', 'allow_short',
        'pivot_lookback', 'fvg_min_size_atr', 'displacement_atr',
        'lp_tolerance_pct', 'fee_rate',
    ]:
        if key in user_params:
            result[key] = user_params[key]

    # 合併巢狀條件
    for key in ['entry_conditions', 'exit_conditions']:
        if key in user_params and isinstance(user_params[key], dict):
            for cond_key, cond_val in user_params[key].items():
                if cond_key in result[key] and isinstance(cond_val, dict):
                    result[key][cond_key] = {**result[key][cond_key], **cond_val}
                else:
                    result[key][cond_key] = cond_val

    _validate_smc_config(result)
    return result


def _validate_smc_config(cfg: dict) -> None:
    """驗證 SMC 配置合法性"""
    v = cfg.get('initial_capital')
    if not isinstance(v, (int, float)) or v <= 0:
        raise SmcConfigError(f'initial_capital 必須是正數，收到: {v!r}')

    v = cfg.get('leverage', 1)
    if not isinstance(v, (int, float)) or not (1 <= v <= 125):
        raise SmcConfigError(f'leverage 必須在 [1, 125] 之間，收到: {v!r}')

    v = cfg.get('risk_per_trade')
    if not isinstance(v, (int, float)) or not (0 < v <= 1):
        raise SmcConfigError(f'risk_per_trade 必須在 (0, 1] 之間，收到: {v!r}')

    v = cfg.get('timeframe')
    if v not in ('1d', '4h', '1h'):
        raise SmcConfigError(f"timeframe 必須是 '1d'|'4h'|'1h'，收到: {v!r}")

    v = cfg.get('start_date')
    try:
        pd.Timestamp(v)
    except Exception:
        raise SmcConfigError(f'start_date 無法解析: {v!r}')

    v = cfg.get('end_date')
    if v is not None:
        try:
            pd.Timestamp(v)
        except Exception:
            raise SmcConfigError(f'end_date 無法解析: {v!r}')

    v = cfg.get('fee_rate')
    if not isinstance(v, (int, float)) or not (0 <= v < 1):
        raise SmcConfigError(f'fee_rate 必須在 [0, 1) 之間，收到: {v!r}')

    if not cfg.get('allow_long') and not cfg.get('allow_short'):
        raise SmcConfigError('allow_long 和 allow_short 不能同時為 False')
