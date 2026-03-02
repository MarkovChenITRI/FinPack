"""
Smart Money Concepts (SMC) 指標計算模組

涵蓋以下概念：
- Pivot High / Low（擺動高低點）
- BOS / CHOCH（突破結構 / 性質改變）
- FVG（公平價值缺口）
- Order Block（訂單區塊）
- Liquidity Pool（流動性池）
- Discount / Premium Zone（折扣 / 溢價區）

所有計算均在確認時刻標記，避免前瞻偏差（Look-ahead Bias）。
"""
import logging
import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


# =============================================================================
# 資料結構
# =============================================================================

@dataclass
class FVG:
    """公平價值缺口"""
    idx: int            # K 線索引（第三根 K 線，即缺口完成時）
    date: str
    direction: str      # 'bullish' | 'bearish'
    top: float          # 缺口上緣
    bottom: float       # 缺口下緣
    mid: float          # 缺口中點
    filled: bool = False

    @property
    def size(self) -> float:
        return self.top - self.bottom


@dataclass
class OrderBlock:
    """訂單區塊"""
    idx: int            # K 線索引（OB 所在 K 線）
    date: str
    direction: str      # 'bullish' | 'bearish'
    top: float          # OB 上緣（High）
    bottom: float       # OB 下緣（Low）
    body_top: float     # 實體上緣
    body_bottom: float  # 實體下緣
    valid: bool = True

    @property
    def mid(self) -> float:
        return (self.top + self.bottom) / 2


@dataclass
class StructurePoint:
    """市場結構事件（BOS / CHOCH）"""
    idx: int
    date: str
    event: str          # 'bullish_bos' | 'bearish_bos' | 'bullish_choch' | 'bearish_choch'
    broken_level: float # 被突破的價格水平
    close: float


@dataclass
class LiquidityPool:
    """流動性池（等高/等低）"""
    idx: int            # 最後一個組成點的索引
    date: str
    direction: str      # 'buy_side' (等高) | 'sell_side' (等低)
    level: float        # 流動性價格水平
    count: int          # 等高/等低點數量
    swept: bool = False


@dataclass
class SmcSignals:
    """單日 SMC 訊號集合（供回測引擎查詢）"""
    date: str
    # 最新結構方向
    bias: str                               # 'bullish' | 'bearish' | 'neutral'
    # 活躍 FVG 列表
    active_bullish_fvgs: list = field(default_factory=list)
    active_bearish_fvgs: list = field(default_factory=list)
    # 活躍 OB 列表
    active_bullish_obs: list = field(default_factory=list)
    active_bearish_obs: list = field(default_factory=list)
    # 最近結構點
    last_swing_high: float = 0.0
    last_swing_low: float = 0.0
    equilibrium: float = 0.0               # 折扣/溢價分界
    # 最近流動性池
    nearest_bsl: float = 0.0              # buy-side liquidity
    nearest_ssl: float = 0.0             # sell-side liquidity


# =============================================================================
# Pivot 高低點偵測
# =============================================================================

def detect_pivots(high: pd.Series, low: pd.Series, lookback: int = 5) -> pd.DataFrame:
    """
    偵測擺動高低點（右側確認，存在 lookback 根的延遲）

    Pivot High[i]: high[i] 是 [i-lookback, i+lookback] 範圍內的最高點
    Pivot Low[i]:  low[i]  是 [i-lookback, i+lookback] 範圍內的最低點

    注意：pivot 在 i+lookback 根 K 線後才能確認，在此時刻標記（無前瞻偏差）。

    Returns:
        DataFrame: columns=['pivot_high', 'pivot_low']
            - pivot_high: 高點價格（NaN 表示非 pivot）
            - pivot_low:  低點價格（NaN 表示非 pivot）
            - confirmed_at: pivot 確認的 K 線索引（= i + lookback）
    """
    n = len(high)
    pivot_high = np.full(n, np.nan)
    pivot_low  = np.full(n, np.nan)

    for i in range(lookback, n - lookback):
        window_high = high.iloc[i - lookback: i + lookback + 1]
        window_low  = low.iloc[i - lookback: i + lookback + 1]

        if high.iloc[i] == window_high.max():
            pivot_high[i] = high.iloc[i]

        if low.iloc[i] == window_low.min():
            pivot_low[i] = low.iloc[i]

    result = pd.DataFrame({
        'pivot_high': pivot_high,
        'pivot_low':  pivot_low,
    }, index=high.index)

    return result


