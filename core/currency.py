"""
FinPack 貨幣處理模組 (簡化版)

使用範例：
    from core.currency import Money, twd, usd, FX
    
    capital = twd(1_000_000)
    price = usd(150.0)
    
    # 同幣別可運算
    total = twd(100) + twd(200)  # TWD 300
    
    # 不同幣別會報錯
    total = twd(100) + usd(10)   # CurrencyMismatchError
    
    # 換匯
    fx = FX()
    price_twd = fx.to_twd(price, date='2024-01-15')
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional, Union
import pandas as pd


# =============================================================================
# 幣別與錯誤
# =============================================================================

class Currency(Enum):
    """幣別"""
    TWD = 'TWD'
    USD = 'USD'
    
    def __str__(self) -> str:
        return self.value


class CurrencyMismatchError(TypeError):
    """幣別不匹配"""
    def __init__(self, left: Currency, right: Currency, op: str):
        super().__init__(f"幣別不匹配: {left} {op} {right}")


# =============================================================================
# Money 類型
# =============================================================================

@dataclass(frozen=False)
class Money:
    """
    帶幣別的金額
    
    只有相同幣別才能加減，乘除用於數量計算（如股數）。
    """
    amount: float
    currency: Currency
    
    def __post_init__(self):
        if isinstance(self.currency, str):
            object.__setattr__(self, 'currency', Currency(self.currency.upper()))
    
    # --- 加減 ---
    def __add__(self, other: Money) -> Money:
        if not isinstance(other, Money):
            return NotImplemented
        if self.currency != other.currency:
            raise CurrencyMismatchError(self.currency, other.currency, '+')
        return Money(self.amount + other.amount, self.currency)
    
    def __radd__(self, other):
        if other == 0:  # 支援 sum()
            return self
        return self.__add__(other)
    
    def __sub__(self, other: Money) -> Money:
        if not isinstance(other, Money):
            return NotImplemented
        if self.currency != other.currency:
            raise CurrencyMismatchError(self.currency, other.currency, '-')
        return Money(self.amount - other.amount, self.currency)
    
    # --- 乘除 ---
    def __mul__(self, n: Union[int, float]) -> Money:
        if isinstance(n, Money):
            raise TypeError("Money 不能與 Money 相乘")
        return Money(self.amount * n, self.currency)
    
    def __rmul__(self, n: Union[int, float]) -> Money:
        return self.__mul__(n)
    
    def __truediv__(self, other: Union[int, float, Money]) -> Union[Money, float]:
        if isinstance(other, Money):
            if self.currency != other.currency:
                raise CurrencyMismatchError(self.currency, other.currency, '/')
            return self.amount / other.amount  # 比率
        return Money(self.amount / other, self.currency)
    
    def __floordiv__(self, n: Union[int, float]) -> int:
        """整除，用於計算可買股數"""
        return int(self.amount // n)
    
    # --- 比較 ---
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Money):
            return False
        return self.currency == other.currency and abs(self.amount - other.amount) < 1e-6
    
    def __lt__(self, other: Money) -> bool:
        if self.currency != other.currency:
            raise CurrencyMismatchError(self.currency, other.currency, '<')
        return self.amount < other.amount
    
    def __le__(self, other: Money) -> bool:
        return self == other or self < other
    
    def __gt__(self, other: Money) -> bool:
        if self.currency != other.currency:
            raise CurrencyMismatchError(self.currency, other.currency, '>')
        return self.amount > other.amount
    
    def __ge__(self, other: Money) -> bool:
        return self == other or self > other
    
    # --- 其他 ---
    def __neg__(self) -> Money:
        return Money(-self.amount, self.currency)
    
    def __abs__(self) -> Money:
        return Money(abs(self.amount), self.currency)
    
    def __bool__(self) -> bool:
        return self.amount != 0
    
    def __float__(self) -> float:
        return float(self.amount)
    
    def __repr__(self) -> str:
        return f"Money({self.amount:,.2f}, {self.currency})"
    
    def __str__(self) -> str:
        if self.currency == Currency.TWD:
            return f"${self.amount:,.0f} TWD"
        return f"${self.amount:,.2f} USD"
    
    def __hash__(self) -> int:
        return hash((round(self.amount, 6), self.currency))
    
    # --- 實用 ---
    def is_twd(self) -> bool:
        return self.currency == Currency.TWD
    
    def is_usd(self) -> bool:
        return self.currency == Currency.USD


# =============================================================================
# 工廠函數
# =============================================================================

def twd(amount: float) -> Money:
    """建立台幣"""
    return Money(amount, Currency.TWD)


def usd(amount: float) -> Money:
    """建立美元"""
    return Money(amount, Currency.USD)


# =============================================================================
# 匯率服務
# =============================================================================

import pickle


class FX:
    """
    匯率服務（USD/TWD）
    
    Usage:
        fx = FX(use_cache=True)   # 從 market_data.pkl 讀取
        fx = FX(use_cache=False)  # 從 yfinance 抓取最新
        
        rate = fx.rate('2024-01-15')
        twd_price = fx.to_twd(usd_price, '2024-01-15')
    """
    
    DEFAULT_RATE = 32.0
    
    def __init__(self, use_cache: bool = True):
        self._history: Dict[str, float] = {}
        self._latest = self.DEFAULT_RATE
        
        if use_cache:
            self._load_from_cache()
        else:
            self._fetch_from_yfinance()
    
    def _load_from_cache(self) -> None:
        """從 market_data.pkl 載入匯率"""
        from core.config import MARKET_CACHE_FILE
        
        if not MARKET_CACHE_FILE.exists():
            return
        
        try:
            with open(MARKET_CACHE_FILE, 'rb') as f:
                cache = pickle.load(f)
            twdx_df = cache.get('data', {}).get('TWD=X')
            if twdx_df is not None and not twdx_df.empty:
                self._load_from_df(twdx_df)
        except Exception:
            pass
    
    def _load_from_df(self, df: pd.DataFrame) -> None:
        """從 DataFrame 載入匯率"""
        self._history = {
            d.strftime('%Y-%m-%d'): round(float(r['Close']), 4)
            for d, r in df.iterrows() if pd.notna(r.get('Close'))
        }
        if self._history:
            self._latest = self._history[max(self._history.keys())]
    
    def _fetch_from_yfinance(self) -> None:
        """從 yfinance 抓取匯率"""
        try:
            import yfinance as yf
            df = yf.Ticker('TWD=X').history(period='6y', interval='1d')
            if not df.empty:
                self._load_from_df(df)
        except Exception:
            pass
    
    def rate(self, date: Optional[str] = None) -> float:
        """取得匯率 (1 USD = ? TWD)"""
        if date is None:
            return self._latest
        if date in self._history:
            return self._history[date]
        if self._history:
            for d in reversed(sorted(self._history.keys())):
                if d <= date:
                    return self._history[d]
        return self.DEFAULT_RATE
    
    def to_twd(self, m: Money, date: Optional[str] = None) -> Money:
        """轉換為台幣"""
        if m.is_twd():
            return m
        return twd(m.amount * self.rate(date))
    
    def to_usd(self, m: Money, date: Optional[str] = None) -> Money:
        """轉換為美元"""
        if m.is_usd():
            return m
        return usd(m.amount / self.rate(date))
    
    @property
    def latest(self) -> float:
        return self._latest
    
    @property
    def date_range(self) -> tuple:
        if not self._history:
            return (None, None)
        dates = sorted(self._history.keys())
        return (dates[0], dates[-1])
    
    def __repr__(self) -> str:
        start, end = self.date_range
        if start:
            return f"FX({start}~{end}, rate={self._latest:.2f})"
        return f"FX(rate={self._latest:.2f})"
