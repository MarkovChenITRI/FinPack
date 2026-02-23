"""
FinPack Cloud Functions - 獨立回測腳本

Google Cloud Functions 入口點：main(request)
本地測試：python run.py --debug（啟用快取）

自動執行流程：
1. 抓取 6 年市場與股票資料
2. 以預設參數執行 4 年回測
3. 輸出總報酬、年化指標、交易列表

注意：Google Cloud Functions 禁止儲存檔案，僅在 --debug 模式下啟用快取
"""
import sys
import json
import pickle
import logging
from pathlib import Path
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import Optional, Tuple
from enum import Enum

import requests
import pandas as pd
import numpy as np
import yfinance as yf
from tqdm import tqdm

# ============================================================
# 配置
# ============================================================

# 執行模式（--debug 啟用快取）
DEBUG_MODE = '--debug' in sys.argv

BASE_DIR = Path(__file__).parent
CACHE_DIR = BASE_DIR / "cache"

# 計算參數
SHARPE_WINDOW = 252
RISK_FREE_RATE = 0.04
DATA_PERIOD = "6y"
BACKTEST_YEARS = 4
MIN_STOCKS_FOR_VALID_DAY_RATIO = 0.5  # 每日至少要有 50% 股票有數據

# TradingView 設定（直接設定，不使用環境變數）
TRADINGVIEW_WATCHLIST_ID = '118349730'
TRADINGVIEW_SESSION_ID = 'b379eetq1pojcel6olyymmpo1rd41nng'

# 不可交易的 industry 類型（由 TradingView 分類決定）
NON_TRADABLE_INDUSTRIES = {'Market Index', 'Index'}

# 預設回測參數
DEFAULT_BACKTEST_CONFIG = {
    'initial_capital': 1000000,
    'amount_per_stock': 100000,
    'max_positions': 10,
    'rebalance_freq': 'weekly',
    'buy_conditions': {
        'sharpe_rank': {'enabled': True, 'top_n': 15},
        'sharpe_threshold': {'enabled': True, 'threshold': 1.0},
        'sharpe_streak': {'enabled': False, 'days': 3},
        'growth_streak': {'enabled': True, 'days': 2},
        'growth_rank': {'enabled': False, 'top_k': 7},
        'sort_sharpe': {'enabled': True},
        'sort_industry': {'enabled': False},
    },
    'sell_conditions': {
        'sharpe_fail': {'enabled': True, 'periods': 2, 'top_n': 15},
        'growth_fail': {'enabled': False, 'days': 5},
        'not_selected': {'enabled': False, 'periods': 3},
        'drawdown': {'enabled': True, 'threshold': 0.40},
        'weakness': {'enabled': False, 'rank_k': 20, 'periods': 3},
    },
    'rebalance_strategy': {
        'type': 'delayed',
        'batch_ratio': 0.20,
        'concentrate_top_k': 3,
    }
}

FEES = {
    'us': {'rate': 0.003, 'min_fee': 15},
    'tw': {'rate': 0.006, 'min_fee': 0}
}

# Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ============================================================
# 快取管理（僅在 DEBUG_MODE 下啟用）
# ============================================================

def ensure_cache_dir():
    if DEBUG_MODE:
        CACHE_DIR.mkdir(exist_ok=True)

def get_cache_path(name: str) -> Path:
    ensure_cache_dir()
    return CACHE_DIR / f"{name}.pkl"

def is_cache_valid(cache_path: Path, max_age_hours: int = 24) -> bool:
    if not DEBUG_MODE:
        return False
    if not cache_path.exists():
        return False
    mtime = datetime.fromtimestamp(cache_path.stat().st_mtime)
    return datetime.now() - mtime < timedelta(hours=max_age_hours)

def load_cache(name: str, max_age_hours: int = 24) -> Optional[dict]:
    """載入快取（僅 DEBUG_MODE）"""
    if not DEBUG_MODE:
        return None
    cache_path = get_cache_path(name)
    if is_cache_valid(cache_path, max_age_hours):
        try:
            with open(cache_path, 'rb') as f:
                logger.info(f"[DEBUG] Loading cache: {name}")
                return pickle.load(f)
        except Exception as e:
            logger.warning(f"Cache load failed: {e}")
    return None