# =============================================================================
# BOS / CHOCH 偵測
# =============================================================================

def detect_structure(
    ohlcv: pd.DataFrame,
    pivots: pd.DataFrame,
    lookback: int = 5
) -> list:
    """
    偵測 BOS / CHOCH 市場結構事件

    規則：
    - Bullish BOS:  收盤 > 最近已確認 Swing High（延續上漲結構）
    - Bearish BOS:  收盤 < 最近已確認 Swing Low（延續下跌結構）
    - Bullish CHOCH: 在下跌結構中出現的第一次 Bullish BOS（趨勢翻轉訊號）
    - Bearish CHOCH: 在上漲結構中出現的第一次 Bearish BOS（趨勢翻轉訊號）

    Returns:
        list of StructurePoint（按時間順序）
    """
    close  = ohlcv['Close']
    n      = len(close)
    events = []

    # 追蹤最近有效的 swing high/low（已確認的）
    last_swing_high: float = np.nan
    last_swing_low:  float = np.nan
    current_bias: str      = 'neutral'   # 'bullish' | 'bearish' | 'neutral'

    for i in range(lookback * 2, n):
        date_str = str(ohlcv.index[i])[:10]
        c = close.iloc[i]

        # 更新 swing high/low（只接受 i - lookback 以前已確認的 pivot）
        confirmed_idx = i - lookback
        if confirmed_idx >= 0:
            ph = pivots['pivot_high'].iloc[confirmed_idx]
            pl = pivots['pivot_low'].iloc[confirmed_idx]
            if not np.isnan(ph) and (np.isnan(last_swing_high) or ph > last_swing_high):
                # 只採用更高的 swing high（反映上漲結構）
                last_swing_high = ph
            if not np.isnan(pl) and (np.isnan(last_swing_low) or pl < last_swing_low):
                # 只採用更低的 swing low（反映下跌結構）
                last_swing_low = pl

        # 在中性/下跌結構中：偵測 Bullish BOS / CHOCH
        if not np.isnan(last_swing_high) and c > last_swing_high:
            if current_bias == 'bearish' or current_bias == 'neutral':
                event_type = 'bullish_choch' if current_bias == 'bearish' else 'bullish_bos'
            else:
                event_type = 'bullish_bos'

            events.append(StructurePoint(
                idx=i,
                date=date_str,
                event=event_type,
                broken_level=last_swing_high,
                close=c
            ))
            current_bias = 'bullish'
            # 重置 swing high，需等新的 swing high 被確認
            last_swing_high = np.nan

        # 在中性/上漲結構中：偵測 Bearish BOS / CHOCH
        elif not np.isnan(last_swing_low) and c < last_swing_low:
            if current_bias == 'bullish' or current_bias == 'neutral':
                event_type = 'bearish_choch' if current_bias == 'bullish' else 'bearish_bos'
            else:
                event_type = 'bearish_bos'

            events.append(StructurePoint(
                idx=i,
                date=date_str,
                event=event_type,
                broken_level=last_swing_low,
                close=c
            ))
            current_bias = 'bearish'
            last_swing_low = np.nan

    return events


# =============================================================================
# FVG 偵測
# =============================================================================

