"""
日期對齊模組

對齊所有股票的交易日，使用 bfill 填補缺失值
"""
import logging
import pandas as pd
from typing import Tuple

from .config import MIN_STOCKS_FOR_VALID_DAY, MIN_STOCKS_FOR_VALID_DAY_RATIO

logger = logging.getLogger(__name__)


def align_data_with_bfill(raw_data: dict) -> Tuple[dict, pd.DatetimeIndex]:
    """
    對齊所有股票的日期，並用 bfill 填補空缺
    
    不同市場有不同的交易日（如週末只有 BTC-USD 有資料）
    
    解決方案：
    1. 建立統一日期索引（所有股票日期的聯集）
    2. 過濾出「有效交易日」（≥50 支股票有資料的日子）
    3. 每支股票 reindex 到統一日期
    4. 使用 bfill (backward fill) 填補缺失值
    
    Args:
        raw_data: {ticker: DataFrame with OHLCV}
        
    Returns:
        (aligned_data, unified_dates)
    """
    if not raw_data:
        return {}, pd.DatetimeIndex([])
    
    # Step 1: 統計每個日期有多少股票有資料
    date_stock_count = {}
    for ticker, df in raw_data.items():
        if df.empty:
            continue
        for date in df.index:
            date_stock_count[date] = date_stock_count.get(date, 0) + 1
    
    # Step 2: 過濾出有效交易日
    valid_dates = [
        date for date, count in date_stock_count.items()
        if count >= MIN_STOCKS_FOR_VALID_DAY
    ]
    
    if not valid_dates:
        # 股票太少時使用所有日期
        valid_dates = list(date_stock_count.keys())
    
    unified_dates = pd.DatetimeIndex(sorted(valid_dates))
    
    # Step 3: 對齊每支股票的資料
    aligned_data = {}
    for ticker, df in raw_data.items():
        if df.empty:
            continue
        
        # Reindex 到統一日期，然後 bfill + ffill
        aligned_df = df.reindex(unified_dates).bfill().ffill()
        aligned_data[ticker] = aligned_df
    
    # 記錄過濾掉的日期數量
    total_dates = len(date_stock_count)
    filtered_dates = total_dates - len(unified_dates)
    if filtered_dates > 0:
        logger.info(f"過濾掉 {filtered_dates} 個非主要交易日")
    
    return aligned_data, unified_dates


def align_close_prices(stock_data: dict) -> Tuple[pd.DataFrame, pd.DatetimeIndex]:
    """
    對齊所有股票的收盤價到相同日期
    
    這是 backtest 專用的簡化版本，直接返回 DataFrame
    
    Args:
        stock_data: {symbol: DataFrame with Close column}
    
    Returns:
        aligned_df: DataFrame [Date x Symbol]
        date_index: DatetimeIndex
    """
    if not stock_data:
        raise ValueError("No stock data provided")
    
    # 收集所有股票的收盤價
    close_series = {s: df['Close'] for s, df in stock_data.items() if 'Close' in df.columns}
    
    # 合併成 DataFrame 並填充缺失值
    df = pd.DataFrame(close_series).sort_index().bfill().ffill()
    
    # 動態計算最小股票數（基於總股票數的比例）
    min_stocks = max(5, int(len(close_series) * MIN_STOCKS_FOR_VALID_DAY_RATIO))
    
    # 篩選有效交易日
    valid_mask = df.notna().sum(axis=1) >= min_stocks
    df = df[valid_mask]
    
    if len(df) == 0:
        raise ValueError(f"No valid trading days. Total: {len(close_series)}, min required: {min_stocks}")
    
    logger.info(f"對齊完成: {len(df)} 個交易日, {len(df.columns)} 檔股票")
    return df, df.index
