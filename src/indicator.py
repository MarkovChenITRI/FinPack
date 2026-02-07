"""
指標計算模組

計算 Sharpe Ratio、排名矩陣、排名變化（Growth）
"""
import pandas as pd
import numpy as np
from .config import SHARPE_WINDOW, RISK_FREE_RATE


def calculate_sharpe(close_series: pd.Series) -> pd.Series:
    """
    計算滾動 Sharpe 比率
    
    Sharpe = (滾動平均超額報酬 / 滾動標準差) × √252
    
    用途：評估股票風險調整後報酬，作為選股與排名的主要依據
    """
    if close_series.empty:
        return pd.Series(dtype=float)
    
    returns = close_series.pct_change()
    daily_rf = RISK_FREE_RATE / SHARPE_WINDOW
    excess_returns = returns - daily_rf
    
    rolling_mean = excess_returns.rolling(SHARPE_WINDOW).mean()
    rolling_std = excess_returns.rolling(SHARPE_WINDOW).std()
    
    # 避免除以零產生 Inf
    rolling_std = rolling_std.replace(0, np.nan)
    
    sharpe = rolling_mean / rolling_std * np.sqrt(SHARPE_WINDOW)
    
    # 將 Inf/-Inf 替換為 NaN，然後用 bfill/ffill 填補
    sharpe = sharpe.replace([np.inf, -np.inf], np.nan)
    sharpe = sharpe.bfill().ffill()
    
    return sharpe


def calculate_ranking_matrix(sharpe_matrix: pd.DataFrame) -> pd.DataFrame:
    """
    計算 Sharpe 排名矩陣
    
    對每一天的所有股票 Sharpe 值進行排序，1 = 最高 Sharpe
    
    用途：用於相對排名判斷，如 sharpe_rank 條件「Sharpe Top-N」
    
    Returns:
        DataFrame: 排名矩陣 (日期 × 股票)，值為該股票當日的排名
    """
    if sharpe_matrix.empty:
        return pd.DataFrame()
    
    # 計算每日排名（1 = 最高 Sharpe）
    ranking_matrix = sharpe_matrix.rank(axis=1, ascending=False, method='min')
    
    return ranking_matrix


def calculate_growth_matrix(ranking_matrix: pd.DataFrame) -> pd.DataFrame:
    """
    計算排名變化矩陣（Growth）
    
    Growth = 前一天排名 - 今天排名
    
    - 正值：排名上升（例：#20 → #10 = +10）
    - 負值：排名下降（例：#10 → #20 = -10）
    
    用途：識別排名快速上升的股票，作為 growth_rank/growth_streak 成長動能條件與「Growth Top-N」選股依據
    
    Returns:
        DataFrame: 排名變化矩陣 (日期 × 股票)
    """
    if ranking_matrix.empty:
        return pd.DataFrame()
    
    # 排名變化 = 前一天排名 - 今天排名
    growth_matrix = ranking_matrix.shift(1) - ranking_matrix
    
    return growth_matrix


def calculate_all_indicators(aligned_data: dict) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    計算所有衍生指標
    
    Args:
        aligned_data: 對齊後的股票資料 {ticker: DataFrame}
        
    Returns:
        tuple: (sharpe_matrix, ranking_matrix, growth_matrix)
            - sharpe_matrix: Sharpe Ratio 原始值 (日期 × 股票)
            - ranking_matrix: Sharpe 排名 (日期 × 股票)，1 = 最高
            - growth_matrix: 排名變化 (日期 × 股票)，正值 = 排名上升
    """
    sharpe_data = {}
    
    print(f"  📊 aligned_data 有 {len(aligned_data)} 檔股票")
    
    for ticker, df in aligned_data.items():
        if 'Close' not in df.columns:
            print(f"    ⚠️ {ticker} 沒有 Close 欄位，跳過")
            continue
        
        sharpe = calculate_sharpe(df['Close'])
        sharpe_data[ticker] = sharpe
    
    # 建立 Sharpe 矩陣
    if sharpe_data:
        sharpe_matrix = pd.DataFrame(sharpe_data).sort_index()
        
        # 處理殘餘的 Inf/NaN
        sharpe_matrix = sharpe_matrix.replace([np.inf, -np.inf], np.nan)
        sharpe_matrix = sharpe_matrix.bfill().ffill()
        
        # 計算排名矩陣
        ranking_matrix = calculate_ranking_matrix(sharpe_matrix)
        
        # 計算排名變化（Growth）
        growth_matrix = calculate_growth_matrix(ranking_matrix)
        growth_matrix = growth_matrix.fillna(0)
    else:
        sharpe_matrix = pd.DataFrame()
        ranking_matrix = pd.DataFrame()
        growth_matrix = pd.DataFrame()
    
    return sharpe_matrix, ranking_matrix, growth_matrix
