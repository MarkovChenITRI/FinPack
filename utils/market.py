"""
市場數據工具 - 提供美股/台股大盤加權K線數據
"""
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta


class MarketDataLoader:
    """市場數據加載器"""
    
    def __init__(self):
        self.cache = {}
        
    def get_index_data(self, symbol: str, period: str = "2y") -> pd.DataFrame:
        """
        獲取指數歷史數據
        
        Args:
            symbol: 指數代碼 (如 ^IXIC, ^TWII)
            period: 時間範圍 (1y, 2y, 5y, max)
            
        Returns:
            DataFrame with OHLCV data
        """
        cache_key = f"{symbol}_{period}"
        
        if cache_key in self.cache:
            return self.cache[cache_key].copy()
        
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period=period, interval="1d")
            df = df.tz_localize(None)
            df = df.sort_index()
            
            self.cache[cache_key] = df
            return df.copy()
            
        except Exception as e:
            print(f"Error fetching {symbol}: {e}")
            return pd.DataFrame()
    
    def get_weighted_kline(self, symbol: str, period: str = "2y", convert_to_usd: bool = False) -> list:
        """
        獲取K線數據（用於前端圖表）
        
        Args:
            symbol: 指數代碼
            period: 時間範圍
            convert_to_usd: 未使用（保留參數以相容）
            
        Returns:
            list of dict: [{time, open, high, low, close, volume}, ...]
        """
        df = self.get_index_data(symbol, period)
        
        if df.empty:
            return []
        
        kline_data = []
        for idx, row in df.iterrows():
            # 跳過無效數據 (NaN)
            if pd.isna(row['Open']) or pd.isna(row['Close']):
                continue
                
            kline_data.append({
                'time': idx.strftime('%Y-%m-%d'),
                'open': round(row['Open'], 2),
                'high': round(row['High'], 2),
                'low': round(row['Low'], 2),
                'close': round(row['Close'], 2),
                'volume': int(row['Volume']) if not pd.isna(row['Volume']) else 0
            })
        
        return kline_data
    
    def get_global_weighted_index(self, period: str = "2y") -> list:
        """
        計算國際加權指數 (NASDAQ 與台股 1:1 固定權重)
        
        計算方式: 
        縮放係數 = NASDAQ收盤價 ÷ 台股收盤價 (標準化尺度)
        加權價格 = (NASDAQ價格 + 台股價格 × 縮放係數) ÷ 2
        
        Returns:
            list of dict: [{time, open, high, low, close, volume}, ...]
        """
        # 獲取原始數據
        nasdaq_df = self.get_index_data('^IXIC', period)
        twii_df = self.get_index_data('^TWII', period)
        
        if nasdaq_df.empty or twii_df.empty:
            return []
        
        # 找出共同交易日
        common_dates = nasdaq_df.index.intersection(twii_df.index)
        
        if len(common_dates) == 0:
            return []
        
        kline_data = []
        
        for date in sorted(common_dates):
            nq = nasdaq_df.loc[date]
            tw = twii_df.loc[date]
            
            if tw['Close'] == 0:
                continue
            
            # 縮放係數 = NASDAQ收盤價 ÷ 台股收盤價
            scale_factor = nq['Close'] / tw['Close']
            
            # 加權價格計算 (1:1 固定權重)
            weighted_open = (nq['Open'] + tw['Open'] * scale_factor) / 2
            weighted_high = (nq['High'] + tw['High'] * scale_factor) / 2
            weighted_low = (nq['Low'] + tw['Low'] * scale_factor) / 2
            weighted_close = (nq['Close'] + tw['Close'] * scale_factor) / 2
            
            # 確保 high >= low
            actual_high = max(weighted_open, weighted_high, weighted_low, weighted_close)
            actual_low = min(weighted_open, weighted_high, weighted_low, weighted_close)
            
            total_volume = int(nq['Volume'] + tw['Volume'])
            
            kline_data.append({
                'time': date.strftime('%Y-%m-%d'),
                'open': round(weighted_open, 2),
                'high': round(actual_high, 2),
                'low': round(actual_low, 2),
                'close': round(weighted_close, 2),
                'volume': total_volume
            })
        
        return kline_data
    
    def get_all_market_data(self, period: str = "2y") -> dict:
        """
        獲取所有市場數據
        
        Returns:
            dict with 'global', 'nasdaq', 'twii', 'gold', 'btc', 'bonds' data
        """
        return {
            'global': self.get_global_weighted_index(period),
            'nasdaq': self.get_weighted_kline('^IXIC', period),
            'twii': self.get_weighted_kline('^TWII', period),
            'gold': self.get_weighted_kline('GC=F', period),      # 黃金期貨
            'btc': self.get_weighted_kline('BTC-USD', period),    # 比特幣
            'bonds': self.get_weighted_kline('TLT', period)       # 美國20年期公債 ETF
        }


# 匯率獲取
def get_usd_twd_rate() -> float:
    """獲取美元兌台幣匯率"""
    try:
        ticker = yf.Ticker("TWD=X")
        data = ticker.history(period="1d")
        if not data.empty:
            return round(data['Close'].iloc[-1], 2)
    except:
        pass
    return 32.0  # 預設匯率


# 單例實例
_market_loader = None

def get_market_loader() -> MarketDataLoader:
    """獲取市場數據加載器單例"""
    global _market_loader
    if _market_loader is None:
        _market_loader = MarketDataLoader()
        # 更新匯率
        _market_loader.usd_twd_rate = get_usd_twd_rate()
    return _market_loader
