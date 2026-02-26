"""
回測引擎模組

支援買賣條件、再平衡策略、績效計算

幣別處理：
- 所有資金以 TWD 為準（使用 Money 類型）
- 美股價格為 USD，需根據當日匯率轉換
- 台股價格為 TWD
"""
import logging
import pandas as pd
import numpy as np
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Union
from enum import Enum

from core.config import FEES, NON_TRADABLE_INDUSTRIES
from core.indicator import Indicators
from core.currency import Money, Currency, twd, usd, FX

logger = logging.getLogger(__name__)


class TradeType(Enum):
    BUY = 'buy'
    SELL = 'sell'


@dataclass
class Trade:
    """
    交易紀錄
    
    金額欄位使用 Money 類型確保幣別安全。
    """
    date: str
    symbol: str
    type: TradeType
    shares: int
    price: Money           # 成交價（原始幣別）
    amount: Money          # 成交金額（原始幣別）
    amount_twd: Money      # 成交金額（TWD，用於統計）
    fee: Money             # 手續費（TWD）
    reason: str = ''
    profit: Money = field(default_factory=lambda: twd(0))  # 損益（TWD）
    
    def to_dict(self) -> dict:
        return {
            'date': self.date,
            'symbol': self.symbol,
            'type': self.type.value,
            'shares': self.shares,
            'price': str(self.price),
            'amount': str(self.amount),
            'amount_twd': f"${self.amount_twd.amount:,.0f}",
            'fee': f"${self.fee.amount:,.0f}",
            'reason': self.reason,
            'profit': f"${self.profit.amount:+,.0f}" if self.profit.amount != 0 else '',
        }


@dataclass
class Position:
    """
    持倉
    
    - avg_cost: 平均成本（原始幣別，美股為 USD，台股為 TWD）
    - cost_basis: 成本基礎（TWD，用於計算損益）
    """
    symbol: str
    shares: int
    avg_cost: Money        # 每股成本（原始幣別）
    cost_basis: Money      # 總成本（TWD）
    buy_date: str
    buy_price: Money       # 買入價（原始幣別）
    peak_price: float = 0.0  # 最高價（原始幣別數值，用於回撤計算）
    country: str = 'US'


@dataclass
class BacktestResult:
    """
    回測結果
    
    金額使用 Money 類型（TWD）。
    """
    initial_capital: Money   # TWD
    final_equity: Money      # TWD
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
            'initial_capital': str(self.initial_capital),
            'final_equity': str(self.final_equity),
            'total_return': f"{self.total_return:.2%}",
            'annualized_return': f"{self.annualized_return:.2%}",
            'total_trades': self.total_trades,
            'win_trades': self.win_trades,
            'loss_trades': self.loss_trades,
            'win_rate': f"{self.win_rate:.2%}",
            'max_drawdown': f"{self.max_drawdown:.2%}",
            'sharpe_ratio': round(self.sharpe_ratio, 2),
        }


