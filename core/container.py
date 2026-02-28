"""
資料容器 (Singleton)

統一的資料存取介面，供所有入口點共用
"""
import logging
import pandas as pd
from datetime import datetime
from typing import Optional, List, Dict

logger = logging.getLogger(__name__)

from .config import CACHE_DIR
from .data import (
    smart_load_or_fetch, save_stock_cache, fetch_all_stock_data
)
from .align import align_data_with_bfill
from .indicator import calculate_all_indicators
from .currency import FX
from .market import MarketDataLoader


# =============================================================================
# 資料處理工具函數（共用）
# =============================================================================

def build_close_df(aligned_data: dict) -> pd.DataFrame:
    """
    從對齊資料建立收盤價 DataFrame
    
    Args:
        aligned_data: 對齊後的股票資料 {ticker: DataFrame}
        
    Returns:
        pd.DataFrame: 收盤價矩陣 [Date x Symbol]
    """
    close_dict = {}
    for ticker, df in aligned_data.items():
        if 'Close' in df.columns:
            close_dict[ticker] = df['Close']
    
    if not close_dict:
        return pd.DataFrame()
    
    return pd.DataFrame(close_dict).sort_index()


def filter_by_market(close_df: pd.DataFrame, stock_info: dict, market: str):
    """
    依市場過濾股票
    
    Args:
        close_df: 收盤價 DataFrame
        stock_info: 股票資訊
        market: 'us' | 'tw' | 'global'
        
    Returns:
        (filtered_close_df, filtered_stock_info)
    """
    country_map = {'us': 'US', 'tw': 'TW'}
    target_country = country_map.get(market)
    
    if not target_country:
        return close_df, stock_info
    
    filtered_tickers = [
        t for t in close_df.columns
        if stock_info.get(t, {}).get('country') == target_country
    ]
    
    filtered_info = {
        t: info for t, info in stock_info.items()
        if info.get('country') == target_country
    }
    
    return close_df[filtered_tickers], filtered_info


# =============================================================================
# 資料容器類別
# =============================================================================