def detect_fvgs(ohlcv: pd.DataFrame, min_size_atr_ratio: float = 0.1) -> list:
    """
    偵測公平價值缺口（Fair Value Gap）

    Bullish FVG: 三根 K 線中，Low[i] > High[i-2]
    Bearish FVG: 三根 K 線中，High[i] < Low[i-2]

    第 i 根 K 線收盤即可確認，無前瞻偏差。

    Args:
        ohlcv: OHLCV DataFrame
        min_size_atr_ratio: FVG 最小大小 / ATR 比例（過濾雜訊小缺口）

    Returns:
        list of FVG
    """
    high  = ohlcv['High']
    low   = ohlcv['Low']
    close = ohlcv['Close']
    n     = len(ohlcv)

    # 計算 ATR（14 根）用於過濾過小缺口
    tr = pd.concat([
        high - low,
        (high - close.shift(1)).abs(),
        (low  - close.shift(1)).abs()
    ], axis=1).max(axis=1)
    atr = tr.rolling(14).mean()

    fvgs = []
    for i in range(2, n):
        date_str   = str(ohlcv.index[i])[:10]
        atr_val    = atr.iloc[i]
        min_size   = atr_val * min_size_atr_ratio if not np.isnan(atr_val) else 0

        # Bullish FVG
        gap = low.iloc[i] - high.iloc[i - 2]
        if gap > 0 and gap >= min_size:
            fvgs.append(FVG(
                idx=i,
                date=date_str,
                direction='bullish',
                top=low.iloc[i],
                bottom=high.iloc[i - 2],
                mid=(low.iloc[i] + high.iloc[i - 2]) / 2
            ))

        # Bearish FVG
        gap = low.iloc[i - 2] - high.iloc[i]
        if gap > 0 and gap >= min_size:
            fvgs.append(FVG(
                idx=i,
                date=date_str,
                direction='bearish',
                top=low.iloc[i - 2],
                bottom=high.iloc[i],
                mid=(low.iloc[i - 2] + high.iloc[i]) / 2
            ))

    return fvgs


def update_fvg_fill_status(fvgs: list, ohlcv: pd.DataFrame, at_idx: int) -> None:
    """
    更新 FVG 填補狀態（in-place）

    Bullish FVG 填補條件：收盤 <= FVG mid
    Bearish FVG 填補條件：收盤 >= FVG mid
    """
    close = ohlcv['Close'].iloc[at_idx]
    for fvg in fvgs:
        if fvg.filled:
            continue
        if fvg.direction == 'bullish' and close <= fvg.mid:
            fvg.filled = True
        elif fvg.direction == 'bearish' and close >= fvg.mid:
            fvg.filled = True


# =============================================================================
# Order Block 偵測
# =============================================================================

def detect_order_blocks(
    ohlcv: pd.DataFrame,
    structure_events: list,
    displacement_atr_ratio: float = 1.5,
    lookback: int = 10
) -> list:
    """
    偵測訂單區塊（Order Block）

    Bullish OB: 在多頭 BOS/CHOCH 之前，位移動量前的最後一根看跌 K 線
    Bearish OB: 在空頭 BOS/CHOCH 之前，位移動量前的最後一根看漲 K 線

    Args:
        ohlcv: OHLCV DataFrame
        structure_events: detect_structure() 的結果
        displacement_atr_ratio: 位移 K 線實體大小 / ATR 的最小倍數
        lookback: 往前搜尋 OB 的最大 K 線數

    Returns:
        list of OrderBlock
    """
    open_  = ohlcv['Open']
    high   = ohlcv['High']
    low    = ohlcv['Low']
    close  = ohlcv['Close']

    # 計算 ATR（14 根）
    tr = pd.concat([
        high - low,
        (high - close.shift(1)).abs(),
        (low  - close.shift(1)).abs()
    ], axis=1).max(axis=1)
    atr = tr.rolling(14).mean()

    # 計算每根 K 線的實體大小
    body = (close - open_).abs()

    obs = []

    for event in structure_events:
        idx      = event.idx
        atr_val  = atr.iloc[idx]
        if np.isnan(atr_val):
            continue

        min_body = atr_val * displacement_atr_ratio

        if 'bullish' in event.event:
            # 尋找位移起點：往前找第一根實體 >= min_body 的看漲 K 線
            displacement_idx = None
            for j in range(idx, max(idx - lookback, 0), -1):
                if close.iloc[j] > open_.iloc[j] and body.iloc[j] >= min_body:
                    displacement_idx = j
                    break
            if displacement_idx is None:
                continue

            # OB = 位移 K 線之前的最後一根看跌 K 線
            ob_idx = None
            for j in range(displacement_idx - 1, max(displacement_idx - lookback, 0), -1):
                if close.iloc[j] < open_.iloc[j]:  # 看跌 K 線
                    ob_idx = j
                    break
            if ob_idx is None:
                continue

            obs.append(OrderBlock(
                idx=ob_idx,
                date=str(ohlcv.index[ob_idx])[:10],
                direction='bullish',
                top=high.iloc[ob_idx],
                bottom=low.iloc[ob_idx],
                body_top=open_.iloc[ob_idx],
                body_bottom=close.iloc[ob_idx]
            ))

        elif 'bearish' in event.event:
            # 尋找位移起點：往前找第一根實體 >= min_body 的看跌 K 線
            displacement_idx = None
            for j in range(idx, max(idx - lookback, 0), -1):
                if close.iloc[j] < open_.iloc[j] and body.iloc[j] >= min_body:
                    displacement_idx = j
                    break
            if displacement_idx is None:
                continue

            # OB = 位移 K 線之前的最後一根看漲 K 線
            ob_idx = None
            for j in range(displacement_idx - 1, max(displacement_idx - lookback, 0), -1):
                if close.iloc[j] > open_.iloc[j]:  # 看漲 K 線
                    ob_idx = j
                    break
            if ob_idx is None:
                continue

            obs.append(OrderBlock(
                idx=ob_idx,
                date=str(ohlcv.index[ob_idx])[:10],
                direction='bearish',
                top=high.iloc[ob_idx],
                bottom=low.iloc[ob_idx],
                body_top=close.iloc[ob_idx],
                body_bottom=open_.iloc[ob_idx]
            ))

    return obs


