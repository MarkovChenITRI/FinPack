"""
Cloud Functions 回測引擎
移植自 static/js/backtest/Engine.js
"""
import pandas as pd
import numpy as np
import logging
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum

from .config import DEFAULT_BACKTEST_CONFIG, FEES, BACKTEST_YEARS, NON_TRADABLE_INDUSTRIES
from .indicator import Indicators

logger = logging.getLogger(__name__)


class TradeType(Enum):
    BUY = 'buy'
    SELL = 'sell'


@dataclass
class Trade:
    """交易紀錄"""
    date: str
    symbol: str
    type: TradeType
    shares: int
    price: float
    amount: float
    fee: float
    reason: str = ''
    
    def to_dict(self) -> dict:
        return {
            'date': self.date,
            'symbol': self.symbol,
            'type': self.type.value,
            'shares': self.shares,
            'price': self.price,
            'amount': self.amount,
            'fee': self.fee,
            'reason': self.reason,
        }


@dataclass
class Position:
    """持倉"""
    symbol: str
    shares: int
    avg_cost: float
    buy_date: str
    buy_price: float
    peak_price: float = 0.0
    
    @property
    def cost_basis(self) -> float:
        return self.shares * self.avg_cost


@dataclass
class BacktestResult:
    """回測結果"""
    initial_capital: float
    final_equity: float
    total_return: float
    annualized_return: float
    total_trades: int
    win_trades: int
    loss_trades: int
    win_rate: float
    max_drawdown: float
    sharpe_ratio: float
    trades: list
    equity_curve: list
    
    def to_dict(self) -> dict:
        return {
            'initial_capital': self.initial_capital,
            'final_equity': self.final_equity,
            'total_return': f"{self.total_return:.2%}",
            'annualized_return': f"{self.annualized_return:.2%}",
            'total_trades': self.total_trades,
            'win_trades': self.win_trades,
            'loss_trades': self.loss_trades,
            'win_rate': f"{self.win_rate:.2%}",
            'max_drawdown': f"{self.max_drawdown:.2%}",
            'sharpe_ratio': round(self.sharpe_ratio, 2),
            'trade_count': len(self.trades),
        }