def save_cache(name: str, data: dict):
    """儲存快取（僅 DEBUG_MODE）"""
    if not DEBUG_MODE:
        return
    try:
        with open(get_cache_path(name), 'wb') as f:
            pickle.dump(data, f)
        logger.info(f"[DEBUG] Saved cache: {name}")
    except Exception as e:
        logger.warning(f"Cache save failed: {e}")

# ============================================================
# 資料擷取
# ============================================================

def fetch_watchlist() -> Tuple[dict, dict]:
    """從 TradingView 擷取觀察清單"""
    cached = load_cache('watchlist')
    if cached:
        return cached['watchlist'], cached['stock_info']
    
    url = f"https://in.tradingview.com/api/v1/symbols_list/custom/{TRADINGVIEW_WATCHLIST_ID}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Cookie': f'sessionid={TRADINGVIEW_SESSION_ID}',
        'x-requested-with': 'XMLHttpRequest',
    }
    
    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    symbols = resp.json()["symbols"]
    
    watchlist = {}
    stock_info = {}
    current_industry = None
    
    for item in symbols:
        # "###IndustryName\u2064" 標記新的產業分組
        if "###" in item:
            current_industry = item.strip("###\u2064")
            continue
        
        if not current_industry or ':' not in item:
            continue
            
        provider, code = item.split(':', 1)
        
        # 轉換為 yfinance 格式
        if provider in ['NASDAQ', 'NYSE', 'AMEX']:
            yf_code = code
            country = 'US'
        elif provider == 'TWSE':
            yf_code = f"{code}.TW"
            country = 'TW'
        elif provider == 'TPEX':
            yf_code = f"{code}.TWO"
            country = 'TW'
        else:
            continue
        
        if provider not in watchlist:
            watchlist[provider] = []
        watchlist[provider].append(yf_code)
        
        stock_info[yf_code] = {
            'symbol': yf_code,
            'provider': provider,
            'name': code,
            'industry': current_industry,
            'country': country,
        }
    
    # 不再手動加入市場指數，信任 TradingView 的分類
    
    save_cache('watchlist', {'watchlist': watchlist, 'stock_info': stock_info})
    return watchlist, stock_info

def fetch_stock_history(symbol: str) -> Optional[pd.DataFrame]:
    """擷取股票歷史資料（symbol 已是 yfinance 格式）"""
    try:
        df = yf.Ticker(symbol).history(period=DATA_PERIOD)
        if df.empty:
            logger.debug(f"  {symbol}: empty")
            return None
        df = df[['Open', 'High', 'Low', 'Close', 'Volume']].copy()
        df.index = pd.to_datetime(df.index).tz_localize(None)
        if len(df) <= 100:
            logger.debug(f"  {symbol}: only {len(df)} rows")
        return df
    except Exception as e:
        logger.debug(f"  {symbol}: error {e}")
        return None

def fetch_all_stocks(watchlist: dict) -> dict:
    """擷取所有股票歷史資料"""
    cached = load_cache('stock_history')
    if cached:
        return cached
    
    all_data = {}
    total = sum(len(v) for v in watchlist.values())
    
    all_symbols = [(provider, symbol) for provider, symbols in watchlist.items() for symbol in symbols]
    
    with tqdm(all_symbols, desc="Fetching stocks", unit="stock") as pbar:
        for provider, symbol in pbar:
            pbar.set_postfix_str(symbol)
            df = fetch_stock_history(symbol)
            if df is not None and len(df) > 100:
                all_data[symbol] = df
    
    logger.info(f"Fetched {len(all_data)}/{total} stocks successfully")
    save_cache('stock_history', all_data)
    return all_data

def align_close_prices(stock_data: dict) -> Tuple[pd.DataFrame, pd.DatetimeIndex]:
    close_series = {s: df['Close'] for s, df in stock_data.items() if 'Close' in df.columns}
    df = pd.DataFrame(close_series).sort_index().bfill().ffill()
    
    # 動態計算最小股票數（基於總股票數的比例）
    min_stocks = max(5, int(len(close_series) * MIN_STOCKS_FOR_VALID_DAY_RATIO))
    valid_mask = df.notna().sum(axis=1) >= min_stocks
    df = df[valid_mask].dropna(axis=1, how='any')
    
    if len(df) == 0:
        raise ValueError(f"No valid trading days found. Total stocks: {len(close_series)}, min required: {min_stocks}")
    
    logger.info(f"Aligned: {len(df)} days, {len(df.columns)} stocks (min {min_stocks} stocks/day)")
    return df, df.index