class DataContainer:
    """
    資料容器：封裝所有資料存取操作
    
    全域實例在檔案底部建立，各模組直接 import 使用：
        from core import container
        container.get_all_tickers()
    """
    
    def __init__(self, auto_load: bool = True):
        # 原始資料
        self.raw_data: Dict = {}
        self.watchlist: Dict = {}
        self.stock_info: Dict = {}
        self.last_update: Optional[datetime] = None
        
        # 衍生資料
        self.aligned_data: Dict = {}
        self.unified_dates: Optional[pd.DatetimeIndex] = None
        self.sharpe_matrix: Optional[pd.DataFrame] = None
        self.ranking_matrix: Optional[pd.DataFrame] = None
        self.growth_matrix: Optional[pd.DataFrame] = None
        
        # 收盤價矩陣（預先建立）
        self._close_df: Optional[pd.DataFrame] = None
        
        # 匯率服務
        self.fx: Optional[FX] = None
        
        self.initialized = False
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        
        if auto_load:
            self.load_or_fetch()

        # 市場資料加載器（載入快取，無網路呼叫）
        # preload_all() 由 main.py 在啟動時另行呼叫以更新快取
        self.market_loader = MarketDataLoader()
    
    def load_or_fetch(self, force_refresh: bool = False):
        """載入快取或重新抓取資料"""
        if force_refresh:
            logger.info('[LOAD] 強制重新抓取股票資料...')
            self.raw_data, self.watchlist, self.stock_info = fetch_all_stock_data()
            self.last_update = datetime.now()
            if self.raw_data:
                save_stock_cache(self.raw_data, self.watchlist, self.stock_info)
                logger.info('[LOAD] 股票資料抓取完成 (%d 檔)', len(self.raw_data))
        else:
            self.raw_data, self.watchlist, self.stock_info, self.last_update = smart_load_or_fetch()

        if self.raw_data:
            logger.info('[LOAD] 原始資料就緒 (最後更新: %s)', self.last_update)
            logger.info('[LOAD] raw_data: %d 檔股票', len(self.raw_data))

        # 日期對齊
        logger.info('[ALIGN] 對齊股票日期...')
        self.aligned_data, self.unified_dates = align_data_with_bfill(self.raw_data)
        n_dates = len(self.unified_dates) if self.unified_dates is not None else 0
        logger.info('[ALIGN] 完成: %d 個交易日', n_dates)

        # 建立收盤價矩陣
        self._close_df = build_close_df(self.aligned_data)

        # 計算指標
        logger.info('[INDICATOR] 計算衍生指標...')
        self.sharpe_matrix, self.ranking_matrix, self.growth_matrix = calculate_all_indicators(self.aligned_data)
        logger.info('[INDICATOR] 計算完成')

        # 載入匯率
        logger.info('[FX] 載入匯率資料...')
        self.fx = FX(use_cache=True)
        logger.info('[FX] %s', self.fx)

        self.initialized = True
    
    def refresh(self):
        """強制重新抓取資料"""
        self.load_or_fetch(force_refresh=True)
    
    # ===== 收盤價矩陣 =====
    
    def get_close_df(self, market: str = 'global') -> pd.DataFrame:
        """
        取得收盤價矩陣，可選擇市場過濾
        
        Args:
            market: 'us' | 'tw' | 'global'
            
        Returns:
            pd.DataFrame: 收盤價矩陣 [Date x Symbol]
        """
        if self._close_df is None or self._close_df.empty:
            return pd.DataFrame()
        
        if market == 'global':
            return self._close_df.copy()
        
        filtered_df, _ = filter_by_market(self._close_df, self.stock_info, market)
        return filtered_df
    
    def get_filtered_stock_info(self, market: str = 'global') -> dict:
        """取得過濾後的股票資訊"""
        if market == 'global':
            return self.stock_info.copy()
        
        _, filtered_info = filter_by_market(self._close_df, self.stock_info, market)
        return filtered_info
    
    # ===== 股票清單查詢 =====
    
    def get_all_tickers(self) -> List[str]:
        """取得所有股票代碼"""
        return list(self.aligned_data.keys())
    
    def get_tickers_by_country(self, country: str) -> List[str]:
        """依國家篩選股票"""
        return [
            ticker for ticker, info in self.stock_info.items()
            if info.get('country') == country and ticker in self.aligned_data
        ]
    
    def get_tickers_by_industry(self, industry: str) -> List[str]:
        """依產業篩選股票"""
        return [
            ticker for ticker, info in self.stock_info.items()
            if info.get('industry') == industry and ticker in self.aligned_data
        ]
    
    def get_stock_info(self, ticker: str) -> dict:
        """取得股票資訊"""
        return self.stock_info.get(ticker, {})
    
    def get_industries(self) -> List[str]:
        """取得所有產業名稱"""
        return list(self.watchlist.keys())
    
    # ===== 價格數據查詢 =====
    
    def get_stock_price(self, ticker: str, date: str) -> dict:
        """取得股票在特定日期的價格"""
        if ticker not in self.aligned_data:
            return {'error': f'股票 {ticker} 不存在'}
        
        df = self.aligned_data[ticker]
        
        try:
            target_date = pd.to_datetime(date).strftime('%Y-%m-%d')
            matched = df[df.index.astype(str).str[:10] == target_date]
            
            if matched.empty:
                return {'error': f'找不到 {ticker} 在 {date} 的資料'}
            
            row = matched.iloc[0]
            info = self.stock_info.get(ticker, {})
            
            return {
                'ticker': ticker,
                'date': target_date,
                'open': float(row['Open']),
                'high': float(row['High']),
                'low': float(row['Low']),
                'close': float(row['Close']),
                'country': info.get('country', ''),
                'industry': info.get('industry', '')
            }
        except Exception as e:
            return {'error': str(e)}
    
    def get_stock_ohlcv(self, ticker: str) -> Optional[pd.DataFrame]:
        """取得股票完整 OHLCV 資料"""
        if ticker not in self.aligned_data:
            return None
        
        df = self.aligned_data[ticker].copy()
        df.index = df.index.astype(str).str[:10]
        return df
    
    # ===== Sharpe 數據查詢 =====
    
    def get_stock_sharpe(self, ticker: str) -> pd.Series:
        """取得單一股票的 Sharpe 時間序列"""
        if self.sharpe_matrix is None or ticker not in self.sharpe_matrix.columns:
            return pd.Series(dtype=float)
        return self.sharpe_matrix[ticker]
    
    def get_sharpe_matrix(self, start_date: str = None, 
                         end_date: str = None) -> pd.DataFrame:
        """取得 Sharpe 矩陣"""
        if self.sharpe_matrix is None:
            return pd.DataFrame()
        
        df = self.sharpe_matrix.copy()
        
        if start_date:
            df = df[df.index >= start_date]
        if end_date:
            df = df[df.index <= end_date]
        
        return df
    
    def get_daily_sharpe_summary(self, date: str = None) -> dict:
        """取得特定日期的 Sharpe 摘要（按國家分組）"""
        if self.sharpe_matrix is None or self.sharpe_matrix.empty:
            return {'date': None, 'US': {}, 'TW': {}}
        
        if date:
            target_str = str(date)[:10]
            matched_dates = [d for d in self.sharpe_matrix.index if str(d)[:10] == target_str]
            if not matched_dates:
                return {'date': date, 'US': {}, 'TW': {}}
            actual_date = matched_dates[0]
        else:
            actual_date = self.sharpe_matrix.index[-1]
        
        row = self.sharpe_matrix.loc[actual_date]
        
        us_tickers = set(self.get_tickers_by_country('US'))
        tw_tickers = set(self.get_tickers_by_country('TW'))
        
        def summarize(tickers_set):
            values = row[row.index.isin(tickers_set)].dropna()
            if values.empty:
                return {'count': 0, 'mean': 0, 'max': 0, 'top3': []}
            
            top3 = values.nlargest(3)
            return {
                'count': len(values),
                'mean': round(values.mean(), 3),
                'max': round(values.max(), 3),
                'top3': [{'ticker': t, 'sharpe': round(v, 3)} for t, v in top3.items()]
            }
        
        return {
            'date': str(actual_date)[:10],
            'US': summarize(us_tickers),
            'TW': summarize(tw_tickers)
        }
    
    # ===== 排名與 Growth 數據查詢 =====
    
    def get_ranking_matrix(self, start_date: str = None, 
                          end_date: str = None) -> pd.DataFrame:
        """取得排名矩陣"""
        if self.ranking_matrix is None:
            return pd.DataFrame()
        
        df = self.ranking_matrix.copy()
        
        if start_date:
            df = df[df.index >= start_date]
        if end_date:
            df = df[df.index <= end_date]
        
        return df
    
    def get_growth_matrix(self, start_date: str = None, 
                         end_date: str = None) -> pd.DataFrame:
        """取得排名變化矩陣"""
        if self.growth_matrix is None:
            return pd.DataFrame()
        
        df = self.growth_matrix.copy()
        
        if start_date:
            df = df[df.index >= start_date]
        if end_date:
            df = df[df.index <= end_date]
        
        return df

    # ===== 市場資料委派方法（透過 market_loader） =====

    def get_market_data(self, period: str, aligned_data: dict = None) -> dict:
        """取得市場看板資料（NASDAQ/TWII/黃金/BTC/債券 K 線）"""
        return self.market_loader.get_all_market_data(
            period, aligned_data or self.aligned_data
        )

    def get_kline(self, symbol: str, period: str, aligned_data: dict = None) -> list:
        """取得單一標的 K 線資料"""
        return self.market_loader.get_weighted_kline(
            symbol, period, aligned_data or self.aligned_data
        )

    def get_exchange_rate(self) -> float:
        """取得當前美元兌台幣匯率"""
        return self.market_loader.get_exchange_rate()

    def get_exchange_rate_history(self, period: str) -> dict:
        """取得歷史匯率資料"""
        return self.market_loader.get_exchange_rate_history(period)


# =============================================================================
# 全域實例（供各模組 import 使用）
# =============================================================================

container = DataContainer()
