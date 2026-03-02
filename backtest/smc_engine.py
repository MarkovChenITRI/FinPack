"""
SMC 專用回測引擎（BTC-USD 合約版）

基於 Smart Money Concepts 訊號進行單資產回測。
支援做多/做空、槓桿、強平價驗證。

槓桿邏輯：
- 每筆風險金額 = 初始資金 × risk_per_trade
- 保證金 = 名目本金 / leverage
- 若強平價在止損之前觸發，跳過此筆交易
- PnL 使用名目本金計算（槓桿放大）
"""
import logging
import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from typing import Optional, List

from core.smc import SmcIndicators, FVG, OrderBlock

logger = logging.getLogger(__name__)


# =============================================================================
# 資料結構
# =============================================================================

@dataclass
class SmcTrade:
    """SMC 交易紀錄（含槓桿）"""
    entry_date:  str
    exit_date:   str
    direction:   str            # 'long' | 'short'
    entry_price: float
    exit_price:  float
    stop_loss:   float
    take_profit: float          # 0 = 無止盈
    liq_price:   float          # 強平價
    leverage:    int
    qty:         float          # BTC 名目數量（已乘槓桿）
    margin:      float          # 實際佔用保證金（USD）
    fee:         float          # 手續費（USD）
    pnl:         float          # 損益（USD，含手續費）
    pnl_pct:     float          # 損益百分比（相對保證金）
    reason:      str            # 出場原因

    def to_dict(self) -> dict:
        # 計算風險回報比（R:R）
        sl_dist = abs(self.entry_price - self.stop_loss)
        if self.take_profit and self.take_profit > 0 and sl_dist > 0:
            tp_dist = abs(self.take_profit - self.entry_price)
            rr = round(tp_dist / sl_dist, 2)
        else:
            rr = None

        return {
            'entry_date':  self.entry_date,
            'exit_date':   self.exit_date,
            'direction':   self.direction,
            'entry_price': round(self.entry_price, 2),
            'stop_loss':   round(self.stop_loss, 2),
            'take_profit': round(self.take_profit, 2) if self.take_profit else None,
            'rr':          rr,
            'exit_price':  round(self.exit_price, 2),
            'liq_price':   round(self.liq_price, 2),
            'leverage':    self.leverage,
            'qty':         round(self.qty, 6),
            'margin':      round(self.margin, 2),
            'pnl':         round(self.pnl, 2),
            'pnl_pct':     f"{self.pnl_pct:.2%}",
            'fee':         round(self.fee, 2),
            'reason':      self.reason,
        }


@dataclass
class SmcPosition:
    """SMC 持倉（含槓桿）"""
    direction:   str
    entry_date:  str
    entry_price: float
    qty:         float          # 名目 BTC 數量
    margin:      float          # 保證金（USD）
    stop_loss:   float
    take_profit: float
    liq_price:   float          # 強平價
    leverage:    int
    peak_price:  float          # 追蹤最高/最低（供移動止損）


@dataclass
class SmcBacktestResult:
    """SMC 回測結果"""
    initial_capital:   float
    final_equity:      float
    total_return:      float
    annualized_return: float
    total_trades:      int
    win_trades:        int
    loss_trades:       int
    win_rate:          float
    max_drawdown:      float
    sharpe_ratio:      float
    avg_rr:            float
    leverage:          int
    trades:            list
    equity_curve:      list

    def to_dict(self) -> dict:
        return {
            'initial_capital':   f"${self.initial_capital:,.2f}",
            'final_equity':      f"${self.final_equity:,.2f}",
            'total_return':      f"{self.total_return:.2%}",
            'total_return_raw':  self.total_return,
            'annualized_return': f"{self.annualized_return:.2%}",
            'total_trades':      self.total_trades,
            'win_trades':        self.win_trades,
            'loss_trades':       self.loss_trades,
            'win_rate':          f"{self.win_rate:.2%}",
            'win_rate_raw':      self.win_rate,
            'max_drawdown':      f"{self.max_drawdown:.2%}",
            'max_drawdown_raw':  self.max_drawdown,
            'sharpe_ratio':      round(self.sharpe_ratio, 2),
            'avg_rr':            round(self.avg_rr, 2),
            'leverage':          self.leverage,
        }


