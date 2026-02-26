"""
指標計算模組

計算 Sharpe Ratio、排名矩陣、排名變化（Growth）
支援按國家分組排名（與前端一致）
"""
import logging
import pandas as pd
import numpy as np
from typing import Dict, List, Optional

from .config import SHARPE_WINDOW, RISK_FREE_RATE

logger = logging.getLogger(__name__)


# =============================================================================
# 基礎指標計算
# =============================================================================

def calculate_sharpe(close_data) -> pd.DataFrame:
    """
    計算滾動 Sharpe Ratio
    
    Args:
        close_data: pd.Series (單一股票) 或 pd.DataFrame (多股票矩陣)
    
    Returns:
        Sharpe Ratio Series 或 DataFrame
    """
    if isinstance(close_data, pd.Series):
        return _calculate_sharpe_series(close_data)
    else:
        return _calculate_sharpe_matrix(close_data)


def _calculate_sharpe_series(close_series: pd.Series) -> pd.Series:
    """計算單一股票的滾動 Sharpe"""
    if close_series.empty:
        return pd.Series(dtype=float)
    
    returns = close_series.pct_change()
    daily_rf = RISK_FREE_RATE / SHARPE_WINDOW
    excess_returns = returns - daily_rf
    
    rolling_mean = excess_returns.rolling(SHARPE_WINDOW).mean()
    rolling_std = excess_returns.rolling(SHARPE_WINDOW).std()
    
    # 避免除以零
    rolling_std = rolling_std.replace(0, np.nan)
    
    sharpe = rolling_mean / rolling_std * np.sqrt(SHARPE_WINDOW)
    
    # 處理 Inf/NaN
    sharpe = sharpe.replace([np.inf, -np.inf], np.nan)
    sharpe = sharpe.bfill().ffill()
    
    return sharpe


def _calculate_sharpe_matrix(close_df: pd.DataFrame) -> pd.DataFrame:
    """計算多股票的滾動 Sharpe（矩陣運算）"""
    returns = close_df.pct_change()
    daily_rf = RISK_FREE_RATE / SHARPE_WINDOW
    excess = returns - daily_rf
    
    rolling_mean = excess.rolling(window=SHARPE_WINDOW).mean()
    rolling_std = excess.rolling(window=SHARPE_WINDOW).std().replace(0, np.nan)
    
    sharpe = (rolling_mean / rolling_std) * np.sqrt(SHARPE_WINDOW)
    sharpe = sharpe.replace([np.inf, -np.inf], np.nan)
    sharpe = sharpe.bfill().ffill()
    
    return sharpe


def calculate_ranking_matrix(sharpe_matrix: pd.DataFrame) -> pd.DataFrame:
    """
    計算 Sharpe 排名矩陣
    
    排名值 1 = 當日 Sharpe 最高的股票
    
    Returns:
        DataFrame: 排名矩陣 (日期 × 股票)
    """
    if sharpe_matrix.empty:
        return pd.DataFrame()
    
    return sharpe_matrix.rank(axis=1, ascending=False, method='min')


def calculate_growth_matrix(ranking_matrix: pd.DataFrame) -> pd.DataFrame:
    """
    計算排名變化矩陣（Growth）
    
    Growth = 前一天排名 - 今天排名
    - 正值：排名上升（例：#20 → #10 = +10）
    - 負值：排名下降（例：#10 → #20 = -10）
    
    Returns:
        DataFrame: 排名變化矩陣 (日期 × 股票)
    """
    if ranking_matrix.empty:
        return pd.DataFrame()
    
    return ranking_matrix.shift(1) - ranking_matrix