class BacktestEngine:
    """
    回測引擎
    """
    def __init__(self, 
                 close_df: pd.DataFrame,
                 indicators: Indicators,
                 stock_info: dict,
                 config: dict = None):
        """
        Args:
            close_df: 對齊後的收盤價 DataFrame
            indicators: 指標計算器
            stock_info: 股票資訊
            config: 回測配置（預設使用 DEFAULT_BACKTEST_CONFIG）
        """
        self.close = close_df
        self.indicators = indicators
        self.stock_info = stock_info
        self.config = config or DEFAULT_BACKTEST_CONFIG.copy()
        
        # 狀態
        self.cash = self.config['initial_capital']
        self.positions: dict[str, Position] = {}
        self.trades: list[Trade] = []
        self.equity_curve: list[dict] = []
        
        # 追蹤
        self._sharpe_fail_counter: dict[str, int] = {}
        self._not_selected_counter: dict[str, int] = {}
        self._weakness_counter: dict[str, int] = {}
        self._growth_fail_counter: dict[str, int] = {}
        self._last_rebalance_idx = -999
        
    def run(self, start_date: datetime = None, end_date: datetime = None) -> BacktestResult:
        """
        執行回測
        
        Args:
            start_date: 開始日期（預設為資料起始後 BACKTEST_YEARS 年）
            end_date: 結束日期（預設為資料結束）
        """
        date_index = self.close.index
        
        # 決定回測範圍
        if end_date is None:
            end_date = date_index[-1]
        if start_date is None:
            start_date = end_date - pd.DateOffset(years=BACKTEST_YEARS)
        
        # 找到起始和結束索引
        start_idx = date_index.searchsorted(start_date)
        end_idx = date_index.searchsorted(end_date, side='right') - 1
        
        logger.info(f"Backtest period: {date_index[start_idx].date()} to {date_index[end_idx].date()}")
        logger.info(f"Trading days: {end_idx - start_idx + 1}")
        
        # 主迴圈
        for idx in range(start_idx, end_idx + 1):
            self._process_day(idx)
        
        # 計算結果
        return self._calculate_result(start_idx, end_idx)
    
    def _process_day(self, idx: int):
        """處理單一交易日"""
        date = self.close.index[idx]
        date_str = date.strftime('%Y-%m-%d')
        
        # 更新持倉峰值（用於計算 drawdown）
        self._update_peak_prices(idx)
        
        # 處理賣出訊號
        self._process_sell_signals(idx, date_str)
        
        # 檢查是否為再平衡日
        if self._is_rebalance_day(idx):
            # 處理再平衡/買入
            self._process_rebalance(idx, date_str)
            self._last_rebalance_idx = idx
        
        # 記錄權益
        equity = self._calculate_equity(idx)
        self.equity_curve.append({
            'date': date_str,
            'equity': equity,
            'cash': self.cash,
            'positions': len(self.positions),
        })
    
    def _update_peak_prices(self, idx: int):
        """更新持倉的峰值價格"""
        for symbol, pos in self.positions.items():
            current_price = self.close.iloc[idx].get(symbol, pos.peak_price)
            if current_price > pos.peak_price:
                pos.peak_price = current_price
    
    def _is_rebalance_day(self, idx: int) -> bool:
        """判斷是否為再平衡日"""
        freq = self.config.get('rebalance_freq', 'weekly')
        
        if freq == 'daily':
            return True
        elif freq == 'weekly':
            # 每週一（或該週第一個交易日）
            current_date = self.close.index[idx]
            if idx > 0:
                prev_date = self.close.index[idx - 1]
                return current_date.isocalendar()[1] != prev_date.isocalendar()[1]
            return True
        elif freq == 'monthly':
            current_date = self.close.index[idx]
            if idx > 0:
                prev_date = self.close.index[idx - 1]
                return current_date.month != prev_date.month
            return True
        return False
    
    def _select_stocks(self, idx: int) -> list[str]:
        """
        根據買入條件選擇股票
        """
        buy_cond = self.config['buy_conditions']
        candidates = []
        
        # 根據 TradingView 分類排除不可交易的標的
        all_symbols = [
            s for s in self.close.columns
            if self.stock_info.get(s, {}).get('industry') not in NON_TRADABLE_INDUSTRIES
        ]
        
        for symbol in all_symbols:
            if not self._check_buy_conditions(symbol, idx, buy_cond):
                continue
            
            sharpe = self.indicators.get_sharpe_value(symbol, idx)
            rank = self.indicators.get_rank_value(symbol, idx)
            growth = self.indicators.get_growth_value(symbol, idx)
            industry = self.stock_info.get(symbol, {}).get('industry', 'Unknown')
            
            candidates.append({
                'symbol': symbol,
                'sharpe': sharpe,
                'rank': rank,
                'growth': growth,
                'industry': industry,
            })
        
        # 排序
        if buy_cond.get('sort_industry', {}).get('enabled'):
            # 按產業分組，每產業取最高 Sharpe
            industry_best = {}
            for c in candidates:
                ind = c['industry']
                if ind not in industry_best or c['sharpe'] > industry_best[ind]['sharpe']:
                    industry_best[ind] = c
            candidates = list(industry_best.values())
        
        if buy_cond.get('sort_sharpe', {}).get('enabled'):
            candidates.sort(key=lambda x: x['sharpe'] or -999, reverse=True)
        
        return [c['symbol'] for c in candidates]
    
    def _check_buy_conditions(self, symbol: str, idx: int, buy_cond: dict) -> bool:
        """檢查買入條件"""
        # Sharpe Rank 條件
        if buy_cond.get('sharpe_rank', {}).get('enabled'):
            top_n = buy_cond['sharpe_rank'].get('top_n', 15)
            rank = self.indicators.get_rank_value(symbol, idx)
            if pd.isna(rank) or rank > top_n:
                return False
        
        # Sharpe Threshold 條件
        if buy_cond.get('sharpe_threshold', {}).get('enabled'):
            threshold = buy_cond['sharpe_threshold'].get('threshold', 1.0)
            sharpe = self.indicators.get_sharpe_value(symbol, idx)
            if pd.isna(sharpe) or sharpe < threshold:
                return False
        
        # Sharpe Streak 條件
        if buy_cond.get('sharpe_streak', {}).get('enabled'):
            days = buy_cond['sharpe_streak'].get('days', 3)
            top_n = buy_cond.get('sharpe_rank', {}).get('top_n', 15)
            if not self.indicators.check_sharpe_streak(symbol, idx, days, top_n):
                return False
        
        # Growth Streak 條件
        if buy_cond.get('growth_streak', {}).get('enabled'):
            days = buy_cond['growth_streak'].get('days', 2)
            if not self.indicators.check_growth_streak(symbol, idx, days):
                return False
        
        # Growth Rank 條件
        if buy_cond.get('growth_rank', {}).get('enabled'):
            top_k = buy_cond['growth_rank'].get('top_k', 7)
            growth = self.indicators.get_growth_value(symbol, idx)
            # 需要額外計算 growth rank
            growth_row = self.indicators.growth.iloc[idx]
            growth_rank = growth_row.rank(ascending=False, method='min').get(symbol, 999)
            if growth_rank > top_k:
                return False
        
        return True
    
    def _process_sell_signals(self, idx: int, date_str: str):
        """處理賣出訊號"""
        sell_cond = self.config['sell_conditions']
        to_sell = []
        
        # 取得今日選中的股票（用於 not_selected 條件）
        selected = set(self._select_stocks(idx))
        
        for symbol, pos in list(self.positions.items()):
            sell_reason = self._check_sell_conditions(
                symbol, idx, sell_cond, selected, pos
            )
            if sell_reason:
                to_sell.append((symbol, sell_reason))
        
        # 執行賣出
        for symbol, reason in to_sell:
            self._sell(symbol, idx, date_str, reason)
    
    def _check_sell_conditions(self, symbol: str, idx: int, 
                               sell_cond: dict, selected: set, 
                               pos: Position) -> Optional[str]:
        """
        檢查賣出條件
        
        Returns:
            賣出原因（None 表示不賣出）
        """
        # Sharpe Fail 條件
        if sell_cond.get('sharpe_fail', {}).get('enabled'):
            periods = sell_cond['sharpe_fail'].get('periods', 2)
            top_n = sell_cond['sharpe_fail'].get('top_n', 15)
            rank = self.indicators.get_rank_value(symbol, idx)
            
            if pd.isna(rank) or rank > top_n:
                self._sharpe_fail_counter[symbol] = self._sharpe_fail_counter.get(symbol, 0) + 1
            else:
                self._sharpe_fail_counter[symbol] = 0
            
            if self._sharpe_fail_counter.get(symbol, 0) >= periods:
                return f'sharpe_fail({periods})'
        
        # Growth Fail 條件
        if sell_cond.get('growth_fail', {}).get('enabled'):
            days = sell_cond['growth_fail'].get('days', 5)
            growth = self.indicators.get_growth_value(symbol, idx)
            
            if pd.isna(growth) or growth < 0:
                self._growth_fail_counter[symbol] = self._growth_fail_counter.get(symbol, 0) + 1
            else:
                self._growth_fail_counter[symbol] = 0
            
            if self._growth_fail_counter.get(symbol, 0) >= days:
                return f'growth_fail({days})'
        
        # Not Selected 條件
        if sell_cond.get('not_selected', {}).get('enabled'):
            periods = sell_cond['not_selected'].get('periods', 3)
            
            if symbol not in selected:
                self._not_selected_counter[symbol] = self._not_selected_counter.get(symbol, 0) + 1
            else:
                self._not_selected_counter[symbol] = 0
            
            if self._not_selected_counter.get(symbol, 0) >= periods:
                return f'not_selected({periods})'
        
        # Drawdown 條件
        if sell_cond.get('drawdown', {}).get('enabled'):
            threshold = sell_cond['drawdown'].get('threshold', 0.40)
            current_price = self.close.iloc[idx].get(symbol, pos.buy_price)
            peak_price = pos.peak_price or pos.buy_price
            
            if peak_price > 0:
                drawdown = (peak_price - current_price) / peak_price
                if drawdown >= threshold:
                    return f'drawdown({threshold:.0%})'
        
        # Weakness 條件
        if sell_cond.get('weakness', {}).get('enabled'):
            rank_k = sell_cond['weakness'].get('rank_k', 20)
            periods = sell_cond['weakness'].get('periods', 3)
            rank = self.indicators.get_rank_value(symbol, idx)
            
            if pd.isna(rank) or rank > rank_k:
                self._weakness_counter[symbol] = self._weakness_counter.get(symbol, 0) + 1
            else:
                self._weakness_counter[symbol] = 0
            
            if self._weakness_counter.get(symbol, 0) >= periods:
                return f'weakness({rank_k}, {periods})'
        
        return None
    
    def _process_rebalance(self, idx: int, date_str: str):
        """處理再平衡/買入"""
        strategy = self.config['rebalance_strategy']
        strategy_type = strategy.get('type', 'delayed')
        
        # 取得候選股票
        candidates = self._select_stocks(idx)
        
        # 根據策略處理
        if strategy_type == 'none':
            # 不進行再平衡，只買新股
            self._buy_new_positions(candidates, idx, date_str)
            
        elif strategy_type == 'immediate':
            # 立即賣出非候選股票
            for symbol in list(self.positions.keys()):
                if symbol not in candidates:
                    self._sell(symbol, idx, date_str, 'rebalance_immediate')
            self._buy_new_positions(candidates, idx, date_str)
            
        elif strategy_type == 'batch':
            # 批次賣出
            batch_ratio = strategy.get('batch_ratio', 0.20)
            non_candidates = [s for s in self.positions if s not in candidates]
            n_sell = max(1, int(len(non_candidates) * batch_ratio))
            
            # 賣出排名最差的
            ranked = sorted(non_candidates, 
                          key=lambda s: self.indicators.get_rank_value(s, idx) or 999,
                          reverse=True)
            for symbol in ranked[:n_sell]:
                self._sell(symbol, idx, date_str, 'rebalance_batch')
            
            self._buy_new_positions(candidates, idx, date_str)
            
        elif strategy_type == 'delayed':
            # 延遲再平衡：只有在市場條件良好時才買入
            # 檢查市場強度：至少有足夠的高 Sharpe 股票
            top_n = self.config['buy_conditions'].get('sharpe_rank', {}).get('top_n', 15)
            threshold = self.config['buy_conditions'].get('sharpe_threshold', {}).get('threshold', 1.0)
            
            # 計算高 Sharpe 股票數量
            high_sharpe_count = 0
            for symbol in self.close.columns:
                sharpe = self.indicators.get_sharpe_value(symbol, idx)
                if not pd.isna(sharpe) and sharpe >= threshold:
                    high_sharpe_count += 1
            
            # 如果高 Sharpe 股票足夠，進行買入
            if high_sharpe_count >= top_n // 2:
                self._buy_new_positions(candidates, idx, date_str)
            else:
                logger.debug(f"{date_str}: Delayed rebalance - market weak ({high_sharpe_count} high sharpe stocks)")
            
        elif strategy_type == 'concentrated':
            # 集中投資：只持有 Top K
            top_k = strategy.get('concentrate_top_k', 3)
            top_candidates = candidates[:top_k]
            
            # 賣出不在 Top K 的
            for symbol in list(self.positions.keys()):
                if symbol not in top_candidates:
                    self._sell(symbol, idx, date_str, 'rebalance_concentrated')
            
            self._buy_new_positions(top_candidates, idx, date_str)
    
    def _buy_new_positions(self, candidates: list, idx: int, date_str: str):
        """買入新持倉"""
        max_positions = self.config['max_positions']
        amount_per_stock = self.config['amount_per_stock']
        
        current_positions = len(self.positions)
        slots_available = max_positions - current_positions
        
        for symbol in candidates:
            if slots_available <= 0:
                break
            if symbol in self.positions:
                continue
            if self.cash < amount_per_stock:
                break
            
            price = self.close.iloc[idx].get(symbol)
            if pd.isna(price) or price <= 0:
                continue
            
            # 計算股數
            shares = int(amount_per_stock / price)
            if shares <= 0:
                continue
            
            # 計算費用
            market = self._get_market(symbol)
            fee = self._calculate_fee(shares * price, market)
            
            # 執行買入
            cost = shares * price + fee
            if cost > self.cash:
                continue
            
            self.cash -= cost
            self.positions[symbol] = Position(
                symbol=symbol,
                shares=shares,
                avg_cost=price,
                buy_date=date_str,
                buy_price=price,
                peak_price=price,
            )
            
            self.trades.append(Trade(
                date=date_str,
                symbol=symbol,
                type=TradeType.BUY,
                shares=shares,
                price=price,
                amount=shares * price,
                fee=fee,
                reason='buy',
            ))
            
            slots_available -= 1
    
    def _sell(self, symbol: str, idx: int, date_str: str, reason: str):
        """賣出持倉"""
        if symbol not in self.positions:
            return
        
        pos = self.positions[symbol]
        price = self.close.iloc[idx].get(symbol, pos.avg_cost)
        amount = pos.shares * price
        
        # 計算費用
        market = self._get_market(symbol)
        fee = self._calculate_fee(amount, market)
        
        # 執行賣出
        self.cash += amount - fee
        del self.positions[symbol]
        
        # 清除計數器
        self._sharpe_fail_counter.pop(symbol, None)
        self._not_selected_counter.pop(symbol, None)
        self._weakness_counter.pop(symbol, None)
        self._growth_fail_counter.pop(symbol, None)
        
        self.trades.append(Trade(
            date=date_str,
            symbol=symbol,
            type=TradeType.SELL,
            shares=pos.shares,
            price=price,
            amount=amount,
            fee=fee,
            reason=reason,
        ))
    
    def _get_market(self, symbol: str) -> str:
        """判斷市場"""
        info = self.stock_info.get(symbol, {})
        country = info.get('country', 'US')
        return 'tw' if country == 'TW' else 'us'
    
    def _calculate_fee(self, amount: float, market: str) -> float:
        """計算手續費"""
        fee_config = FEES.get(market, FEES['us'])
        fee = amount * fee_config['rate']
        return max(fee, fee_config['min_fee'])
    
    def _calculate_equity(self, idx: int) -> float:
        """計算總權益"""
        equity = self.cash
        for symbol, pos in self.positions.items():
            price = self.close.iloc[idx].get(symbol, pos.avg_cost)
            equity += pos.shares * price
        return equity
    
    def _calculate_result(self, start_idx: int, end_idx: int) -> BacktestResult:
        """計算回測結果"""
        initial = self.config['initial_capital']
        final = self._calculate_equity(end_idx)
        
        # 總報酬
        total_return = (final - initial) / initial
        
        # 年化報酬
        days = end_idx - start_idx + 1
        years = days / 252
        annualized = (1 + total_return) ** (1 / years) - 1 if years > 0 else 0
        
        # 勝率
        win_trades = 0
        loss_trades = 0
        for i, trade in enumerate(self.trades):
            if trade.type == TradeType.SELL:
                # 找對應的買入
                buy_trade = None
                for j in range(i - 1, -1, -1):
                    if self.trades[j].symbol == trade.symbol and self.trades[j].type == TradeType.BUY:
                        buy_trade = self.trades[j]
                        break
                if buy_trade:
                    profit = trade.amount - trade.fee - buy_trade.amount - buy_trade.fee
                    if profit > 0:
                        win_trades += 1
                    else:
                        loss_trades += 1
        
        total_trades = win_trades + loss_trades
        win_rate = win_trades / total_trades if total_trades > 0 else 0
        
        # 最大回撤
        max_equity = initial
        max_drawdown = 0
        for point in self.equity_curve:
            if point['equity'] > max_equity:
                max_equity = point['equity']
            dd = (max_equity - point['equity']) / max_equity
            if dd > max_drawdown:
                max_drawdown = dd
        
        # 策略 Sharpe（簡化版）
        if len(self.equity_curve) > 1:
            equities = [p['equity'] for p in self.equity_curve]
            returns = np.diff(equities) / equities[:-1]
            sharpe = np.mean(returns) / np.std(returns) * np.sqrt(252) if np.std(returns) > 0 else 0
        else:
            sharpe = 0
        
        return BacktestResult(
            initial_capital=initial,
            final_equity=final,
            total_return=total_return,
            annualized_return=annualized,
            total_trades=len(self.trades),
            win_trades=win_trades,
            loss_trades=loss_trades,
            win_rate=win_rate,
            max_drawdown=max_drawdown,
            sharpe_ratio=sharpe,
            trades=[t.to_dict() for t in self.trades],
            equity_curve=self.equity_curve,
        )