def invalidate_order_blocks(obs: list, ohlcv: pd.DataFrame, at_idx: int) -> None:
    """
    使已失效的 OB 標記為 invalid（in-place）

    Bullish OB 失效：收盤 < OB.bottom
    Bearish OB 失效：收盤 > OB.top
    """
    close = ohlcv['Close'].iloc[at_idx]
    for ob in obs:
        if not ob.valid:
            continue
        if ob.direction == 'bullish' and close < ob.bottom:
            ob.valid = False
        elif ob.direction == 'bearish' and close > ob.top:
            ob.valid = False


# =============================================================================
# 流動性池偵測
# =============================================================================

def detect_liquidity_pools(
    pivots: pd.DataFrame,
    ohlcv: pd.DataFrame,
    tolerance_pct: float = 0.002,
    min_count: int = 2
) -> list:
    """
    偵測流動性池（等高/等低）

    Args:
        pivots: detect_pivots() 結果
        tolerance_pct: 視為「等高/等低」的容忍百分比（預設 0.2%）
        min_count: 最少幾個點才構成流動性池

    Returns:
        list of LiquidityPool
    """
    pools = []

    # Buy-side liquidity (等高，止損集中在上方)
    highs = [(i, pivots['pivot_high'].iloc[i])
             for i in range(len(pivots))
             if not np.isnan(pivots['pivot_high'].iloc[i])]

    used = set()
    for i, (idx1, h1) in enumerate(highs):
        if idx1 in used:
            continue
        cluster = [(idx1, h1)]
        for j, (idx2, h2) in enumerate(highs[i+1:], i+1):
            if idx2 in used:
                continue
            if abs(h2 - h1) / h1 <= tolerance_pct:
                cluster.append((idx2, h2))

        if len(cluster) >= min_count:
            last_idx = cluster[-1][0]
            avg_level = np.mean([h for _, h in cluster])
            pools.append(LiquidityPool(
                idx=last_idx,
                date=str(ohlcv.index[last_idx])[:10],
                direction='buy_side',
                level=avg_level,
                count=len(cluster)
            ))
            for idx, _ in cluster:
                used.add(idx)

    # Sell-side liquidity (等低，止損集中在下方)
    lows = [(i, pivots['pivot_low'].iloc[i])
            for i in range(len(pivots))
            if not np.isnan(pivots['pivot_low'].iloc[i])]

    used = set()
    for i, (idx1, l1) in enumerate(lows):
        if idx1 in used:
            continue
        cluster = [(idx1, l1)]
        for j, (idx2, l2) in enumerate(lows[i+1:], i+1):
            if idx2 in used:
                continue
            if abs(l2 - l1) / l1 <= tolerance_pct:
                cluster.append((idx2, l2))

        if len(cluster) >= min_count:
            last_idx = cluster[-1][0]
            avg_level = np.mean([l for _, l in cluster])
            pools.append(LiquidityPool(
                idx=last_idx,
                date=str(ohlcv.index[last_idx])[:10],
                direction='sell_side',
                level=avg_level,
                count=len(cluster)
            ))
            for idx, _ in cluster:
                used.add(idx)

    return pools