def calculate_all_indicators(aligned_data: dict) -> tuple:
    """
    計算所有衍生指標
    
    Args:
        aligned_data: 對齊後的股票資料 {ticker: DataFrame}
        
    Returns:
        tuple: (sharpe_matrix, ranking_matrix, growth_matrix)
    """
    sharpe_data = {}
    
    logger.info(f"計算指標: {len(aligned_data)} 檔股票")
    
    for ticker, df in aligned_data.items():
        if 'Close' not in df.columns:
            continue
        
        sharpe = _calculate_sharpe_series(df['Close'])
        sharpe_data[ticker] = sharpe
    
    # 建立 Sharpe 矩陣
    if sharpe_data:
        sharpe_matrix = pd.DataFrame(sharpe_data).sort_index()
        
        # 處理殘餘的 Inf/NaN
        sharpe_matrix = sharpe_matrix.replace([np.inf, -np.inf], np.nan)
        sharpe_matrix = sharpe_matrix.bfill().ffill()
        
        # 計算排名矩陣
        ranking_matrix = calculate_ranking_matrix(sharpe_matrix)
        
        # 計算排名變化
        growth_matrix = calculate_growth_matrix(ranking_matrix)
        growth_matrix = growth_matrix.fillna(0)
    else:
        sharpe_matrix = pd.DataFrame()
        ranking_matrix = pd.DataFrame()
        growth_matrix = pd.DataFrame()
    
    return sharpe_matrix, ranking_matrix, growth_matrix


# =============================================================================
# 按國家分組排名（與前端一致）
# =============================================================================

def compute_daily_ranks_by_country(
    matrix: pd.DataFrame, 
    stock_info: dict
) -> Dict[str, Dict[str, List[str]]]:
    """
    計算每日按國家分組的排名（與前端 _compute_daily_ranks 完全一致）
    
    Args:
        matrix: Sharpe 或 Growth DataFrame [Date x Symbol]
        stock_info: {symbol: {country, industry, ...}}
    
    Returns:
        {date_str: {US: [sorted_tickers], TW: [sorted_tickers]}}
        陣列按值降序排列（最高值在前）
    """
    if matrix is None or matrix.empty:
        return {}
    
    ranks = {}
    for date in matrix.index:
        date_str = str(date)[:10]
        row = matrix.loc[date].dropna()
        
        # 按國家分組
        us_stocks = [(t, v) for t, v in row.items() 
                     if stock_info.get(t, {}).get('country') == 'US']
        tw_stocks = [(t, v) for t, v in row.items() 
                     if stock_info.get(t, {}).get('country') == 'TW']
        
        # 按值降序排序
        us_sorted = [t for t, v in sorted(us_stocks, key=lambda x: x[1], reverse=True)]
        tw_sorted = [t for t, v in sorted(tw_stocks, key=lambda x: x[1], reverse=True)]
        
        ranks[date_str] = {'US': us_sorted, 'TW': tw_sorted}
    
    return ranks


# =============================================================================
# Indicators 類（回測引擎用）
# =============================================================================

