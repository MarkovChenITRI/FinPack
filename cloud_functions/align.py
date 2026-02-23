"""
Cloud Functions 資料對齊模組
"""
import pandas as pd
import numpy as np
import logging
from typing import Tuple

from .config import MIN_STOCKS_FOR_VALID_DAY

logger = logging.getLogger(__name__)


def align_close_prices(stock_data: dict) -> Tuple[pd.DataFrame, pd.DatetimeIndex]:
    """
    對齊所有股票的收盤價到相同日期
    
    Args:
        stock_data: {symbol: DataFrame with Close column}
    
    Returns:
        aligned_df: DataFrame [Date x Symbol]
        date_index: DatetimeIndex
    """
    if not stock_data:
        raise ValueError("No stock data provided")
    
    # 收集所有股票的收盤價
    close_series = {}
    for symbol, df in stock_data.items():
        if df is not None and 'Close' in df.columns:
            close_series[symbol] = df['Close']
    
    # 合併成 DataFrame
    df = pd.DataFrame(close_series)
    
    # 排序日期
    df = df.sort_index()
    
    # 使用前向填充（bfill）與後向填充（ffill）處理缺失值
    df = df.bfill().ffill()
    
    # 篩選有效交易日（至少 MIN_STOCKS_FOR_VALID_DAY 支股票有資料）
    valid_mask = df.notna().sum(axis=1) >= MIN_STOCKS_FOR_VALID_DAY
    df = df[valid_mask]
    
    # 移除仍有 NaN 的股票
    df = df.dropna(axis=1, how='any')
    
    logger.info(f"Aligned data: {len(df)} days, {len(df.columns)} stocks")
    
    return df, df.index


def get_date_range_indices(date_index: pd.DatetimeIndex, 
                           start_date: pd.Timestamp = None,
                           end_date: pd.Timestamp = None) -> Tuple[int, int]:
    """
    取得日期範圍的索引
    
    Args:
        date_index: 日期索引
        start_date: 開始日期（None 表示最早）
        end_date: 結束日期（None 表示最晚）
    
    Returns:
        (start_idx, end_idx)
    """
    if start_date is None:
        start_idx = 0
    else:
        start_idx = date_index.searchsorted(start_date)
    
    if end_date is None:
        end_idx = len(date_index) - 1
    else:
        end_idx = date_index.searchsorted(end_date, side='right') - 1
    
    return int(start_idx), int(end_idx)