class BacktestEngine:
    """
    回測引擎
    
    所有資金以 TWD 為單位，使用 Money 類型確保幣別安全。
    美股交易會根據當日匯率轉換。
    
    Args:
        close_df: 對齊後的收盤價 DataFrame [Date x Symbol]
        indicators: 指標計算器
        stock_info: 股票資訊 {symbol: {industry, country, ...}}
        config: 回測配置
        fx: 匯率服務（用於 USD/TWD 轉換）
    """
    
    def __init__(self, 
                 close_df: pd.DataFrame,
                 indicators: Indicators,
                 stock_info: dict,
                 config: dict,
                 fx: Optional[FX] = None):
        """
        Args:
            close_df: 對齊後的收盤價 DataFrame
            indicators: Indicators 實例
            stock_info: 股票資訊
            config: 回測配置（必填，由 run.py 傳入）
            fx: 匯率服務（選填）
        """
        if config is None:
            raise ValueError("config 參數必填，請從 run.py 傳入回測配置")
        
        self.close = close_df
        self.indicators = indicators
        self.stock_info = stock_info
        self.config = config
        self.fx = fx or FX()
        
        # 狀態 - 使用 Money 類型
        initial_capital = self.config['initial_capital']
        if isinstance(initial_capital, Money):
            self.cash: Money = initial_capital
        else:
            self.cash: Money = twd(initial_capital)
        
        self.positions: Dict[str, Position] = {}
        self.trades: List[Trade] = []
        self.equity_curve: List[dict] = []
        
        # 計數器
        self._sharpe_fail_counter: Dict[str, int] = {}
        self._growth_fail_counter: Dict[str, int] = {}
        self._not_selected_counter: Dict[str, int] = {}
        self._weakness_counter: Dict[str, int] = {}
    
    def run(self, start_date=None, end_date=None) -> BacktestResult:
        """執行回測
        
        Args:
            start_date: 開始日期（必填，由 run.py 傳入）
            end_date: 結束日期（必填，由 run.py 傳入）
        """
        if start_date is None or end_date is None:
            raise ValueError("start_date 與 end_date 必填，請從 run.py 傳入")
        
        date_index = self.close.index
        start_idx = date_index.searchsorted(start_date)
        end_idx = date_index.searchsorted(end_date, side='right') - 1
        
        logger.info(f"回測: {date_index[start_idx].date()} ~ {date_index[end_idx].date()}")
        
        for idx in range(start_idx, end_idx + 1):
            self._process_day(idx)
        
        return self._calculate_result(start_idx, end_idx)
    
    def _process_day(self, idx: int):
        """處理單一交易日（與前端 Engine._step 一致）
        
        前端每天流程：
        1. _processSellSignals - 賣出
        2. _selectStocks - 選股
        3. _processRebalance - 再平衡買入（策略決定是否執行）
        4. _processBuySignals - 繼續買入直到滿倉
        
        每天結束記錄完整的持有狀況，供前端點擊權益曲線查看。
        """
        date_str = self.close.index[idx].strftime('%Y-%m-%d')
        self._update_peaks(idx)
        self._process_sells(idx, date_str)
        
        # 每天都嘗試買入（與前端一致）
        # 策略自己決定是否/如何買入
        self._process_rebalance(idx, date_str)
        
        # 計算當日總權益與持倉快照
        equity, holdings_value, holdings_snapshot = self._calc_equity_with_holdings(idx)
        self.equity_curve.append({
            'date': date_str,
            'equity': equity.amount,           # 總資產 (TWD)
            'cash': self.cash.amount,          # 現金 (TWD)
            'holdingsValue': holdings_value,   # 持股市值 (TWD)
            'holdings': holdings_snapshot      # 各持股詳情
        })
    
    def _update_peaks(self, idx: int):
        """更新持倉峰值"""
        for sym, pos in self.positions.items():
            price = self.close.iloc[idx].get(sym, pos.peak_price)
            if price > pos.peak_price:
                pos.peak_price = price
    
    def _is_rebalance_day(self, idx: int) -> bool:
        """判斷是否為再平衡日"""
        freq = self.config.get('rebalance_freq', 'weekly')
        if freq == 'daily':
            return True
        elif freq == 'weekly':
            if idx > 0:
                curr = self.close.index[idx]
                prev = self.close.index[idx - 1]
                return curr.isocalendar()[1] != prev.isocalendar()[1]
            return True
        elif freq == 'monthly':
            if idx > 0:
                return self.close.index[idx].month != self.close.index[idx - 1].month
            return True
        return False
    
    def _select_stocks(self, idx: int) -> List[str]:
        """根據買入條件選擇股票"""
        buy_cond = self.config['buy_conditions']
        candidates = []
        
        for symbol in self.close.columns:
            industry = self.stock_info.get(symbol, {}).get('industry', '')
            if industry in NON_TRADABLE_INDUSTRIES:
                continue
            if not self._check_buy(symbol, idx, buy_cond):
                continue
            
            candidates.append({
                'symbol': symbol,
                'sharpe': self.indicators.get_sharpe(symbol, idx),
                'industry': self.stock_info.get(symbol, {}).get('industry', 'Unknown'),
            })
        
        # 產業分散（與前端 sort_industry.js 邏輯一致）
        if buy_cond.get('sort_industry', {}).get('enabled'):
            per_industry = buy_cond['sort_industry'].get('per_industry', 2)
            
            # 按產業分組
            industry_groups = {}
            for c in candidates:
                ind = c['industry']
                if ind not in industry_groups:
                    industry_groups[ind] = []
                industry_groups[ind].append(c)
            
            # 每個產業按 Sharpe 排序
            for ind in industry_groups:
                industry_groups[ind].sort(
                    key=lambda x: x['sharpe'] if x['sharpe'] is not None else -999, 
                    reverse=True
                )
            
            # 按產業內最高 Sharpe 排序產業順序
            industries = sorted(
                industry_groups.keys(),
                key=lambda i: (industry_groups[i][0]['sharpe'] 
                              if industry_groups[i][0]['sharpe'] is not None else -999),
                reverse=True
            )
            
            # 輪流從每個產業選取（Round-Robin）
            selected = []
            industry_count = {}
            has_more = True
            max_rounds = per_industry * len(industries) + 1  # 安全限制
            round_count = 0
            
            while has_more and round_count < max_rounds:
                has_more = False
                for ind in industries:
                    count = industry_count.get(ind, 0)
                    if count >= per_industry:
                        continue
                    if count < len(industry_groups[ind]):
                        selected.append(industry_groups[ind][count])
                        industry_count[ind] = count + 1
                        has_more = True
                round_count += 1
            
            candidates = selected
        
        # 排序（如果 sort_industry 和 sort_sharpe 都啟用，則以最後一個為準，與前端一致）
        elif buy_cond.get('sort_sharpe', {}).get('enabled'):
            candidates.sort(key=lambda x: x['sharpe'] if x['sharpe'] is not None else -999, reverse=True)
        
        return [c['symbol'] for c in candidates]
    
    def _check_buy(self, symbol: str, idx: int, buy_cond: dict) -> bool:
        """檢查買入條件"""
        date_str = self.close.index[idx].strftime('%Y-%m-%d')
        country = self.stock_info.get(symbol, {}).get('country', 'US')
        
        if buy_cond.get('sharpe_rank', {}).get('enabled'):
            top_n = buy_cond['sharpe_rank'].get('top_n', 15)
            if not self.indicators.check_in_sharpe_top_k(symbol, date_str, country, top_n):
                return False
        
        if buy_cond.get('sharpe_threshold', {}).get('enabled'):
            threshold = buy_cond['sharpe_threshold'].get('threshold', 0.5)
            sharpe = self.indicators.get_sharpe(symbol, idx)
            if pd.isna(sharpe) or sharpe < threshold:
                return False
        
        if buy_cond.get('sharpe_streak', {}).get('enabled'):
            days = buy_cond['sharpe_streak'].get('days', 3)
            top_n = buy_cond['sharpe_streak'].get('top_n', 15)  # 使用自己的 top_n（與 JS 一致）
            if not self.indicators.check_sharpe_streak(symbol, idx, days, top_n):
                return False
        
        if buy_cond.get('growth_streak', {}).get('enabled'):
            days = buy_cond['growth_streak'].get('days', 3)
            percentile = buy_cond['growth_streak'].get('percentile', 50)
            if not self.indicators.check_growth_streak(symbol, idx, days, percentile):
                return False
        
        # growth_rank: 檢查股票是否在 Growth 排名前 N 名（與 JS growth_rank.js 一致）
        if buy_cond.get('growth_rank', {}).get('enabled'):
            top_n = buy_cond['growth_rank'].get('top_n', 15)
            if not self.indicators.check_in_growth_top_k(symbol, date_str, country, top_n):
                return False
        
        return True
    
    def _process_sells(self, idx: int, date_str: str):
        """處理賣出訊號"""
        sell_cond = self.config['sell_conditions']
        selected = set(self._select_stocks(idx))
        to_sell = []
        
        for symbol, pos in list(self.positions.items()):
            reason = self._check_sell(symbol, idx, sell_cond, selected, pos)
            if reason:
                to_sell.append((symbol, reason))
        
        for symbol, reason in to_sell:
            self._sell(symbol, idx, date_str, reason)
    
    def _check_sell(self, symbol: str, idx: int, sell_cond: dict,
                    selected: set, pos: Position) -> Optional[str]:
        """檢查賣出條件"""
        date_str = self.close.index[idx].strftime('%Y-%m-%d')
        country = self.stock_info.get(symbol, {}).get('country', 'US')
        
        # Sharpe 失敗
        if sell_cond.get('sharpe_fail', {}).get('enabled'):
            periods = sell_cond['sharpe_fail'].get('periods', 3)
            top_n = sell_cond['sharpe_fail'].get('top_n', 15)
            in_top_k = self.indicators.check_in_sharpe_top_k(symbol, date_str, country, top_n)
            if not in_top_k:
                self._sharpe_fail_counter[symbol] = self._sharpe_fail_counter.get(symbol, 0) + 1
            else:
                self._sharpe_fail_counter[symbol] = 0
            if self._sharpe_fail_counter.get(symbol, 0) >= periods:
                return f'sharpe_fail({periods})'
        
        # Growth 失敗（與 JS growth_fail.js 一致：計算最近 N 天 Growth 平均值）
        if sell_cond.get('growth_fail', {}).get('enabled'):
            days = sell_cond['growth_fail'].get('days', 5)
            threshold = sell_cond['growth_fail'].get('threshold', 0)
            
            # 計算最近 days 天的 Growth 平均值
            growth_values = []
            for i in range(days):
                check_idx = idx - i
                if check_idx >= 0:
                    g = self.indicators.get_growth(symbol, check_idx)
                    if not pd.isna(g):
                        growth_values.append(g)
            
            if growth_values:
                avg_growth = sum(growth_values) / len(growth_values)
                if avg_growth < threshold:
                    return f'growth_fail({days}d avg={avg_growth:.3f})'
        
        # 未被選中
        if sell_cond.get('not_selected', {}).get('enabled'):
            periods = sell_cond['not_selected'].get('periods', 3)
            if symbol not in selected:
                self._not_selected_counter[symbol] = self._not_selected_counter.get(symbol, 0) + 1
            else:
                self._not_selected_counter[symbol] = 0
            if self._not_selected_counter.get(symbol, 0) >= periods:
                return f'not_selected({periods})'
        
        # 回撤
        if sell_cond.get('drawdown', {}).get('enabled'):
            threshold = sell_cond['drawdown'].get('threshold', 0.40)
            from_highest = sell_cond['drawdown'].get('from_highest', False)  # 預設從買入價計算
            price = self.close.iloc[idx].get(symbol, pos.buy_price.amount)
            
            # 根據設定決定基準價（使用原始幣別的數值）
            if from_highest:
                reference_price = pos.peak_price or pos.buy_price.amount
            else:
                reference_price = pos.buy_price.amount
            
            if reference_price > 0 and (reference_price - price) / reference_price >= threshold:
                return f'drawdown({threshold:.0%})'
        
        # 弱勢（與 JS weakness.js 一致：Sharpe rank > K AND Growth rank > K 連續 M 期）
        if sell_cond.get('weakness', {}).get('enabled'):
            rank_k = sell_cond['weakness'].get('rank_k', 20)
            periods = sell_cond['weakness'].get('periods', 3)
            
            # 取得 Sharpe 和 Growth 排名位置
            sharpe_pos = self.indicators.get_sharpe_rank_position(symbol, date_str, country)
            growth_pos = self.indicators.get_growth_rank_position(symbol, date_str, country)
            
            # 必須同時滿足 Sharpe 和 Growth 排名都超過門檻
            sharpe_bad = sharpe_pos < 0 or sharpe_pos >= rank_k
            growth_bad = growth_pos < 0 or growth_pos >= rank_k
            
            if sharpe_bad and growth_bad:
                self._weakness_counter[symbol] = self._weakness_counter.get(symbol, 0) + 1
            else:
                self._weakness_counter[symbol] = 0
            
            if self._weakness_counter.get(symbol, 0) >= periods:
                return f'weakness(sharpe>{rank_k} & growth>{rank_k}, {periods}期)'
        
        return None
    
    def _process_rebalance(self, idx: int, date_str: str):
        """
        處理再平衡（與前端一致）
        
        所有金額使用 Money 類型，確保幣別安全。
        """
        strategy = self.config['rebalance_strategy']
        stype = strategy.get('type', 'batch')
        candidates = self._select_stocks(idx)
        
        # 找出需要買入的（在候選中但未持有）
        to_buy = [s for s in candidates if s not in self.positions]
        
        if not to_buy:
            return
        
        max_pos = self.config['max_positions']
        slots = max_pos - len(self.positions)
        
        if slots <= 0:
            return
        
        # 限制買入數量
        to_buy = to_buy[:slots]
        
        if stype == 'batch':
            # 分批投入：用現金的固定比例買入（Money / n = Money）
            ratio = strategy.get('batch_ratio', 0.20)
            invest_amount: Money = self.cash * ratio
            amount_per_stock: Money = invest_amount / len(to_buy) if to_buy else twd(0)
            self._buy_stocks(to_buy, idx, date_str, amount_per_stock)
            
        elif stype == 'immediate':
            # 立即投入：用固定金額買入
            amount_per_stock = self._get_amount_per_stock()
            self._buy_stocks(to_buy, idx, date_str, amount_per_stock)
            
        elif stype == 'concentrated':
            # 集中投資：只在前 K 名有明確領先時才買入（與 JS concentrated.js 一致）
            top_k = strategy.get('concentrate_top_k', 3)
            lead_margin = strategy.get('lead_margin', 0.3)  # 領先差距門檻
            market = self.config.get('market', 'us')
            
            # 取得 Top-K 和 Next-K (K+1~2K) 股票的 Sharpe 平均值
            top_k_tickers = []
            next_k_tickers = []
            
            if market in ('global', 'us'):
                us_ranking = self.indicators.sharpe_rank_by_country.get(date_str, {}).get('US', [])
                top_k_tickers.extend(us_ranking[:top_k])
                next_k_tickers.extend(us_ranking[top_k:top_k*2])
            
            if market in ('global', 'tw'):
                tw_ranking = self.indicators.sharpe_rank_by_country.get(date_str, {}).get('TW', [])
                top_k_tickers.extend(tw_ranking[:top_k])
                next_k_tickers.extend(tw_ranking[top_k:top_k*2])
            
            # 計算平均 Sharpe
            def avg_sharpe(tickers):
                values = []
                for t in tickers:
                    s = self.indicators.get_sharpe(t, idx)
                    if not pd.isna(s):
                        values.append(s)
                return sum(values) / len(values) if values else 0
            
            top_k_avg = avg_sharpe(top_k_tickers)
            next_k_avg = avg_sharpe(next_k_tickers)
            
            # 領先判斷邏輯（與 JS 一致）
            should_invest = False
            if next_k_avg <= 0 and top_k_avg > 0:
                # Next-K 平均 <= 0 且 Top-K > 0，視為領先
                should_invest = True
            elif next_k_avg > 0:
                # 檢查領先差距
                lead_ratio = (top_k_avg - next_k_avg) / abs(next_k_avg)
                if lead_ratio >= lead_margin:
                    should_invest = True
            
            if not should_invest:
                return  # 未明確領先，不買
            
            to_buy = to_buy[:top_k]
            amount_per_stock = self._get_amount_per_stock()
            self._buy_stocks(to_buy, idx, date_str, amount_per_stock)
            
        elif stype == 'delayed':
            # 延遲投入：等市場轉強再進場（與 JS delayed.js 一致）
            # 計算 Sharpe Top-N 的平均值，只有平均 > 門檻時才買入
            top_n = strategy.get('top_n', 5)
            sharpe_threshold = strategy.get('sharpe_threshold', 0)
            
            # 取得當日 Sharpe Top-N 股票
            top_sharpe_values = []
            market = self.config.get('market', 'us')
            
            if market in ('global', 'us'):
                us_ranking = self.indicators.sharpe_rank_by_country.get(date_str, {}).get('US', [])
                for s in us_ranking[:top_n]:
                    sharpe = self.indicators.get_sharpe(s, idx)
                    if not pd.isna(sharpe):
                        top_sharpe_values.append(sharpe)
            
            if market in ('global', 'tw'):
                tw_ranking = self.indicators.sharpe_rank_by_country.get(date_str, {}).get('TW', [])
                for s in tw_ranking[:top_n]:
                    sharpe = self.indicators.get_sharpe(s, idx)
                    if not pd.isna(sharpe):
                        top_sharpe_values.append(sharpe)
            
            # 計算平均 Sharpe
            avg_sharpe = sum(top_sharpe_values) / len(top_sharpe_values) if top_sharpe_values else 0
            
            # 只在市場轉強時買入（平均 Sharpe > 門檻）
            if avg_sharpe <= sharpe_threshold:
                return  # 市場未轉強，不買
            
            amount_per_stock = self._get_amount_per_stock()
            self._buy_stocks(to_buy, idx, date_str, amount_per_stock)
        
        else:
            # 預設：none - 不主動再平衡，只靠賣出條件
            pass
    
    def _get_amount_per_stock(self) -> Money:
        """取得每檔投入金額（確保為 Money 類型）"""
        amt = self.config['amount_per_stock']
        if isinstance(amt, Money):
            return amt
        return twd(amt)
    
    def _buy_stocks(self, symbols: list, idx: int, date_str: str, amount_per_stock: Money):
        """
        買入一組股票
        
        Args:
            symbols: 要買入的股票代碼
            idx: 日期索引
            date_str: 日期字串
            amount_per_stock: 每檔投入金額 (Money, TWD)
        """
        # 確保是 Money 類型
        if not isinstance(amount_per_stock, Money):
            amount_per_stock = twd(amount_per_stock)
        
        half_amount = amount_per_stock * 0.5
        
        for symbol in symbols:
            if self.cash < half_amount:  # 現金不足一半就停止
                break
            if symbol in self.positions:
                continue
            
            price_raw = self.close.iloc[idx].get(symbol)
            if pd.isna(price_raw) or price_raw <= 0:
                continue
            
            country = self.stock_info.get(symbol, {}).get('country', 'US')
            is_us = country != 'TW'
            
            # 建立價格 Money 物件
            if is_us:
                price_money = usd(price_raw)
                # 將 TWD 預算轉換為 USD
                budget_usd = self.fx.to_usd(amount_per_stock, date_str)
                # 計算可買股數
                shares = int(budget_usd.amount / price_raw)
            else:
                price_money = twd(price_raw)
                # 台股直接用 TWD 計算
                shares = int(amount_per_stock.amount / price_raw)
            
            if shares <= 0:
                continue
            
            # 計算成本（使用原始幣別）
            if is_us:
                amount_original = usd(shares * price_raw)
                amount_twd = self.fx.to_twd(amount_original, date_str)
            else:
                amount_original = twd(shares * price_raw)
                amount_twd = amount_original
            
            # 計算手續費（TWD）
            fee_cfg = FEES.get('us' if is_us else 'tw', FEES['us'])
            fee_value = max(amount_twd.amount * fee_cfg['rate'], fee_cfg['min_fee'])
            fee = twd(fee_value)
            
            # 總成本（TWD）
            total_cost = amount_twd + fee
            
            if total_cost > self.cash:
                continue
            
            # 扣除現金
            self.cash = self.cash - total_cost
            
            # 建立持倉
            self.positions[symbol] = Position(
                symbol=symbol, 
                shares=shares, 
                avg_cost=price_money,
                cost_basis=total_cost,
                buy_date=date_str, 
                buy_price=price_money, 
                peak_price=price_raw,
                country=country
            )
            
            # 記錄交易
            self.trades.append(Trade(
                date=date_str, 
                symbol=symbol, 
                type=TradeType.BUY,
                shares=shares, 
                price=price_money, 
                amount=amount_original, 
                amount_twd=amount_twd,
                fee=fee, 
                reason='buy'
            ))
    
    def _sell(self, symbol: str, idx: int, date_str: str, reason: str):
        """
        賣出持倉
        
        所有金額使用 Money 類型，根據股票國家處理匯率。
        """
        if symbol not in self.positions:
            return
        
        pos = self.positions[symbol]
        price_raw = self.close.iloc[idx].get(symbol, pos.avg_cost.amount)
        
        country = pos.country
        is_us = country != 'TW'
        
        # 建立價格和金額 Money 物件
        if is_us:
            price_money = usd(price_raw)
            amount_original = usd(pos.shares * price_raw)
            amount_twd = self.fx.to_twd(amount_original, date_str)
        else:
            price_money = twd(price_raw)
            amount_original = twd(pos.shares * price_raw)
            amount_twd = amount_original
        
        # 計算手續費（TWD）
        fee_cfg = FEES.get('us' if is_us else 'tw', FEES['us'])
        fee_value = max(amount_twd.amount * fee_cfg['rate'], fee_cfg['min_fee'])
        fee = twd(fee_value)
        
        # 計算損益（TWD）
        cost_basis = pos.cost_basis  # Money (TWD)
        profit = amount_twd - cost_basis - fee
        
        # 更新現金（TWD）
        self.cash = self.cash + amount_twd - fee
        del self.positions[symbol]
        
        # 清除計數器
        for counter in [self._sharpe_fail_counter, self._growth_fail_counter,
                       self._not_selected_counter, self._weakness_counter]:
            counter.pop(symbol, None)
        
        self.trades.append(Trade(
            date=date_str, 
            symbol=symbol, 
            type=TradeType.SELL,
            shares=pos.shares, 
            price=price_money, 
            amount=amount_original, 
            amount_twd=amount_twd,
            fee=fee, 
            reason=reason, 
            profit=profit
        ))
    
    def _calc_equity(self, idx: int) -> Money:
        """
        計算總權益（TWD）
        
        現金 + 各持倉市值（統一轉為 TWD）
        """
        date_str = self.close.index[idx].strftime('%Y-%m-%d')
        equity = self.cash  # Money (TWD)
        
        for sym, pos in self.positions.items():
            price_raw = self.close.iloc[idx].get(sym, pos.avg_cost.amount)
            
            if pos.country != 'TW':
                # 美股：轉換為 TWD
                market_value_usd = usd(pos.shares * price_raw)
                market_value_twd = self.fx.to_twd(market_value_usd, date_str)
            else:
                # 台股：直接是 TWD
                market_value_twd = twd(pos.shares * price_raw)
            
            equity = equity + market_value_twd
        
        return equity
    
    def _calc_equity_with_holdings(self, idx: int) -> tuple:
        """
        計算總權益並取得每個持倉的詳細資訊
        
        Returns:
            tuple: (equity: Money, holdings_value: float, holdings_snapshot: dict)
                - equity: 總權益 (TWD)
                - holdings_value: 持股市值 (TWD)
                - holdings_snapshot: 各持股詳情 {symbol: {...}}
        
        供前端點擊權益曲線查看當日持有狀況。
        """
        date_str = self.close.index[idx].strftime('%Y-%m-%d')
        equity = self.cash  # Money (TWD)
        holdings_value = 0.0
        holdings_snapshot = {}
        
        for sym, pos in self.positions.items():
            price_raw = self.close.iloc[idx].get(sym, pos.avg_cost.amount)
            
            if pos.country != 'TW':
                # 美股：轉換為 TWD
                market_value_usd = usd(pos.shares * price_raw)
                market_value_twd = self.fx.to_twd(market_value_usd, date_str)
            else:
                # 台股：直接是 TWD
                market_value_twd = twd(pos.shares * price_raw)
            
            equity = equity + market_value_twd
            holdings_value += market_value_twd.amount
            
            # 計算損益百分比
            cost_basis = pos.cost_basis.amount
            pnl_pct = (market_value_twd.amount - cost_basis) / cost_basis if cost_basis > 0 else 0
            
            # 取得股票資訊
            info = self.stock_info.get(sym, {})
            
            holdings_snapshot[sym] = {
                'shares': pos.shares,
                'avgCost': round(pos.avg_cost.amount, 2),
                'currentPrice': round(price_raw, 2),
                'marketValue': round(market_value_twd.amount, 0),
                'pnlPct': round(pnl_pct * 100, 2),
                'buyDate': pos.buy_date,
                'industry': info.get('industry', 'Unknown'),
                'country': pos.country
            }
        
        return equity, holdings_value, holdings_snapshot
    
    def _calculate_result(self, start_idx: int, end_idx: int) -> BacktestResult:
        """
        計算回測結果
        
        所有金額使用 Money 類型（TWD）。
        """
        # 取得初始資金（確保為 Money）
        initial_config = self.config['initial_capital']
        if isinstance(initial_config, Money):
            initial = initial_config
        else:
            initial = twd(initial_config)
        
        final = self._calc_equity(end_idx)  # Money (TWD)
        
        # 計算報酬率（Money / Money = float）
        total_return = (final.amount - initial.amount) / initial.amount
        
        days = end_idx - start_idx + 1
        years = days / 252
        annualized = (1 + total_return) ** (1 / years) - 1 if years > 0 else 0
        
        # 勝率
        sells = [t for t in self.trades if t.type == TradeType.SELL]
        win_trades = sum(1 for t in sells if t.profit.amount > 0)
        loss_trades = sum(1 for t in sells if t.profit.amount <= 0)
        total = len(sells)
        win_rate = win_trades / total if total > 0 else 0
        
        # 最大回撤（使用 equity_curve 中的 float 值）
        max_eq = initial.amount
        max_dd = 0
        for p in self.equity_curve:
            eq = p['equity']
            if eq > max_eq:
                max_eq = eq
            dd = (max_eq - eq) / max_eq if max_eq > 0 else 0
            if dd > max_dd:
                max_dd = dd
        
        # Sharpe
        if len(self.equity_curve) > 1:
            eqs = [p['equity'] for p in self.equity_curve]
            rets = np.diff(eqs) / np.array(eqs[:-1])
            sharpe = np.mean(rets) / np.std(rets) * np.sqrt(252) if np.std(rets) > 0 else 0
        else:
            sharpe = 0
        
        return BacktestResult(
            initial_capital=initial,  # Money (TWD)
            final_equity=final,       # Money (TWD)
            total_return=total_return, 
            annualized_return=annualized,
            total_trades=len(self.trades), 
            win_trades=win_trades, 
            loss_trades=loss_trades, 
            win_rate=win_rate, 
            max_drawdown=max_dd, 
            sharpe_ratio=sharpe,
            trades=[t.to_dict() if hasattr(t, 'to_dict') else t for t in self.trades], 
            equity_curve=self.equity_curve
        )