# =============================================================================
# SMC 指標彙整類
# =============================================================================

class SmcIndicators:
    """
    SMC 指標計算器（惰性計算）

    使用方式：
        smc = SmcIndicators(ohlcv_df)
        signal = smc.get_signal_at(idx)

    所有計算在首次存取時執行，後續使用快取。
    """

    def __init__(
        self,
        ohlcv: pd.DataFrame,
        pivot_lookback: int = 5,
        fvg_min_size_atr: float = 0.1,
        displacement_atr: float = 1.5,
        lp_tolerance_pct: float = 0.002,
    ):
        """
        Args:
            ohlcv: OHLCV DataFrame（Index 為 DatetimeIndex）
            pivot_lookback: Pivot 左右確認根數
            fvg_min_size_atr: FVG 最小尺寸（ATR 倍數）
            displacement_atr: 位移 K 線最小實體（ATR 倍數）
            lp_tolerance_pct: 流動性池容忍度百分比
        """
        self.ohlcv              = ohlcv
        self.pivot_lookback     = pivot_lookback
        self.fvg_min_size_atr   = fvg_min_size_atr
        self.displacement_atr   = displacement_atr
        self.lp_tolerance_pct   = lp_tolerance_pct

        self._pivots: Optional[pd.DataFrame]   = None
        self._structure: Optional[list]        = None
        self._fvgs: Optional[list]             = None
        self._obs: Optional[list]              = None
        self._lp: Optional[list]               = None

    @property
    def pivots(self) -> pd.DataFrame:
        if self._pivots is None:
            logger.info('[SMC] 計算 Pivot 高低點...')
            self._pivots = detect_pivots(
                self.ohlcv['High'], self.ohlcv['Low'], self.pivot_lookback
            )
        return self._pivots

    @property
    def structure(self) -> list:
        if self._structure is None:
            logger.info('[SMC] 偵測市場結構 (BOS/CHOCH)...')
            self._structure = detect_structure(self.ohlcv, self.pivots, self.pivot_lookback)
        return self._structure

    @property
    def fvgs(self) -> list:
        if self._fvgs is None:
            logger.info('[SMC] 偵測 FVG...')
            self._fvgs = detect_fvgs(self.ohlcv, self.fvg_min_size_atr)
        return self._fvgs

    @property
    def order_blocks(self) -> list:
        if self._obs is None:
            logger.info('[SMC] 偵測 Order Block...')
            self._obs = detect_order_blocks(
                self.ohlcv, self.structure, self.displacement_atr
            )
        return self._obs

    @property
    def liquidity_pools(self) -> list:
        if self._lp is None:
            logger.info('[SMC] 偵測流動性池...')
            self._lp = detect_liquidity_pools(
                self.pivots, self.ohlcv, self.lp_tolerance_pct
            )
        return self._lp

    def get_current_bias(self, up_to_idx: int) -> str:
        """取得 up_to_idx 時的市場偏向（'bullish' | 'bearish' | 'neutral'）"""
        bias = 'neutral'
        for event in self.structure:
            if event.idx > up_to_idx:
                break
            if 'bullish' in event.event:
                bias = 'bullish'
            elif 'bearish' in event.event:
                bias = 'bearish'
        return bias

    def get_active_fvgs(self, direction: str, up_to_idx: int) -> list:
        """取得 up_to_idx 前仍有效（未填補）的 FVG"""
        return [f for f in self.fvgs
                if f.direction == direction
                and f.idx <= up_to_idx
                and not f.filled]

    def get_active_obs(self, direction: str, up_to_idx: int) -> list:
        """取得 up_to_idx 前仍有效的 OB"""
        return [ob for ob in self.order_blocks
                if ob.direction == direction
                and ob.idx <= up_to_idx
                and ob.valid]

    def get_swing_range(self, up_to_idx: int) -> tuple:
        """
        取得最近確認的擺動高低點（用於計算折扣/溢價區）

        Returns:
            (swing_low, swing_high)
        """
        swing_high = np.nan
        swing_low  = np.nan

        # 往前找最近的 pivot high/low
        for i in range(min(up_to_idx, len(self.pivots) - 1), -1, -1):
            ph = self.pivots['pivot_high'].iloc[i]
            pl = self.pivots['pivot_low'].iloc[i]
            if np.isnan(swing_high) and not np.isnan(ph):
                swing_high = ph
            if np.isnan(swing_low) and not np.isnan(pl):
                swing_low = pl
            if not np.isnan(swing_high) and not np.isnan(swing_low):
                break

        return swing_low, swing_high

    def is_in_discount(self, price: float, up_to_idx: int) -> bool:
        """判斷當前價格是否在折扣區（< 50% 擺動中點）"""
        swing_low, swing_high = self.get_swing_range(up_to_idx)
        if np.isnan(swing_low) or np.isnan(swing_high):
            return False
        equilibrium = (swing_low + swing_high) / 2
        return price < equilibrium

    def is_in_premium(self, price: float, up_to_idx: int) -> bool:
        """判斷當前價格是否在溢價區（> 50% 擺動中點）"""
        swing_low, swing_high = self.get_swing_range(up_to_idx)
        if np.isnan(swing_low) or np.isnan(swing_high):
            return False
        equilibrium = (swing_low + swing_high) / 2
        return price > equilibrium

    def price_in_fvg(self, price: float, fvg: FVG) -> bool:
        """判斷價格是否在 FVG 內"""
        return fvg.bottom <= price <= fvg.top

    def price_in_ob(self, price: float, ob: OrderBlock) -> bool:
        """判斷價格是否在 OB 內"""
        return ob.bottom <= price <= ob.top

    def get_nearest_liquidity(self, price: float, up_to_idx: int) -> tuple:
        """
        取得最近的 buy-side / sell-side 流動性池

        Returns:
            (nearest_bsl, nearest_ssl)  浮點數或 nan
        """
        valid_lp = [lp for lp in self.liquidity_pools
                    if lp.idx <= up_to_idx and not lp.swept]

        bsl_levels = [lp.level for lp in valid_lp
                      if lp.direction == 'buy_side' and lp.level > price]
        ssl_levels = [lp.level for lp in valid_lp
                      if lp.direction == 'sell_side' and lp.level < price]

        nearest_bsl = min(bsl_levels) if bsl_levels else np.nan
        nearest_ssl = max(ssl_levels) if ssl_levels else np.nan

        return nearest_bsl, nearest_ssl

    def update_at(self, idx: int) -> None:
        """
        在回測迴圈中每個 bar 呼叫，更新 FVG 填補狀態 & OB 失效狀態

        必須在 get_signal_at 之前呼叫。
        """
        update_fvg_fill_status(self.fvgs, self.ohlcv, idx)
        invalidate_order_blocks(self.order_blocks, self.ohlcv, idx)

    def get_signal_at(self, idx: int) -> SmcSignals:
        """
        取得指定索引的完整 SMC 訊號

        Args:
            idx: K 線索引（此時刻的資訊，無前瞻偏差）

        Returns:
            SmcSignals 實例
        """
        date_str = str(self.ohlcv.index[idx])[:10]
        close    = self.ohlcv['Close'].iloc[idx]

        bias = self.get_current_bias(idx)

        # 折扣/溢價
        swing_low, swing_high = self.get_swing_range(idx)
        equilibrium = (swing_low + swing_high) / 2 if not (np.isnan(swing_low) or np.isnan(swing_high)) else np.nan

        # 流動性池
        nearest_bsl, nearest_ssl = self.get_nearest_liquidity(close, idx)

        return SmcSignals(
            date=date_str,
            bias=bias,
            active_bullish_fvgs=self.get_active_fvgs('bullish', idx),
            active_bearish_fvgs=self.get_active_fvgs('bearish', idx),
            active_bullish_obs=self.get_active_obs('bullish', idx),
            active_bearish_obs=self.get_active_obs('bearish', idx),
            last_swing_high=swing_high if not np.isnan(swing_high) else 0.0,
            last_swing_low=swing_low if not np.isnan(swing_low) else 0.0,
            equilibrium=equilibrium if not np.isnan(equilibrium) else 0.0,
            nearest_bsl=nearest_bsl if not np.isnan(nearest_bsl) else 0.0,
            nearest_ssl=nearest_ssl if not np.isnan(nearest_ssl) else 0.0,
        )
