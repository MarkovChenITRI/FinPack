"""
日期對齊模組

對齊所有股票的交易日，使用 bfill 填補缺失值
"""
import pandas as pd
from .config import MIN_STOCKS_FOR_VALID_DAY


def align_data_with_bfill(raw_data: dict) -> tuple[dict, pd.DatetimeIndex]:
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
        print(f"  📅 過濾掉 {filtered_dates} 個非主要交易日")
    
    return aligned_data, unified_dates
