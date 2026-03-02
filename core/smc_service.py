"""
SMC 信號預計算服務

在伺服器啟動時，對 BTC-USD 歷史資料一次性計算所有 SMC 指標，
並序列化為前端可直接使用的 JSON 格式，快取在記憶體中。

用法：
    from core.smc_service import smc_service
    smc_service.precompute(ohlcv_1d, timeframe='1d')
    signals = smc_service.get_signals('1d')
"""
import logging
import numpy as np
import pandas as pd

from core.smc import SmcIndicators

logger = logging.getLogger(__name__)


class SmcSignalService:
    """SMC 信號預計算服務（單例使用）"""

    def __init__(self):
        # 各 timeframe 的序列化信號快取
        self._cache: dict[str, dict] = {}
        # SmcIndicators 實例快取（供回測引擎直接使用）
        self._indicators: dict[str, SmcIndicators] = {}

    def precompute(self, ohlcv: pd.DataFrame, timeframe: str = '1d') -> None:
        """
        預計算指定 timeframe 的所有 SMC 信號並序列化快取。

        Args:
            ohlcv:     BTC-USD OHLCV DataFrame（DatetimeIndex）
            timeframe: '1d' | '4h' | '1h'
        """
        if ohlcv.empty:
            logger.warning('[SMC Service] ohlcv 為空，略過 %s 預計算', timeframe)
            return

        logger.info('[SMC Service] 開始預計算 %s SMC 信號（共 %d 根K線）...', timeframe, len(ohlcv))

        indicators = SmcIndicators(ohlcv)
        self._indicators[timeframe] = indicators

        # 觸發全量計算（lazy property 強制求值）
        _ = indicators.pivots
        _ = indicators.structure
        _ = indicators.fvgs
        _ = indicators.order_blocks
        _ = indicators.liquidity_pools

        # 序列化為前端格式
        signals = self._serialize(indicators, ohlcv)
        self._cache[timeframe] = signals

        logger.info(
            '[SMC Service] %s 預計算完成：BOS/CHOCH=%d, FVG=%d, OB=%d, LP=%d',
            timeframe,
            len(signals['bos']) + len(signals['choch']),
            len(signals['fvgs']),
            len(signals['order_blocks']),
            len(signals['liquidity_pools']),
        )

    def get_signals(self, timeframe: str = '1d') -> dict:
        """
        取得指定 timeframe 的序列化 SMC 信號。

        Returns:
            dict with keys: bos, choch, fvgs, order_blocks, liquidity_pools
            若尚未預計算則回傳空結構。
        """
        return self._cache.get(timeframe, self._empty_signals())

    def get_indicators(self, timeframe: str = '1d') -> SmcIndicators | None:
        """取得 SmcIndicators 實例（供回測引擎使用）"""
        return self._indicators.get(timeframe)

    def is_ready(self, timeframe: str = '1d') -> bool:
        return timeframe in self._cache

    # ------------------------------------------------------------------
    # 序列化工具
    # ------------------------------------------------------------------

    def _serialize(self, indicators: SmcIndicators, ohlcv: pd.DataFrame) -> dict:
        """將 SmcIndicators 的計算結果序列化為前端 JSON 格式"""
        bos_list   = []
        choch_list = []

        for sp in indicators.structure:
            record = {
                'time':      sp.date,
                'price':     round(sp.broken_level, 2),
                'close':     round(sp.close, 2),
                'direction': 'bullish' if 'bullish' in sp.event else 'bearish',
            }
            if 'choch' in sp.event:
                choch_list.append(record)
            else:
                bos_list.append(record)

        fvg_list = []
        for fvg in indicators.fvgs:
            fvg_list.append({
                'time':      fvg.date,
                'top':       round(fvg.top, 2),
                'bottom':    round(fvg.bottom, 2),
                'mid':       round(fvg.mid, 2),
                'type':      fvg.direction,   # 'bullish' | 'bearish'
                'filled':    fvg.filled,
            })

        ob_list = []
        for ob in indicators.order_blocks:
            ob_list.append({
                'time':        ob.date,
                'top':         round(ob.top, 2),
                'bottom':      round(ob.bottom, 2),
                'body_top':    round(ob.body_top, 2),
                'body_bottom': round(ob.body_bottom, 2),
                'type':        ob.direction,   # 'bullish' | 'bearish'
                'valid':       ob.valid,
            })

        lp_list = []
        for lp in indicators.liquidity_pools:
            lp_list.append({
                'time':        lp.date,
                'price':       round(lp.level, 2),
                'type':        lp.direction,   # 'buy_side' | 'sell_side'
                'touch_count': lp.count,
                'swept':       lp.swept,
            })

        # 最後一根 K 線的偏向（供前端顯示）
        last_idx = len(ohlcv) - 1
        final_bias = indicators.get_current_bias(last_idx)
        sl, sh = indicators.get_swing_range(last_idx)

        return {
            'bos':             bos_list,
            'choch':           choch_list,
            'fvgs':            fvg_list,
            'order_blocks':    ob_list,
            'liquidity_pools': lp_list,
            'summary': {
                'bias':        final_bias,
                'swing_high':  round(sh, 2) if not np.isnan(sh) else None,
                'swing_low':   round(sl, 2) if not np.isnan(sl) else None,
                'total_bars':  len(ohlcv),
            },
        }

    @staticmethod
    def _empty_signals() -> dict:
        return {
            'bos':             [],
            'choch':           [],
            'fvgs':            [],
            'order_blocks':    [],
            'liquidity_pools': [],
            'summary': {
                'bias':       'neutral',
                'swing_high': None,
                'swing_low':  None,
                'total_bars': 0,
            },
        }


# 全域單例
smc_service = SmcSignalService()
