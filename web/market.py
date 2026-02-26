"""
市場數據加載器

負責載入市場指數、匯率等數據
"""
import pickle
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Optional

import pandas as pd
import yfinance as yf

from core.config import CACHE_DIR, MARKET_CACHE_FILE


class MarketDataLoader:
    """
    市場數據加載器
    
    設計原則：
    - 初始化時載入所有市場資料（max 範圍）
    - 伺服器運行期間只從快取讀取，不再從 yfinance 抓取
    - 不同 period 從已載入的資料中切片
    """
    
    # 預載的市場指數（包含匯率 TWD=X）
    MARKET_SYMBOLS = ['^IXIC', '^TWII', 'GC=F', 'BTC-USD', 'TLT', '^GSPC', 'TWD=X']
    
    def __init__(self):
        self.cache: Dict[str, pd.DataFrame] = {}
        self.cache_time: Dict[str, datetime] = {}
        self.exchange_rate: float = 32.0
        self.initialized: bool = False
        
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        self._load_cache_from_disk()
    
    def _load_cache_from_disk(self) -> bool:
        """從磁碟載入快取"""
        if not MARKET_CACHE_FILE.exists():
            print(f"⚠️ 市場快取檔案不存在: {MARKET_CACHE_FILE}")
            return False
        
        try:
            print(f"📥 正在讀取市場快取檔案...")
            with open(MARKET_CACHE_FILE, 'rb') as f:
                saved = pickle.load(f)
                self.cache = saved.get('data', {})
                self.cache_time = saved.get('time', {})
                self.exchange_rate = saved.get('exchange_rate', 32.0)
                print(f"✅ 載入市場資料快取成功")
                print(f"   - 共 {len(self.cache)} 個 symbol")
                for sym, df in self.cache.items():
                    if isinstance(df, pd.DataFrame):
                        print(f"   - {sym}: {len(df)} 筆資料")
                return True
        except Exception as e:
            print(f"⚠️ 載入市場快取失敗: {e}")
            print(f"   提示: 可能是 pandas 版本不相容，需重新產生 cache")
            return False
    
    def _save_cache_to_disk(self):
        """將快取存入磁碟"""
        try:
            with open(MARKET_CACHE_FILE, 'wb') as f:
                pickle.dump({
                    'data': self.cache,
                    'time': self.cache_time,
                    'exchange_rate': self.exchange_rate
                }, f)
            print(f"   ✅ 已儲存至 {MARKET_CACHE_FILE}")
        except Exception as e:
            print(f"   ❌ 儲存市場快取失敗: {e}")
    
    def _has_cache(self, symbol: str) -> bool:
        """檢查是否有該 symbol 的快取"""
        return symbol in self.cache and not self.cache[symbol].empty
    
    def _filter_by_period(self, df: pd.DataFrame, period: str) -> pd.DataFrame:
        """根據 period 過濾 DataFrame"""
        if df.empty:
            return df
        
        period_days = {
            '1mo': 30, '3mo': 90, '6mo': 180,
            '1y': 365, '2y': 730, '5y': 1825, '6y': 2190
        }
        
        if period in period_days:
            cutoff = datetime.now() - timedelta(days=period_days[period])
            return df[df.index >= cutoff].copy()
        
        return df.copy()
    
    def preload_all(self, aligned_data: dict = None, max_staleness_days: int = 1):
        """
        預載所有市場資料（智慧快取策略）
        
        Args:
            aligned_data: 已對齊的股票資料
            max_staleness_days: 允許的最大過期天數
        """
        print(f"\n🔄 開始預載市場資料...")
        
        now = datetime.now()
        today = now.date()
        rate_limited = False
        
        for symbol in self.MARKET_SYMBOLS:
            print(f"\n   📊 處理 {symbol}...")
            
            # 檢查快取
            if symbol in self.cache and isinstance(self.cache[symbol], pd.DataFrame):
                cached_df = self.cache[symbol]
                if not cached_df.empty:
                    cache_latest_date = cached_df.index[-1].date()
                    days_diff = (today - cache_latest_date).days
                    
                    if days_diff <= max_staleness_days:
                        print(f"      ✅ 快取有效")
                        continue
            
            if rate_limited:
                print(f"      ⚠️ 已被限速，跳過")
                continue
            
            # 從 aligned_data 讀取
            if aligned_data and symbol in aligned_data:
                df = aligned_data[symbol].copy()
                if not df.empty:
                    print(f"      ✅ 從 aligned_data 載入 ({len(df)} 筆)")
                    self.cache[symbol] = df
                    self.cache_time[symbol] = now
                    continue
            
            # 從 yfinance 抓取
            try:
                print(f"      📥 從 yfinance 抓取...")
                ticker = yf.Ticker(symbol)
                df = ticker.history(period="max", interval="1d")
                
                if df.empty:
                    print(f"      ❌ 無資料")
                    continue
                
                df = df.tz_localize(None)
                df = df.sort_index()
                print(f"      ✅ 成功 ({len(df)} 筆)")
                self.cache[symbol] = df
                self.cache_time[symbol] = now
                
            except Exception as e:
                print(f"      ❌ 失敗: {e}")
                if "Rate limited" in str(e) or "Too Many Requests" in str(e):
                    rate_limited = True
        
        # 設定匯率
        if self._has_cache('TWD=X'):
            self.exchange_rate = round(self.cache['TWD=X']['Close'].iloc[-1], 2)
            print(f"\n   💱 匯率: {self.exchange_rate}")
        
        self._save_cache_to_disk()
        self.initialized = True
        print(f"✅ 市場資料預載完成\n")
    
    def get_index_data(self, symbol: str, period: str = "2y", 
                       aligned_data: dict = None) -> pd.DataFrame:
        """獲取指數歷史數據"""
        if self._has_cache(symbol):
            return self._filter_by_period(self.cache[symbol], period)
        
        if aligned_data and symbol in aligned_data:
            df = aligned_data[symbol].copy()
            return self._filter_by_period(df, period)
        
        if self.initialized:
            return pd.DataFrame()
        
        # 初始化期間允許抓取
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period="max", interval="1d")
            df = df.tz_localize(None).sort_index()
            
            if not df.empty:
                self.cache[symbol] = df
                self.cache_time[symbol] = datetime.now()
                self._save_cache_to_disk()
            
            return self._filter_by_period(df, period)
        except Exception as e:
            print(f"Error fetching {symbol}: {e}")
            return pd.DataFrame()
    
    def get_weighted_kline(self, symbol: str, period: str = "2y", 
                          aligned_data: dict = None) -> list:
        """獲取 K 線數據（供前端圖表）"""
        df = self.get_index_data(symbol, period, aligned_data)
        
        if df.empty:
            return []
        
        kline_data = []
        for idx, row in df.iterrows():
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
    
    def get_global_weighted_index(self, period: str = "2y", 
                                  aligned_data: dict = None) -> list:
        """
        計算國際加權指數 (NASDAQ 與台股 1:1 權重)
        
        正確做法：以台幣計價
        - 先把 NASDAQ 的 USD 價格用當天匯率換成 TWD
        - 再跟 TWII (本身已是 TWD) 做 1:1 加權平均
        """
        nasdaq_df = self.get_index_data('^IXIC', period, aligned_data)
        twii_df = self.get_index_data('^TWII', period, aligned_data)
        
        if nasdaq_df.empty or twii_df.empty:
            return []
        
        # 獲取匯率資料
        fx_history = self.get_exchange_rate_history('6y')
        
        common_dates = nasdaq_df.index.intersection(twii_df.index)
        if len(common_dates) == 0:
            return []
        
        kline_data = []
        first_nq_twd = None
        first_tw = None
        
        for date in sorted(common_dates):
            date_str = date.strftime('%Y-%m-%d')
            nq = nasdaq_df.loc[date]
            tw = twii_df.loc[date]
            
            # 獲取當天匯率（找最近有效匯率）
            fx_rate = fx_history.get(date_str)
            if fx_rate is None:
                # 找最近的匯率
                for d in sorted(fx_history.keys(), reverse=True):
                    if d <= date_str:
                        fx_rate = fx_history[d]
                        break
            if fx_rate is None:
                fx_rate = self.exchange_rate  # 預設匯率
            
            # 將 NASDAQ 換成台幣
            nq_open_twd = nq['Open'] * fx_rate
            nq_high_twd = nq['High'] * fx_rate
            nq_low_twd = nq['Low'] * fx_rate
            nq_close_twd = nq['Close'] * fx_rate
            
            # 記錄第一天的價格（用於標準化）
            if first_nq_twd is None:
                first_nq_twd = nq_close_twd
                first_tw = tw['Close']
            
            # 標準化後加權（讓兩者從相同起點 100 開始）
            nq_normalized = (nq_close_twd / first_nq_twd) * 100
            tw_normalized = (tw['Close'] / first_tw) * 100
            
            # 1:1 加權平均
            weighted_close = (nq_normalized + tw_normalized) / 2
            
            # open/high/low 也做類似處理（用收盤價比例近似）
            if nq_close_twd > 0 and tw['Close'] > 0:
                nq_open_norm = (nq_open_twd / first_nq_twd) * 100
                nq_high_norm = (nq_high_twd / first_nq_twd) * 100
                nq_low_norm = (nq_low_twd / first_nq_twd) * 100
                tw_open_norm = (tw['Open'] / first_tw) * 100
                tw_high_norm = (tw['High'] / first_tw) * 100
                tw_low_norm = (tw['Low'] / first_tw) * 100
                
                weighted_open = (nq_open_norm + tw_open_norm) / 2
                weighted_high = (nq_high_norm + tw_high_norm) / 2
                weighted_low = (nq_low_norm + tw_low_norm) / 2
            else:
                weighted_open = weighted_close
                weighted_high = weighted_close
                weighted_low = weighted_close
            
            actual_high = max(weighted_open, weighted_high, weighted_low, weighted_close)
            actual_low = min(weighted_open, weighted_high, weighted_low, weighted_close)
            
            kline_data.append({
                'time': date_str,
                'open': round(weighted_open, 2),
                'high': round(actual_high, 2),
                'low': round(actual_low, 2),
                'close': round(weighted_close, 2),
                'volume': int(nq['Volume'] + tw['Volume'])
            })
        
        return kline_data
    
    def get_all_market_data(self, period: str = "2y", aligned_data: dict = None) -> dict:
        """獲取所有市場數據"""
        return {
            'global': self.get_global_weighted_index(period, aligned_data),
            'nasdaq': self.get_weighted_kline('^IXIC', period, aligned_data),
            'twii': self.get_weighted_kline('^TWII', period, aligned_data),
            'gold': self.get_weighted_kline('GC=F', period, aligned_data),
            'btc': self.get_weighted_kline('BTC-USD', period, aligned_data),
            'bonds': self.get_weighted_kline('TLT', period, aligned_data)
        }
    
    def get_exchange_rate(self) -> float:
        """獲取美元兌台幣匯率"""
        return self.exchange_rate
    
    def get_exchange_rate_history(self, period: str = "6y") -> dict:
        """獲取歷史匯率數據"""
        if not self._has_cache('TWD=X'):
            return {}
        
        df = self._filter_by_period(self.cache['TWD=X'], period)
        if df.empty:
            return {}
        
        return {
            date.strftime('%Y-%m-%d'): round(row['Close'], 4)
            for date, row in df.iterrows()
        }
