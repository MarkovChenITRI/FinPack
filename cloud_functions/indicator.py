"""
Cloud Functions 指標計算模組
"""
import pandas as pd
import numpy as np
import logging

from .config import SHARPE_WINDOW, RISK_FREE_RATE

logger = logging.getLogger(__name__)


def calculate_sharpe(close_df: pd.DataFrame, 
                     window: int = None,
                     risk_free_rate: float = None) -> pd.DataFrame:
    """
    計算滾動 Sharpe Ratio
    
    Args:
        close_df: 收盤價 DataFrame [Date x Symbol]
        window: 計算視窗（預設 SHARPE_WINDOW）
        risk_free_rate: 無風險利率（預設 RISK_FREE_RATE）
    
    Returns:
        sharpe_df: Sharpe Ratio DataFrame [Date x Symbol]
    """
    if window is None:
        window = SHARPE_WINDOW
    if risk_free_rate is None:
        risk_free_rate = RISK_FREE_RATE
    
    # 計算日報酬率
    returns = close_df.pct_change()
    
    # 年化日無風險利率
    daily_rf = risk_free_rate / 252
    
    # 計算超額報酬
    excess_returns = returns - daily_rf
    
    # 滾動平均與標準差
    rolling_mean = excess_returns.rolling(window=window).mean()
    rolling_std = excess_returns.rolling(window=window).std()
    
    # 避免除以零
    rolling_std = rolling_std.replace(0, np.nan)
    
    # 年化 Sharpe Ratio
    sharpe = (rolling_mean / rolling_std) * np.sqrt(252)
    
    return sharpe


def calculate_ranking(sharpe_df: pd.DataFrame) -> pd.DataFrame:
    """
    計算 Sharpe 排名（1 = 最高）
    
    Args:
        sharpe_df: Sharpe Ratio DataFrame
    
    Returns:
        rank_df: 排名 DataFrame（1 = 最高 Sharpe）
    """
    # ascending=False: 最高 Sharpe = rank 1
    rank_df = sharpe_df.rank(axis=1, ascending=False, method='min')
    return rank_df


def calculate_growth(rank_df: pd.DataFrame) -> pd.DataFrame:
    """
    計算排名變化（正值 = 排名上升/改善）
    
    注意：rank 下降（數值變小）代表股票變強
    所以 growth = 前一天 rank - 今天 rank
    正值表示排名改善
    
    Args:
        rank_df: 排名 DataFrame
    
    Returns:
        growth_df: 排名變化 DataFrame
    """
    # growth = rank_shift(1) - rank_current
    # 如果今天 rank=5, 昨天 rank=10, growth=10-5=5（改善）
    growth_df = rank_df.shift(1) - rank_df
    return growth_df


class Indicators:
    """
    指標計算器，封裝所有指標計算
    """
    def __init__(self, close_df: pd.DataFrame):
        self.close = close_df
        self._sharpe = None
        self._rank = None
        self._growth = None
        
    @property
    def sharpe(self) -> pd.DataFrame:
        """Sharpe Ratio（惰性計算）"""
        if self._sharpe is None:
            logger.info("Calculating Sharpe ratios...")
            self._sharpe = calculate_sharpe(self.close)
        return self._sharpe
    
    @property
    def rank(self) -> pd.DataFrame:
        """Sharpe 排名（惰性計算）"""
        if self._rank is None:
            logger.info("Calculating ranks...")
            self._rank = calculate_ranking(self.sharpe)
        return self._rank
    
    @property
    def growth(self) -> pd.DataFrame:
        """排名變化（惰性計算）"""
        if self._growth is None:
            logger.info("Calculating growth...")
            self._growth = calculate_growth(self.rank)
        return self._growth
    
    def get_top_n_symbols(self, date_idx: int, top_n: int) -> list:
        """取得指定日期的 Top N 股票"""
        if date_idx < 0 or date_idx >= len(self.rank):
            return []
        
        row = self.rank.iloc[date_idx]
        valid = row[row <= top_n]
        return valid.index.tolist()
    
    def get_sharpe_value(self, symbol: str, date_idx: int) -> float:
        """取得指定股票在指定日期的 Sharpe 值"""
        if date_idx < 0 or date_idx >= len(self.sharpe):
            return np.nan
        return self.sharpe.iloc[date_idx].get(symbol, np.nan)
    
    def get_rank_value(self, symbol: str, date_idx: int) -> float:
        """取得指定股票在指定日期的排名"""
        if date_idx < 0 or date_idx >= len(self.rank):
            return np.nan
        return self.rank.iloc[date_idx].get(symbol, np.nan)
    
    def get_growth_value(self, symbol: str, date_idx: int) -> float:
        """取得指定股票在指定日期的排名變化"""
        if date_idx < 0 or date_idx >= len(self.growth):
            return np.nan
        return self.growth.iloc[date_idx].get(symbol, np.nan)
    
    def check_growth_streak(self, symbol: str, date_idx: int, days: int) -> bool:
        """
        檢查成長連續性
        
        Args:
            symbol: 股票代碼
            date_idx: 日期索引
            days: 連續天數
        
        Returns:
            True if growth > 0 for all past `days` days
        """
        if date_idx < days:
            return False
        
        for i in range(days):
            growth = self.get_growth_value(symbol, date_idx - i)
            if pd.isna(growth) or growth <= 0:
                return False
        return True
    
    def check_sharpe_streak(self, symbol: str, date_idx: int, 
                            days: int, top_n: int) -> bool:
        """
        檢查 Sharpe 排名連續性
        
        Args:
            symbol: 股票代碼
            date_idx: 日期索引
            days: 連續天數
            top_n: 排名門檻
        
        Returns:
            True if rank <= top_n for all past `days` days
        """
        if date_idx < days:
            return False
        
        for i in range(days):
            rank = self.get_rank_value(symbol, date_idx - i)
            if pd.isna(rank) or rank > top_n:
                return False
        return True