# ============================================================
# 指標計算
# ============================================================

def calculate_sharpe(close_df: pd.DataFrame) -> pd.DataFrame:
    returns = close_df.pct_change()
    excess = returns - (RISK_FREE_RATE / 252)
    rolling_mean = excess.rolling(window=SHARPE_WINDOW).mean()
    rolling_std = excess.rolling(window=SHARPE_WINDOW).std().replace(0, np.nan)
    return (rolling_mean / rolling_std) * np.sqrt(252)

def calculate_ranking(sharpe_df: pd.DataFrame) -> pd.DataFrame:
    return sharpe_df.rank(axis=1, ascending=False, method='min')

def calculate_growth(rank_df: pd.DataFrame) -> pd.DataFrame:
    return rank_df.shift(1) - rank_df

class Indicators:
    def __init__(self, close_df: pd.DataFrame):
        self.close = close_df
        self._sharpe = None
        self._rank = None
        self._growth = None
    
    @property
    def sharpe(self) -> pd.DataFrame:
        if self._sharpe is None:
            self._sharpe = calculate_sharpe(self.close)
        return self._sharpe
    
    @property
    def rank(self) -> pd.DataFrame:
        if self._rank is None:
            self._rank = calculate_ranking(self.sharpe)
        return self._rank
    
    @property
    def growth(self) -> pd.DataFrame:
        if self._growth is None:
            self._growth = calculate_growth(self.rank)
        return self._growth
    
    def get_sharpe(self, symbol: str, idx: int) -> float:
        return self.sharpe.iloc[idx].get(symbol, np.nan)
    
    def get_rank(self, symbol: str, idx: int) -> float:
        return self.rank.iloc[idx].get(symbol, np.nan)
    
    def get_growth(self, symbol: str, idx: int) -> float:
        return self.growth.iloc[idx].get(symbol, np.nan)
    
    def check_growth_streak(self, symbol: str, idx: int, days: int) -> bool:
        if idx < days:
            return False
        for i in range(days):
            g = self.get_growth(symbol, idx - i)
            if pd.isna(g) or g <= 0:
                return False
        return True
    
    def check_sharpe_streak(self, symbol: str, idx: int, days: int, top_n: int) -> bool:
        if idx < days:
            return False
        for i in range(days):
            r = self.get_rank(symbol, idx - i)
            if pd.isna(r) or r > top_n:
                return False
        return True

# ============================================================
# 回測引擎
# ============================================================

class TradeType(Enum):
    BUY = 'buy'
    SELL = 'sell'

@dataclass
class Trade:
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
            'date': self.date, 'symbol': self.symbol, 'type': self.type.value,
            'shares': self.shares, 'price': round(self.price, 2),
            'amount': round(self.amount, 2), 'fee': round(self.fee, 2), 'reason': self.reason,
        }

@dataclass
class Position:
    symbol: str
    shares: int
    avg_cost: float
    buy_date: str
    buy_price: float
    peak_price: float = 0.0