class Indicators:
    """
    指標計算器，封裝所有指標計算（惰性計算）
    
    提供按國家分組的排名，與前端完全一致
    """
    
    def __init__(self, close_df: pd.DataFrame, stock_info: dict):
        """
        Args:
            close_df: 收盤價 DataFrame [Date x Symbol]
            stock_info: {symbol: {country, industry, ...}}
        """
        self.close = close_df
        self.stock_info = stock_info
        self._sharpe = None
        self._rank = None
        self._growth = None
        self._growth_rank = None
        self._sharpe_rank_by_country = None
        self._growth_rank_by_country = None
    
    @property
    def sharpe(self) -> pd.DataFrame:
        """Sharpe Ratio（惰性計算）"""
        if self._sharpe is None:
            logger.info("計算 Sharpe Ratio...")
            self._sharpe = _calculate_sharpe_matrix(self.close)
        return self._sharpe
    
    @property
    def rank(self) -> pd.DataFrame:
        """Sharpe 排名（全局）"""
        if self._rank is None:
            logger.info("計算全局排名...")
            self._rank = calculate_ranking_matrix(self.sharpe)
        return self._rank
    
    @property
    def growth(self) -> pd.DataFrame:
        """排名變化"""
        if self._growth is None:
            logger.info("計算排名變化...")
            self._growth = calculate_growth_matrix(self.rank)
        return self._growth
    
    @property
    def growth_rank(self) -> pd.DataFrame:
        """Growth 排名（1 = 最高正向成長）"""
        if self._growth_rank is None:
            self._growth_rank = self.growth.rank(axis=1, ascending=False, method='min')
        return self._growth_rank
    
    @property
    def sharpe_rank_by_country(self) -> Dict[str, Dict[str, List[str]]]:
        """按國家分組的 Sharpe 排名"""
        if self._sharpe_rank_by_country is None:
            logger.info("計算按國家分組的 Sharpe 排名...")
            self._sharpe_rank_by_country = compute_daily_ranks_by_country(
                self.sharpe, self.stock_info
            )
        return self._sharpe_rank_by_country
    
    @property
    def growth_rank_by_country(self) -> Dict[str, Dict[str, List[str]]]:
        """按國家分組的 Growth 排名"""
        if self._growth_rank_by_country is None:
            logger.info("計算按國家分組的 Growth 排名...")
            self._growth_rank_by_country = compute_daily_ranks_by_country(
                self.growth, self.stock_info
            )
        return self._growth_rank_by_country
    
    def get_dates(self) -> List[str]:
        """取得所有日期"""
        return [str(d)[:10] for d in self.close.index]
    
    def get_sharpe(self, symbol: str, idx: int) -> float:
        """取得指定股票在指定索引的 Sharpe 值"""
        return self.sharpe.iloc[idx].get(symbol, np.nan)
    
    def get_rank(self, symbol: str, idx: int) -> float:
        """取得指定股票在指定索引的排名"""
        return self.rank.iloc[idx].get(symbol, np.nan)
    
    def get_growth(self, symbol: str, idx: int) -> float:
        """取得指定股票在指定索引的排名變化"""
        return self.growth.iloc[idx].get(symbol, np.nan)
    
    def check_in_sharpe_top_k(self, symbol: str, date_str: str, country: str, top_k: int) -> bool:
        """檢查股票是否在該國家的 Sharpe Top-K"""
        day_rank = self.sharpe_rank_by_country.get(date_str, {})
        ranking = day_rank.get(country, [])
        return symbol in ranking[:top_k]
    
    def check_in_growth_top_k(self, symbol: str, date_str: str, country: str, top_k: int) -> bool:
        """檢查股票是否在該國家的 Growth Top-K"""
        day_rank = self.growth_rank_by_country.get(date_str, {})
        ranking = day_rank.get(country, [])
        return symbol in ranking[:top_k]
    
    def get_sharpe_rank_position(self, symbol: str, date_str: str, country: str) -> int:
        """取得股票在 Sharpe 排名中的位置（0-based，不在排名中則返回 -1）"""
        day_rank = self.sharpe_rank_by_country.get(date_str, {})
        ranking = day_rank.get(country, [])
        try:
            return ranking.index(symbol)
        except ValueError:
            return -1
    
    def get_growth_rank_position(self, symbol: str, date_str: str, country: str) -> int:
        """取得股票在 Growth 排名中的位置（0-based，不在排名中則返回 -1）"""
        day_rank = self.growth_rank_by_country.get(date_str, {})
        ranking = day_rank.get(country, [])
        try:
            return ranking.index(symbol)
        except ValueError:
            return -1
    
    def check_in_growth_top_percentile(self, symbol: str, date_str: str, 
                                        country: str, percentile: float) -> bool:
        """檢查股票是否在該國家的 Growth 排名前 X%"""
        import math
        day_rank = self.growth_rank_by_country.get(date_str, {})
        ranking = day_rank.get(country, [])
        if not ranking:
            return False
        
        # 使用 ceil 與 JS 保持一致（Math.ceil）
        top_n = max(1, math.ceil(len(ranking) * percentile / 100))
        return symbol in ranking[:top_n]
    
    def check_growth_streak(self, symbol: str, idx: int, days: int, 
                            percentile: float = 50) -> bool:
        """檢查 Growth 排名連續性"""
        if idx < days - 1:
            return False
        
        country = self.stock_info.get(symbol, {}).get('country', 'US')
        dates = self.get_dates()
        
        for i in range(days):
            check_idx = idx - i
            if check_idx < 0 or check_idx >= len(dates):
                return False
            
            date_str = dates[check_idx]
            if not self.check_in_growth_top_percentile(symbol, date_str, country, percentile):
                return False
        
        return True
    
    def check_sharpe_streak(self, symbol: str, idx: int, days: int, top_n: int) -> bool:
        """檢查 Sharpe 排名連續性"""
        if idx < days - 1:
            return False
        
        country = self.stock_info.get(symbol, {}).get('country', 'US')
        dates = self.get_dates()
        
        for i in range(days):
            check_idx = idx - i
            if check_idx < 0 or check_idx >= len(dates):
                return False
            
            date_str = dates[check_idx]
            if not self.check_in_sharpe_top_k(symbol, date_str, country, top_n):
                return False
        
        return True
