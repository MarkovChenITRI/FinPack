"""
BTC 資料容器

BTC-USD 單資產資料存取介面，供 run_btc.py 和 web 層使用。
取代原有的多股票 DataContainer，只處理 BTC-USD OHLCV。
"""
import logging
import pandas as pd
from datetime import datetime
from typing import Optional, Dict

from .config import CACHE_DIR
from .data import smart_load_btc, save_btc_cache

logger = logging.getLogger(__name__)


class BtcDataContainer:
    """
    BTC-USD 資料容器

    統一管理 BTC OHLCV 資料的載入與存取。
    支援多個時間框架的獨立快取。

    使用方式：
        container = BtcDataContainer()
        container.load('1d')
        df = container.get_ohlcv('1d')
    """

    def __init__(self):
        self._ohlcv: Dict[str, pd.DataFrame] = {}
        self._last_update: Dict[str, Optional[datetime]] = {}
        self.initialized = False
        CACHE_DIR.mkdir(parents=True, exist_ok=True)

    def load(
        self,
        timeframe: str = '1d',
        use_cache: bool = False,
        start: str = None,
        end: str = None,
    ) -> pd.DataFrame:
        """
        載入指定時間框架的 BTC-USD 資料

        Args:
            timeframe: '1d' | '4h' | '1h'
            use_cache: True = 強制使用本地快取（debug 模式）
            start:     可選起始日期（用於抓取時過濾）
            end:       可選結束日期

        Returns:
            pd.DataFrame (OHLCV)
        """
        logger.info('[BTC] 載入 %s 資料...', timeframe)
        df = smart_load_btc(
            timeframe = timeframe,
            use_cache = use_cache,
            start     = start,
            end       = end,
        )
        if not df.empty:
            self._ohlcv[timeframe] = df
            self._last_update[timeframe] = datetime.now()
            logger.info('[BTC] %s: %d 根 K 線 (%s ~ %s)',
                        timeframe, len(df),
                        str(df.index[0])[:10],
                        str(df.index[-1])[:10])
            self.initialized = True
        else:
            logger.error('[BTC] 無法載入 %s 資料', timeframe)

        return df

    def get_ohlcv(self, timeframe: str = '1d') -> pd.DataFrame:
        """取得已載入的 OHLCV DataFrame"""
        if timeframe not in self._ohlcv:
            return self.load(timeframe)
        return self._ohlcv[timeframe]

    def slice(
        self,
        start: str,
        end: str = None,
        timeframe: str = '1d',
    ) -> pd.DataFrame:
        """
        裁切 OHLCV 到指定日期範圍

        Args:
            start:     'YYYY-MM-DD'
            end:       'YYYY-MM-DD'（None = 最後一天）
            timeframe: '1d' | '4h' | '1h'
        """
        df = self.get_ohlcv(timeframe)
        if df.empty:
            return df

        mask = df.index >= pd.Timestamp(start)
        if end:
            mask &= df.index <= pd.Timestamp(end)

        return df[mask].copy()

    @property
    def latest_close(self) -> float:
        """最新收盤價（日線）"""
        df = self.get_ohlcv('1d')
        if df.empty:
            return 0.0
        return float(df['Close'].iloc[-1])

    def __repr__(self) -> str:
        loaded = list(self._ohlcv.keys())
        return f"BtcDataContainer(loaded={loaded})"


# =============================================================================
# 全域實例（供各模組 import 使用）
# =============================================================================

container = BtcDataContainer()