@dataclass
class BacktestResult:
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
            'final_equity': round(self.final_equity, 2),
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
    def __init__(self, close_df: pd.DataFrame, indicators: Indicators,
                 stock_info: dict, config: dict = None):
        self.close = close_df
        self.indicators = indicators
        self.stock_info = stock_info
        self.config = config or DEFAULT_BACKTEST_CONFIG.copy()
        
        self.cash = self.config['initial_capital']
        self.positions: dict[str, Position] = {}
        self.trades: list[Trade] = []
        self.equity_curve: list[dict] = []
        
        self._sharpe_fail_counter: dict[str, int] = {}
        self._growth_fail_counter: dict[str, int] = {}
        self._not_selected_counter: dict[str, int] = {}
        self._weakness_counter: dict[str, int] = {}
    
    def run(self, start_date: datetime = None, end_date: datetime = None) -> BacktestResult:
        date_index = self.close.index
        if end_date is None:
            end_date = date_index[-1]
        if start_date is None:
            start_date = end_date - pd.DateOffset(years=BACKTEST_YEARS)
        
        start_idx = date_index.searchsorted(start_date)
        end_idx = date_index.searchsorted(end_date, side='right') - 1
        
        logger.info(f"Backtest: {date_index[start_idx].date()} ~ {date_index[end_idx].date()}")
        
        for idx in range(start_idx, end_idx + 1):
            self._process_day(idx)
        
        return self._calculate_result(start_idx, end_idx)
    
    def _process_day(self, idx: int):
        date_str = self.close.index[idx].strftime('%Y-%m-%d')
        self._update_peaks(idx)
        self._process_sells(idx, date_str)
        if self._is_rebalance_day(idx):
            self._process_rebalance(idx, date_str)
        equity = self._calc_equity(idx)
        self.equity_curve.append({'date': date_str, 'equity': equity, 'positions': len(self.positions)})
    
    def _update_peaks(self, idx: int):
        for sym, pos in self.positions.items():
            price = self.close.iloc[idx].get(sym, pos.peak_price)
            if price > pos.peak_price:
                pos.peak_price = price
    
    def _is_rebalance_day(self, idx: int) -> bool:
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
    
    def _select_stocks(self, idx: int) -> list[str]:
        buy_cond = self.config['buy_conditions']
        candidates = []
        
        for symbol in self.close.columns:
            # 根據 TradingView 分類排除不可交易的標的
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
        
        if buy_cond.get('sort_industry', {}).get('enabled'):
            industry_best = {}
            for c in candidates:
                ind = c['industry']
                if ind not in industry_best or c['sharpe'] > industry_best[ind]['sharpe']:
                    industry_best[ind] = c
            candidates = list(industry_best.values())
        
        if buy_cond.get('sort_sharpe', {}).get('enabled'):
            candidates.sort(key=lambda x: x['sharpe'] or -999, reverse=True)
        
        return [c['symbol'] for c in candidates]
    
    def _check_buy(self, symbol: str, idx: int, buy_cond: dict) -> bool:
        if buy_cond.get('sharpe_rank', {}).get('enabled'):
            top_n = buy_cond['sharpe_rank'].get('top_n', 15)
            rank = self.indicators.get_rank(symbol, idx)
            if pd.isna(rank) or rank > top_n:
                return False
        
        if buy_cond.get('sharpe_threshold', {}).get('enabled'):
            threshold = buy_cond['sharpe_threshold'].get('threshold', 1.0)
            sharpe = self.indicators.get_sharpe(symbol, idx)
            if pd.isna(sharpe) or sharpe < threshold:
                return False
        
        if buy_cond.get('sharpe_streak', {}).get('enabled'):
            days = buy_cond['sharpe_streak'].get('days', 3)
            top_n = buy_cond.get('sharpe_rank', {}).get('top_n', 15)
            if not self.indicators.check_sharpe_streak(symbol, idx, days, top_n):
                return False
        
        if buy_cond.get('growth_streak', {}).get('enabled'):
            days = buy_cond['growth_streak'].get('days', 2)
            if not self.indicators.check_growth_streak(symbol, idx, days):
                return False
        
        return True
    
    def _process_sells(self, idx: int, date_str: str):
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
        if sell_cond.get('sharpe_fail', {}).get('enabled'):
            periods = sell_cond['sharpe_fail'].get('periods', 2)
            top_n = sell_cond['sharpe_fail'].get('top_n', 15)
            rank = self.indicators.get_rank(symbol, idx)
            if pd.isna(rank) or rank > top_n:
                self._sharpe_fail_counter[symbol] = self._sharpe_fail_counter.get(symbol, 0) + 1
            else:
                self._sharpe_fail_counter[symbol] = 0
            if self._sharpe_fail_counter.get(symbol, 0) >= periods:
                return f'sharpe_fail({periods})'
        
        if sell_cond.get('growth_fail', {}).get('enabled'):
            days = sell_cond['growth_fail'].get('days', 5)
            growth = self.indicators.get_growth(symbol, idx)
            if pd.isna(growth) or growth < 0:
                self._growth_fail_counter[symbol] = self._growth_fail_counter.get(symbol, 0) + 1
            else:
                self._growth_fail_counter[symbol] = 0
            if self._growth_fail_counter.get(symbol, 0) >= days:
                return f'growth_fail({days})'
        
        if sell_cond.get('not_selected', {}).get('enabled'):
            periods = sell_cond['not_selected'].get('periods', 3)
            if symbol not in selected:
                self._not_selected_counter[symbol] = self._not_selected_counter.get(symbol, 0) + 1
            else:
                self._not_selected_counter[symbol] = 0
            if self._not_selected_counter.get(symbol, 0) >= periods:
                return f'not_selected({periods})'
        
        if sell_cond.get('drawdown', {}).get('enabled'):
            threshold = sell_cond['drawdown'].get('threshold', 0.40)
            price = self.close.iloc[idx].get(symbol, pos.buy_price)
            peak = pos.peak_price or pos.buy_price
            if peak > 0 and (peak - price) / peak >= threshold:
                return f'drawdown({threshold:.0%})'
        
        if sell_cond.get('weakness', {}).get('enabled'):
            rank_k = sell_cond['weakness'].get('rank_k', 20)
            periods = sell_cond['weakness'].get('periods', 3)
            rank = self.indicators.get_rank(symbol, idx)
            if pd.isna(rank) or rank > rank_k:
                self._weakness_counter[symbol] = self._weakness_counter.get(symbol, 0) + 1
            else:
                self._weakness_counter[symbol] = 0
            if self._weakness_counter.get(symbol, 0) >= periods:
                return f'weakness({rank_k},{periods})'
        
        return None
    
    def _process_rebalance(self, idx: int, date_str: str):
        strategy = self.config['rebalance_strategy']
        stype = strategy.get('type', 'delayed')
        candidates = self._select_stocks(idx)
        
        if stype == 'immediate':
            for symbol in list(self.positions.keys()):
                if symbol not in candidates:
                    self._sell(symbol, idx, date_str, 'rebalance')
        elif stype == 'batch':
            ratio = strategy.get('batch_ratio', 0.20)
            non_cand = [s for s in self.positions if s not in candidates]
            n_sell = max(1, int(len(non_cand) * ratio))
            ranked = sorted(non_cand, key=lambda s: self.indicators.get_rank(s, idx) or 999, reverse=True)
            for symbol in ranked[:n_sell]:
                self._sell(symbol, idx, date_str, 'rebalance_batch')
        elif stype == 'concentrated':
            top_k = strategy.get('concentrate_top_k', 3)
            top_cand = candidates[:top_k]
            for symbol in list(self.positions.keys()):
                if symbol not in top_cand:
                    self._sell(symbol, idx, date_str, 'concentrate')
            candidates = top_cand
        elif stype == 'delayed':
            top_n = self.config['buy_conditions'].get('sharpe_rank', {}).get('top_n', 15)
            threshold = self.config['buy_conditions'].get('sharpe_threshold', {}).get('threshold', 1.0)
            high_count = sum(1 for s in self.close.columns
                           if not pd.isna(self.indicators.get_sharpe(s, idx))
                           and self.indicators.get_sharpe(s, idx) >= threshold)
            if high_count < top_n // 2:
                return  # 市場弱勢，不買入
        
        self._buy_new(candidates, idx, date_str)
    
    def _buy_new(self, candidates: list, idx: int, date_str: str):
        max_pos = self.config['max_positions']
        amount = self.config['amount_per_stock']
        slots = max_pos - len(self.positions)
        
        for symbol in candidates:
            if slots <= 0 or self.cash < amount:
                break
            if symbol in self.positions:
                continue
            
            price = self.close.iloc[idx].get(symbol)
            if pd.isna(price) or price <= 0:
                continue
            
            shares = int(amount / price)
            if shares <= 0:
                continue
            
            market = 'tw' if self.stock_info.get(symbol, {}).get('country') == 'TW' else 'us'
            fee_cfg = FEES.get(market, FEES['us'])
            fee = max(shares * price * fee_cfg['rate'], fee_cfg['min_fee'])
            cost = shares * price + fee
            
            if cost > self.cash:
                continue
            
            self.cash -= cost
            self.positions[symbol] = Position(
                symbol=symbol, shares=shares, avg_cost=price,
                buy_date=date_str, buy_price=price, peak_price=price
            )
            self.trades.append(Trade(
                date=date_str, symbol=symbol, type=TradeType.BUY,
                shares=shares, price=price, amount=shares * price, fee=fee, reason='buy'
            ))
            slots -= 1
    
    def _sell(self, symbol: str, idx: int, date_str: str, reason: str):
        if symbol not in self.positions:
            return
        
        pos = self.positions[symbol]
        price = self.close.iloc[idx].get(symbol, pos.avg_cost)
        amount = pos.shares * price
        
        market = 'tw' if self.stock_info.get(symbol, {}).get('country') == 'TW' else 'us'
        fee_cfg = FEES.get(market, FEES['us'])
        fee = max(amount * fee_cfg['rate'], fee_cfg['min_fee'])
        
        self.cash += amount - fee
        del self.positions[symbol]
        
        for counter in [self._sharpe_fail_counter, self._growth_fail_counter,
                       self._not_selected_counter, self._weakness_counter]:
            counter.pop(symbol, None)
        
        self.trades.append(Trade(
            date=date_str, symbol=symbol, type=TradeType.SELL,
            shares=pos.shares, price=price, amount=amount, fee=fee, reason=reason
        ))
    
    def _calc_equity(self, idx: int) -> float:
        equity = self.cash
        for sym, pos in self.positions.items():
            equity += pos.shares * self.close.iloc[idx].get(sym, pos.avg_cost)
        return equity
    
    def _calculate_result(self, start_idx: int, end_idx: int) -> BacktestResult:
        initial = self.config['initial_capital']
        final = self._calc_equity(end_idx)
        total_return = (final - initial) / initial
        
        days = end_idx - start_idx + 1
        years = days / 252
        annualized = (1 + total_return) ** (1 / years) - 1 if years > 0 else 0
        
        win_trades = loss_trades = 0
        for i, t in enumerate(self.trades):
            if t.type == TradeType.SELL:
                for j in range(i - 1, -1, -1):
                    if self.trades[j].symbol == t.symbol and self.trades[j].type == TradeType.BUY:
                        profit = t.amount - t.fee - self.trades[j].amount - self.trades[j].fee
                        if profit > 0:
                            win_trades += 1
                        else:
                            loss_trades += 1
                        break
        
        total = win_trades + loss_trades
        win_rate = win_trades / total if total > 0 else 0
        
        max_eq = initial
        max_dd = 0
        for p in self.equity_curve:
            if p['equity'] > max_eq:
                max_eq = p['equity']
            dd = (max_eq - p['equity']) / max_eq
            if dd > max_dd:
                max_dd = dd
        
        if len(self.equity_curve) > 1:
            eqs = [p['equity'] for p in self.equity_curve]
            rets = np.diff(eqs) / eqs[:-1]
            sharpe = np.mean(rets) / np.std(rets) * np.sqrt(252) if np.std(rets) > 0 else 0
        else:
            sharpe = 0
        
        return BacktestResult(
            initial_capital=initial, final_equity=final,
            total_return=total_return, annualized_return=annualized,
            total_trades=len(self.trades), win_trades=win_trades, loss_trades=loss_trades,
            win_rate=win_rate, max_drawdown=max_dd, sharpe_ratio=sharpe,
            trades=[t.to_dict() for t in self.trades], equity_curve=self.equity_curve
        )