# =============================================================================
# 強平價計算工具
# =============================================================================

def calc_liq_price(direction: str, entry: float, leverage: int) -> float:
    """
    計算強平價（不含維持保證金率，簡化計算）

    Long:  liq = entry × (1 - 1/leverage)
    Short: liq = entry × (1 + 1/leverage)
    """
    if leverage <= 1:
        return 0.0  # 無槓桿現貨，無強平
    if direction == 'long':
        return entry * (1.0 - 1.0 / leverage)
    else:
        return entry * (1.0 + 1.0 / leverage)


def is_liq_safe(direction: str, liq_price: float, stop_loss: float) -> bool:
    """
    確認強平價不會比止損更早觸發

    Long:  需要 liq_price < stop_loss（強平比止損低）
    Short: 需要 liq_price > stop_loss（強平比止損高）
    返回 True 表示安全（可以開倉）
    """
    if liq_price == 0.0:  # 無槓桿
        return True
    if direction == 'long':
        return liq_price < stop_loss
    else:
        return liq_price > stop_loss


# =============================================================================
# SMC 回測引擎
# =============================================================================

class SmcEngine:
    """
    BTC-USD Smart Money Concepts 合約回測引擎

    Args:
        ohlcv:  OHLCV DataFrame（完整歷史，含回測起點前的 warmup 資料）
        config: load_smc_config() 返回的配置 dict
    """

    def __init__(self, ohlcv: pd.DataFrame, config: dict):
        if ohlcv.empty:
            raise ValueError('ohlcv 不得為空')
        if config is None:
            raise ValueError('config 必填')

        self.ohlcv    = ohlcv
        self.config   = config
        self.leverage = int(config.get('leverage', 1))

        # SMC 指標（惰性計算）
        self.smc = SmcIndicators(
            ohlcv,
            pivot_lookback   = config['pivot_lookback'],
            fvg_min_size_atr = config['fvg_min_size_atr'],
            displacement_atr = config['displacement_atr'],
            lp_tolerance_pct = config['lp_tolerance_pct'],
        )

        # 回測狀態
        self.equity: float                    = config['initial_capital']
        self.position: Optional[SmcPosition] = None
        self.trades:   List[SmcTrade]        = []
        self.equity_curve: List[dict]        = []

    # =========================================================================
    # 公開方法
    # =========================================================================

    def run(self, start_date: str = None, end_date: str = None) -> SmcBacktestResult:
        """執行回測"""
        start = start_date or self.config['start_date']
        end   = end_date   or self.config.get('end_date')

        idx_start = self.ohlcv.index.searchsorted(pd.Timestamp(start))
        if end:
            idx_end = self.ohlcv.index.searchsorted(pd.Timestamp(end), side='right') - 1
        else:
            idx_end = len(self.ohlcv) - 1

        logger.info('[SMC] 回測: %s ~ %s (leverage=%dx)',
                    self.ohlcv.index[idx_start].date(),
                    self.ohlcv.index[idx_end].date(),
                    self.leverage)

        # 預計算所有 SMC 訊號
        _ = self.smc.structure
        _ = self.smc.fvgs
        _ = self.smc.order_blocks
        _ = self.smc.liquidity_pools

        for idx in range(idx_start, idx_end + 1):
            self._process_bar(idx)

        return self._calculate_result(idx_start, idx_end)

    # =========================================================================
    # 內部：每根 K 線處理
    # =========================================================================

    def _process_bar(self, idx: int) -> None:
        date_str = str(self.ohlcv.index[idx])[:10]

        self.smc.update_at(idx)

        if self.position is not None:
            self._process_exit(idx, date_str)

        if self.position is None:
            self._process_entry(idx, date_str)

        if self.position is not None:
            self._update_peak(idx)

        equity = self._calc_equity(idx)
        self.equity_curve.append({
            'time':   date_str,
            'equity': round(equity, 2),
        })

    def _process_entry(self, idx: int, date_str: str) -> None:
        close  = self.ohlcv['Close'].iloc[idx]
        signal = self.smc.get_signal_at(idx)
        entry  = self.config['entry_conditions']
        cfg    = self.config

        if cfg['allow_long']:
            ok, stop_price, tp_price = self._check_long_entry(idx, close, signal, entry)
            if ok and stop_price > 0:
                self._open_position('long', idx, date_str, close, stop_price, tp_price)
                return

        if cfg['allow_short']:
            ok, stop_price, tp_price = self._check_short_entry(idx, close, signal, entry)
            if ok and stop_price > 0:
                self._open_position('short', idx, date_str, close, stop_price, tp_price)

    def _check_long_entry(self, idx, close, signal, entry):
        if entry.get('require_bias', {}).get('enabled'):
            if signal.bias != 'bullish':
                return False, 0, 0

        if entry.get('require_discount', {}).get('enabled'):
            if not self.smc.is_in_discount(close, idx):
                return False, 0, 0

        require_ob  = entry.get('require_ob',  {}).get('enabled', False)
        require_fvg = entry.get('require_fvg', {}).get('enabled', False)

        tp_price = signal.nearest_bsl
        stop_loss_pct = self.config['exit_conditions']['stop_loss_pct']['pct']

        if require_ob:
            for ob in reversed(signal.active_bullish_obs):
                if self.smc.price_in_ob(close, ob):
                    stop_price = ob.bottom * (1 - stop_loss_pct)
                    return True, stop_price, tp_price

        if require_fvg:
            for fvg in reversed(signal.active_bullish_fvgs):
                if self.smc.price_in_fvg(close, fvg):
                    stop_price = fvg.bottom * (1 - stop_loss_pct)
                    return True, stop_price, tp_price

        if require_ob or require_fvg:
            return False, 0, 0

        return False, 0, 0

    def _check_short_entry(self, idx, close, signal, entry):
        if entry.get('require_bias', {}).get('enabled'):
            if signal.bias != 'bearish':
                return False, 0, 0

        if entry.get('require_discount', {}).get('enabled'):
            if not self.smc.is_in_premium(close, idx):
                return False, 0, 0

        require_ob  = entry.get('require_ob',  {}).get('enabled', False)
        require_fvg = entry.get('require_fvg', {}).get('enabled', False)

        tp_price = signal.nearest_ssl
        stop_loss_pct = self.config['exit_conditions']['stop_loss_pct']['pct']

        if require_ob:
            for ob in reversed(signal.active_bearish_obs):
                if self.smc.price_in_ob(close, ob):
                    stop_price = ob.top * (1 + stop_loss_pct)
                    return True, stop_price, tp_price

        if require_fvg:
            for fvg in reversed(signal.active_bearish_fvgs):
                if self.smc.price_in_fvg(close, fvg):
                    stop_price = fvg.top * (1 + stop_loss_pct)
                    return True, stop_price, tp_price

        if require_ob or require_fvg:
            return False, 0, 0

        return False, 0, 0

    def _open_position(
        self,
        direction:   str,
        idx:         int,
        date_str:    str,
        entry_price: float,
        stop_price:  float,
        tp_price:    float,
    ) -> None:
        """
        開倉（含槓桿驗證）

        資金管理：
        - risk_amount  = equity × risk_per_trade
        - stop_distance = |entry - stop| / entry（百分比）
        - 名目本金 = risk_amount / stop_distance
        - 保證金   = 名目本金 / leverage
        - qty      = 名目本金 / entry_price
        """
        stop_distance = abs(entry_price - stop_price) / entry_price
        if stop_distance <= 0:
            return

        # 計算強平價，驗證安全性
        liq_price = calc_liq_price(direction, entry_price, self.leverage)
        if not is_liq_safe(direction, liq_price, stop_price):
            logger.debug(
                '[SMC] 跳過 %s @ %.2f：強平價 %.2f 會先於止損 %.2f 觸發',
                direction, entry_price, liq_price, stop_price
            )
            return

        risk_amount  = self.equity * self.config['risk_per_trade']
        notional     = risk_amount / stop_distance          # 名目本金
        margin       = notional / self.leverage             # 所需保證金
        qty          = notional / entry_price               # 名目 BTC 數量

        # 保證金不超過可用資金的 50%（防過度集中）
        max_margin = self.equity * 0.5
        if margin > max_margin:
            margin   = max_margin
            notional = margin * self.leverage
            qty      = notional / entry_price

        if margin > self.equity or qty <= 0:
            return

        fee = notional * self.config['fee_rate']
        self.equity -= (margin + fee)

        self.position = SmcPosition(
            direction   = direction,
            entry_date  = date_str,
            entry_price = entry_price,
            qty         = qty,
            margin      = margin,
            stop_loss   = stop_price,
            take_profit = tp_price,
            liq_price   = liq_price,
            leverage    = self.leverage,
            peak_price  = entry_price,
        )

        logger.debug(
            '[SMC] 開 %s @ %.2f | SL=%.2f TP=%.2f LIQ=%.2f margin=$%.2f %dx',
            direction, entry_price, stop_price, tp_price, liq_price, margin, self.leverage
        )

    def _process_exit(self, idx: int, date_str: str) -> None:
        pos    = self.position
        close  = self.ohlcv['Close'].iloc[idx]
        low    = self.ohlcv['Low'].iloc[idx]
        high   = self.ohlcv['High'].iloc[idx]
        exit_  = self.config['exit_conditions']
        signal = self.smc.get_signal_at(idx)

        reason     = None
        exit_price = close

        if pos.direction == 'long':
            # 強平（優先檢查）
            if pos.liq_price > 0 and low <= pos.liq_price:
                reason     = f'liquidated({pos.liq_price:.2f})'
                exit_price = pos.liq_price

            elif exit_.get('stop_loss_pct', {}).get('enabled') and low <= pos.stop_loss:
                reason     = f'stop_loss({pos.stop_loss:.2f})'
                exit_price = pos.stop_loss

            elif (exit_.get('take_profit_liquidity', {}).get('enabled')
                  and pos.take_profit > 0 and high >= pos.take_profit):
                reason     = f'tp_liquidity({pos.take_profit:.2f})'
                exit_price = pos.take_profit

            elif exit_.get('structure_exit', {}).get('enabled') and signal.bias == 'bearish':
                reason     = 'structure_flip_bearish'
                exit_price = close

            elif exit_.get('max_holding_bars', {}).get('enabled'):
                bars_held = idx - self.ohlcv.index.searchsorted(pd.Timestamp(pos.entry_date))
                if bars_held >= exit_['max_holding_bars']['bars']:
                    reason     = f'max_bars({bars_held})'
                    exit_price = close

        elif pos.direction == 'short':
            if pos.liq_price > 0 and high >= pos.liq_price:
                reason     = f'liquidated({pos.liq_price:.2f})'
                exit_price = pos.liq_price

            elif exit_.get('stop_loss_pct', {}).get('enabled') and high >= pos.stop_loss:
                reason     = f'stop_loss({pos.stop_loss:.2f})'
                exit_price = pos.stop_loss

            elif (exit_.get('take_profit_liquidity', {}).get('enabled')
                  and pos.take_profit > 0 and low <= pos.take_profit):
                reason     = f'tp_liquidity({pos.take_profit:.2f})'
                exit_price = pos.take_profit

            elif exit_.get('structure_exit', {}).get('enabled') and signal.bias == 'bullish':
                reason     = 'structure_flip_bullish'
                exit_price = close

            elif exit_.get('max_holding_bars', {}).get('enabled'):
                bars_held = idx - self.ohlcv.index.searchsorted(pd.Timestamp(pos.entry_date))
                if bars_held >= exit_['max_holding_bars']['bars']:
                    reason     = f'max_bars({bars_held})'
                    exit_price = close

        if reason is None:
            return

        self._close_position(date_str, exit_price, reason)

    def _close_position(self, date_str: str, exit_price: float, reason: str) -> None:
        """
        平倉（含槓桿 PnL 計算）

        Long  PnL = (exit - entry) / entry × notional
        Short PnL = (entry - exit) / entry × notional
        """
        pos     = self.position
        notional = pos.qty * pos.entry_price   # 名目本金

        if pos.direction == 'long':
            pnl_raw = (exit_price - pos.entry_price) / pos.entry_price * notional
        else:
            pnl_raw = (pos.entry_price - exit_price) / pos.entry_price * notional

        fee = (pos.qty * exit_price) * self.config['fee_rate']
        pnl = pnl_raw - fee

        # 強平時 pnl 最多虧損保證金
        if 'liquidated' in reason:
            pnl = max(pnl, -pos.margin)

        pnl_pct = pnl / pos.margin if pos.margin > 0 else 0

        # 歸還保證金 + pnl（若已爆倉則只歸還 0）
        returned = max(pos.margin + pnl, 0)
        self.equity += returned

        self.trades.append(SmcTrade(
            entry_date  = pos.entry_date,
            exit_date   = date_str,
            direction   = pos.direction,
            entry_price = pos.entry_price,
            exit_price  = exit_price,
            stop_loss   = pos.stop_loss,
            take_profit = pos.take_profit,
            liq_price   = pos.liq_price,
            leverage    = pos.leverage,
            qty         = pos.qty,
            margin      = pos.margin,
            fee         = fee,
            pnl         = pnl,
            pnl_pct     = pnl_pct,
            reason      = reason,
        ))

        logger.debug('[SMC] 平倉 %s @ %.2f | PnL=$%.2f (%s)',
                     pos.direction, exit_price, pnl, reason)
        self.position = None

    def _update_peak(self, idx: int) -> None:
        pos = self.position
        if pos.direction == 'long':
            h = self.ohlcv['High'].iloc[idx]
            if h > pos.peak_price:
                pos.peak_price = h
        else:
            l = self.ohlcv['Low'].iloc[idx]
            if l < pos.peak_price:
                pos.peak_price = l

    # =========================================================================
    # 內部：權益計算
    # =========================================================================

    def _calc_equity(self, idx: int) -> float:
        """計算當日總權益（USD）"""
        if self.position is None:
            return self.equity

        close = self.ohlcv['Close'].iloc[idx]
        pos   = self.position
        notional = pos.qty * pos.entry_price

        if pos.direction == 'long':
            unrealized = (close - pos.entry_price) / pos.entry_price * notional
        else:
            unrealized = (pos.entry_price - close) / pos.entry_price * notional

        # 保證金 + 未實現損益（最低 0，爆倉清零）
        position_value = max(pos.margin + unrealized, 0)
        return self.equity + position_value

    # =========================================================================
    # 內部：計算回測結果
    # =========================================================================

    def _calculate_result(self, start_idx: int, end_idx: int) -> SmcBacktestResult:
        initial = self.config['initial_capital']
        final   = self._calc_equity(end_idx)

        total_return = (final - initial) / initial
        days         = end_idx - start_idx + 1
        years        = max(days / 365, 0.01)
        annualized   = (1 + total_return) ** (1 / years) - 1

        win_trades  = [t for t in self.trades if t.pnl > 0]
        loss_trades = [t for t in self.trades if t.pnl <= 0]
        total       = len(self.trades)
        win_rate    = len(win_trades) / total if total > 0 else 0

        avg_win  = np.mean([t.pnl for t in win_trades])  if win_trades  else 0
        avg_loss = abs(np.mean([t.pnl for t in loss_trades])) if loss_trades else 1
        avg_rr   = avg_win / avg_loss if avg_loss > 0 else 0

        # 最大回撤
        peak   = initial
        max_dd = 0.0
        for p in self.equity_curve:
            eq = p['equity']
            if eq > peak:
                peak = eq
            dd = (peak - eq) / peak if peak > 0 else 0
            if dd > max_dd:
                max_dd = dd

        # Sharpe
        if len(self.equity_curve) > 1:
            eqs  = [p['equity'] for p in self.equity_curve]
            rets = np.diff(eqs) / np.array(eqs[:-1])
            sharpe = (np.mean(rets) / np.std(rets) * np.sqrt(365)
                      if np.std(rets) > 0 else 0)
        else:
            sharpe = 0.0

        return SmcBacktestResult(
            initial_capital   = initial,
            final_equity      = final,
            total_return      = total_return,
            annualized_return = annualized,
            total_trades      = total,
            win_trades        = len(win_trades),
            loss_trades       = len(loss_trades),
            win_rate          = win_rate,
            max_drawdown      = max_dd,
            sharpe_ratio      = sharpe,
            avg_rr            = avg_rr,
            leverage          = self.leverage,
            trades            = [t.to_dict() for t in self.trades],
            equity_curve      = self.equity_curve,
        )
