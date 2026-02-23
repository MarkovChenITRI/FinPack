"""
FinPack 資料容器 (Singleton)

統一的資料存取介面，供 engine/ 各模組使用
"""
import pandas as pd
from datetime import datetime
from typing import Optional

from .config import CACHE_DIR
from .data import (
    load_stock_cache, save_stock_cache, fetch_all_stock_data,
    MarketDataLoader, get_usd_twd_rate
)
from .align import align_data_with_bfill
from .indicator import calculate_all_indicators


class DataContainer:
    """
    資料容器：封裝所有資料存取操作
    
    使用 Singleton 模式，全域共用一個實例
    """
    
    def __init__(self, auto_load: bool = True):
        # 原始資料（快取）
        self.raw_data = {}
        self.watchlist = {}
        self.stock_info = {}
        self.last_update: Optional[datetime] = None
        
        # 衍生資料（動態計算）
        self.aligned_data = {}
        self.unified_dates: Optional[pd.DatetimeIndex] = None
        self.sharpe_matrix: Optional[pd.DataFrame] = None   # Sharpe Ratio 原始值
        self.ranking_matrix: Optional[pd.DataFrame] = None  # Sharpe 排名 (1 = 最高)
        self.growth_matrix: Optional[pd.DataFrame] = None   # 排名變化 (正值 = 上升)
        
        # 市場數據加載器
        self.market_loader = MarketDataLoader()
        
        self.initialized = False
        
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        
        if auto_load:
            self.load_or_fetch()
    
    def load_or_fetch(self, force_refresh: bool = False):
        """載入快取或重新抓取資料"""
        if not force_refresh:
            self.raw_data, self.watchlist, self.stock_info, self.last_update = load_stock_cache()
        
        if self.raw_data:
            print(f"✅ 從快取載入原始資料 (最後更新: {self.last_update})")
            print(f"  📦 raw_data: {len(self.raw_data)} 檔股票")
        else:
            print("📥 開始抓取股票資料...")
            self.raw_data, self.watchlist, self.stock_info = fetch_all_stock_data()
            self.last_update = datetime.now()
            save_stock_cache(self.raw_data, self.watchlist, self.stock_info)
            print(f"✅ 股票資料抓取完成 ({len(self.raw_data)} 檔股票)")
        
        # 日期對齊
        print("📅 對齊股票日期（bfill）...")
        self.aligned_data, self.unified_dates = align_data_with_bfill(self.raw_data)
        print(f"✅ 日期對齊完成")
        print(f"  📅 unified_dates: {len(self.unified_dates) if self.unified_dates is not None else 0} 個交易日")
        print(f"  📦 aligned_data: {len(self.aligned_data)} 檔股票")
        
        # 計算指標
        print("📊 計算衍生指標...")
        self.sharpe_matrix, self.ranking_matrix, self.growth_matrix = calculate_all_indicators(self.aligned_data)
        print(f"✅ 指標計算完成")
        print(f"  📊 sharpe_matrix: {self.sharpe_matrix.shape if self.sharpe_matrix is not None and not self.sharpe_matrix.empty else 'None/Empty'}")
        print(f"  📊 ranking_matrix: {self.ranking_matrix.shape if self.ranking_matrix is not None and not self.ranking_matrix.empty else 'None/Empty'}")
        print(f"  📊 growth_matrix: {self.growth_matrix.shape if self.growth_matrix is not None and not self.growth_matrix.empty else 'None/Empty'}")
        
        # 預先載入市場資料
        print("📈 預先載入市場資料...")
        self.market_loader.preload_all(self.aligned_data)
        print(f"✅ 市場資料載入完成")
        
        self.initialized = True
    
    def refresh(self):
        """強制重新抓取資料"""
        self.load_or_fetch(force_refresh=True)
    
    # ===== 股票清單查詢 =====
    
    def get_all_tickers(self) -> list:
        """取得所有股票代碼"""
        return list(self.aligned_data.keys())
    
    def get_tickers_by_country(self, country: str) -> list:
        """依國家篩選股票"""
        return [
            ticker for ticker, info in self.stock_info.items()
            if info.get('country') == country and ticker in self.aligned_data
        ]
    
    def get_tickers_by_industry(self, industry: str) -> list:
        """依產業篩選股票"""
        return [
            ticker for ticker, info in self.stock_info.items()
            if info.get('industry') == industry and ticker in self.aligned_data
        ]
    
    def get_stock_info(self, ticker: str) -> dict:
        """取得股票資訊"""
        return self.stock_info.get(ticker, {})
    
    def get_industries(self) -> list:
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
    
    def get_sharpe_matrix(self, start_date: str = None, end_date: str = None) -> pd.DataFrame:
        """取得 Sharpe 矩陣（可選日期範圍）"""
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
    
    def get_ranking_matrix(self, start_date: str = None, end_date: str = None) -> pd.DataFrame:
        """
        取得排名矩陣（可選日期範圍）
        
        排名值 1 = 當日 Sharpe 最高的股票
        用於：sharpe_rank 條件判斷（Sharpe Top-N）
        """
        if self.ranking_matrix is None:
            return pd.DataFrame()
        
        df = self.ranking_matrix.copy()
        
        if start_date:
            df = df[df.index >= start_date]
        if end_date:
            df = df[df.index <= end_date]
        
        return df
    
    def get_growth_matrix(self, start_date: str = None, end_date: str = None) -> pd.DataFrame:
        """
        取得排名變化矩陣（可選日期範圍）
        
        正值 = 排名上升（如 #20 → #10 = +10）
        負值 = 排名下降（如 #10 → #20 = -10）
        用於：growth_rank/growth_streak 成長動能條件、Growth Top-N 選股
        """
        if self.growth_matrix is None:
            return pd.DataFrame()
        
        df = self.growth_matrix.copy()
        
        if start_date:
            df = df[df.index >= start_date]
        if end_date:
            df = df[df.index <= end_date]
        
        return df
    
    # ===== 市場數據查詢 =====
    
    def get_market_data(self, period: str = '1y') -> dict:
        """取得所有市場數據"""
        return self.market_loader.get_all_market_data(period, self.aligned_data)
    
    def get_kline(self, symbol: str, period: str = '1y') -> list:
        """取得指定標的 K 線數據"""
        return self.market_loader.get_weighted_kline(symbol, period, self.aligned_data)
    
    def get_exchange_rate(self) -> float:
        """取得美元兌台幣匯率"""
        return self.market_loader.get_exchange_rate()
    
    def get_exchange_rate_history(self) -> dict:
        """取得歷史匯率數據 {date: rate}"""
        return self.market_loader.get_exchange_rate_history()


# ===== Singleton 實例 =====

_container: Optional[DataContainer] = None


def get_container() -> DataContainer:
    """取得資料容器（Singleton）"""
    global _container
    if _container is None:
        _container = DataContainer(auto_load=True)
    return _container


def refresh_container() -> DataContainer:
    """強制重新載入資料"""
    global _container
    _container = DataContainer(auto_load=False)
    _container.load_or_fetch(force_refresh=True)
    return _container