# ============================================================
# 主要流程
# ============================================================

def run_backtest() -> dict:
    """執行完整回測流程"""
    start_time = datetime.now()
    logger.info("=" * 50)
    logger.info(f"FinPack Backtest Engine {'[DEBUG MODE]' if DEBUG_MODE else '[CLOUD MODE]'}")
    logger.info("=" * 50)
    
    # 1. 載入資料
    logger.info("Loading data...")
    watchlist, stock_info = fetch_watchlist()
    stock_data = fetch_all_stocks(watchlist)
    
    # 過濾只保留美股
    us_symbols = {s for s, info in stock_info.items() if info.get('country') == 'US'}
    stock_data = {s: df for s, df in stock_data.items() if s in us_symbols}
    stock_info = {s: info for s, info in stock_info.items() if s in us_symbols}
    logger.info(f"Filtered to {len(stock_data)} US stocks")
    
    close_df, _ = align_close_prices(stock_data)
    logger.info(f"Data: {len(close_df)} days, {len(close_df.columns)} stocks")
    
    # 2. 計算指標
    logger.info("Calculating indicators...")
    indicators = Indicators(close_df)
    _ = indicators.sharpe
    _ = indicators.rank
    _ = indicators.growth
    
    # 3. 執行回測
    logger.info("Running backtest...")
    engine = BacktestEngine(close_df, indicators, stock_info)
    result = engine.run()
    
    # 4. 取得當前持倉
    current_holdings = []
    last_idx = len(close_df) - 1
    for symbol, pos in engine.positions.items():
        current_price = close_df.iloc[last_idx].get(symbol, pos.avg_cost)
        market_value = pos.shares * current_price
        pnl = market_value - (pos.shares * pos.avg_cost)
        pnl_pct = (current_price - pos.avg_cost) / pos.avg_cost if pos.avg_cost > 0 else 0
        current_holdings.append({
            'symbol': symbol,
            'shares': pos.shares,
            'avg_cost': round(pos.avg_cost, 2),
            'current_price': round(current_price, 2),
            'market_value': round(market_value, 2),
            'pnl': round(pnl, 2),
            'pnl_pct': f"{pnl_pct:.2%}",
            'buy_date': pos.buy_date,
        })
    current_holdings.sort(key=lambda x: x['pnl'], reverse=True)
    
    # 5. 輸出結果
    elapsed = (datetime.now() - start_time).total_seconds()
    summary = result.to_dict()
    
    logger.info("=" * 50)
    logger.info(f"Initial: ${summary['initial_capital']:,.0f}")
    logger.info(f"Final:   ${summary['final_equity']:,.0f}")
    logger.info(f"Return:  {summary['total_return']} (Annual: {summary['annualized_return']})")
    logger.info(f"Win Rate: {summary['win_rate']} | Max DD: {summary['max_drawdown']}")
    logger.info(f"Sharpe: {summary['sharpe_ratio']} | Trades: {summary['total_trades']}")
    logger.info(f"Holdings: {len(current_holdings)} positions")
    logger.info(f"Elapsed: {elapsed:.1f}s")
    logger.info("=" * 50)
    
    # 輸出當前持倉
    if current_holdings:
        logger.info("\n=== Current Holdings ===")
        for h in current_holdings:
            logger.info(f"  {h['symbol']:8s} | {h['shares']:6d} shares | Cost: ${h['avg_cost']:8.2f} | Now: ${h['current_price']:8.2f} | P&L: ${h['pnl']:+10.2f} ({h['pnl_pct']})")
        logger.info("")
    
    # 輸出交易明細
    logger.info("\n=== Trade History ===")
    for t in result.trades:
        logger.info(f"  {t['date']} | {t['type']:4s} | {t['symbol']:8s} | {t['shares']:6d} @ ${t['price']:8.2f} | {t['reason']}")
    logger.info("")
    
    return {
        'success': True,
        'elapsed_seconds': round(elapsed, 1),
        'summary': summary,
        'current_holdings': current_holdings,
        'trades': result.trades,  # 完整交易明細
        'equity_curve': result.equity_curve[-30:],
    }

def main(request=None):
    """
    Google Cloud Functions HTTP entry point
    
    本地測試：python run.py --debug
    
    部署指令：
    gcloud functions deploy finpack-backtest \
        --runtime python311 \
        --trigger-http \
        --entry-point main \
        --allow-unauthenticated
    """
    try:
        result = run_backtest()
        
        if request:
            from flask import jsonify
            return jsonify(result)
        return json.dumps(result, ensure_ascii=False, indent=2)
    
    except Exception as e:
        logger.exception("Backtest failed")
        error = {'success': False, 'error': str(e)}
        if request:
            from flask import jsonify
            return jsonify(error), 500
        return json.dumps(error)

# 本地測試
if __name__ == '__main__':
    if DEBUG_MODE:
        logger.info("Running in DEBUG mode (cache enabled)")
    else:
        logger.info("Running in CLOUD mode (cache disabled)")
    print(main())
