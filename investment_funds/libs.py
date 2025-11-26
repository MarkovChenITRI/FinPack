"""
FinBuddy Trading System - 完整庫文件
適用於 Google Cloud Functions 部署
"""

import requests
import yfinance as yf
import numpy as np
import pandas as pd
from scipy.stats import linregress
from scipy.optimize import linprog
from scipy.signal import find_peaks
from sklearn.linear_model import LogisticRegression
from dataclasses import dataclass
from typing import Dict, List, Union
from abc import ABC, abstractmethod
import warnings

warnings.simplefilter(action='ignore', category=pd.errors.PerformanceWarning)


# ============================================================================
# 數據結構
# ============================================================================

@dataclass
class PortfolioSnapshot:
    """投資組合快照 - 記錄每日狀態"""
    timestamp: pd.Timestamp
    cash: float
    positions: Dict[str, int]  # {ticker: units}
    total_value: float


# ============================================================================
# 策略模組
# ============================================================================

class BaseStrategy(ABC):
    """策略基類"""
    
    @abstractmethod
    def calculate_weights(self, market_data: pd.Series, codes: list) -> dict:
        """計算投資組合配置權重"""
        pass


class MaxSharpeStrategy(BaseStrategy):
    """最大夏普策略 - 選擇 Sharpe 最高的前 topk 檔股票"""
    
    def __init__(self, topk: int = 5, max_weight: float = 0.2):
        self.topk = topk
        self.max_weight = max_weight
        
    def calculate_weights(self, market_data: pd.Series, codes: list) -> dict:
        """按 Sharpe 排序並分配權重"""
        weights = {code: 0.0 for code in codes}
        
        # 收集有效股票 (Sharpe > 0)
        valid_stocks = []
        for code in codes:
            sharpe_key = f"{code}_Sharpe"
            price_key = f"{code}_Close"
            
            if sharpe_key in market_data.index and price_key in market_data.index:
                sharpe = market_data[sharpe_key]
                price = market_data[price_key]
                
                if pd.notna(sharpe) and pd.notna(price) and sharpe > 0 and price > 0:
                    valid_stocks.append((code, sharpe))
        
        if not valid_stocks:
            weights['CASH'] = 1.0
            return weights
        
        # 按 Sharpe 降序排序, 取前 topk
        valid_stocks.sort(key=lambda x: x[1], reverse=True)
        selected = valid_stocks[:self.topk]
        
        # 平均分配權重
        remaining = 1.0
        for code, _ in selected:
            alloc = min(self.max_weight, remaining)
            weights[code] = alloc
            remaining -= alloc
            if remaining <= 0:
                break
        
        weights['CASH'] = remaining
        return weights


class LinearProgrammingStrategy(BaseStrategy):
    """線性規劃策略 - 在 Beta 約束下最大化 Sharpe"""
    
    def __init__(self, max_weight: float = 0.2, enable_beta_constraint: bool = True):
        self.max_weight = max_weight
        self.enable_beta_constraint = enable_beta_constraint
        
    def calculate_weights(self, market_data: pd.Series, codes: list) -> dict:
        """用線性規劃求解最佳權重"""
        weights = {code: 0.0 for code in codes}
        
        # 收集有效股票
        valid_codes = []
        sharpe_list = []
        beta_list = []
        
        for code in codes:
            sharpe_key = f"{code}_Sharpe"
            beta_key = f"{code}_Beta"
            price_key = f"{code}_Close"
            
            if all(k in market_data.index for k in [sharpe_key, beta_key, price_key]):
                sharpe = market_data[sharpe_key]
                beta = market_data[beta_key]
                price = market_data[price_key]
                
                if all(pd.notna(v) and np.isfinite(v) for v in [sharpe, beta, price]) and price > 0:
                    valid_codes.append(code)
                    sharpe_list.append(sharpe)
                    beta_list.append(beta)
        
        if not valid_codes:
            weights['CASH'] = 1.0
            return weights
        
        # 設定線性規劃問題
        n = len(valid_codes)
        sharpe = np.array(sharpe_list)
        beta = np.array(beta_list)
        
        # 目標函數: 最大化 Sharpe (轉為最小化 -Sharpe)
        c = -sharpe
        
        # 等式約束: 總權重 = 1
        A_eq = [np.ones(n)]
        b_eq = [1.0]
        
        # 不等式約束: Beta 限制
        A_ub = []
        b_ub = []
        
        if self.enable_beta_constraint and 'betas' in market_data.index:
            beta_threshold = market_data['betas']
            if pd.notna(beta_threshold) and np.isfinite(beta_threshold):
                A_ub.append(beta)
                b_ub.append(beta_threshold)
        
        # 邊界: 0 <= weight <= max_weight
        bounds = [(0, self.max_weight) for _ in range(n)]
        
        # 求解
        res = linprog(
            c, 
            A_ub=A_ub or None, 
            b_ub=b_ub or None,
            A_eq=A_eq, 
            b_eq=b_eq, 
            bounds=bounds, 
            method="highs"
        )
        
        # 處理結果
        if res.success and res.x.sum() > 1e-6:
            for i, code in enumerate(valid_codes):
                weights[code] = res.x[i]
        else:
            weights['CASH'] = 1.0
        
        return weights


# ============================================================================
# Trader 模組
# ============================================================================

class Trader:
    """交易員 - 管理資金、持倉與策略執行"""
    
    def __init__(self, balance: float, strategy: BaseStrategy, rebalance_frequency: str = 'daily'):
        self.initial_balance = balance
        self.cash = balance
        self.inventory = {}  # {ticker: units}
        self.strategy = strategy
        self.rebalance_frequency = rebalance_frequency.lower()
        
        self.portfolio_history = []  # List[PortfolioSnapshot]
        self.last_rebalance_date = None
        
    def _should_rebalance(self, current_date: pd.Timestamp) -> bool:
        """判斷是否該執行 rebalance"""
        if self.last_rebalance_date is None:
            return True
            
        if self.rebalance_frequency == 'daily':
            return True
        elif self.rebalance_frequency == 'weekly':
            return current_date.weekday() == 0 and \
                   (current_date - self.last_rebalance_date).days >= 7
        elif self.rebalance_frequency == 'monthly':
            return current_date.month != self.last_rebalance_date.month
        elif self.rebalance_frequency == 'quarterly':
            quarter_months = [1, 4, 7, 10]
            return current_date.month in quarter_months and \
                   current_date.month != self.last_rebalance_date.month
        elif self.rebalance_frequency == 'yearly':
            return current_date.year != self.last_rebalance_date.year
        
        return False
        
    def decide(self, market_data: pd.Series, codes: list) -> Dict[str, float]:
        """根據策略決定配置權重"""
        return self.strategy.calculate_weights(market_data, codes)
        
    def execute_trades(self, weights: Dict[str, float], market_data: pd.Series):
        """執行交易 - 根據權重調整持倉"""
        current_value = self.get_portfolio_value(market_data)
        
        # 計算目標持倉
        new_inventory = {}
        for ticker, weight in weights.items():
            if ticker == 'CASH':
                continue
                
            price_key = f'{ticker}_Close'
            if price_key not in market_data.index:
                continue
                
            price = market_data[price_key]
            if pd.isna(price) or price <= 0:
                continue
                
            if weight > 0:
                target_value = current_value * weight
                units = int(target_value / price)
                if units > 0:
                    new_inventory[ticker] = units
        
        # 計算實際使用金額
        used = sum(
            units * market_data[f'{ticker}_Close']
            for ticker, units in new_inventory.items()
            if f'{ticker}_Close' in market_data.index
        )
        
        # 更新持倉與現金
        self.cash = current_value - used
        self.inventory = new_inventory
        self.last_rebalance_date = market_data.name
        
    def update_daily_snapshot(self, market_data: pd.Series):
        """記錄每日投資組合狀態"""
        snapshot = PortfolioSnapshot(
            timestamp=market_data.name,
            cash=self.cash,
            positions=self.inventory.copy(),
            total_value=self.get_portfolio_value(market_data)
        )
        self.portfolio_history.append(snapshot)
        
    def get_portfolio_value(self, market_data: pd.Series) -> float:
        """計算當前投資組合總價值"""
        total = self.cash
        for ticker, units in self.inventory.items():
            price_key = f'{ticker}_Close'
            if price_key in market_data.index:
                price = market_data[price_key]
                if pd.notna(price) and price > 0:
                    total += units * price
        return total
        
    def get_positions(self) -> Dict[str, int]:
        """取得當前持倉"""
        return self.inventory.copy()

    def get_annualized_return(self) -> float:
        """計算年化報酬率"""
        if not self.portfolio_history:
            return 0.0
        
        start_value = self.initial_balance
        end_value = self.portfolio_history[-1].total_value
        
        start_date = self.portfolio_history[0].timestamp
        end_date = self.portfolio_history[-1].timestamp
        
        years = (end_date - start_date).days / 365.25
        
        if years <= 0:
            return 0.0
            
        annualized_return = (end_value / start_value) ** (1 / years) - 1
        return annualized_return


# ============================================================================
# 數據提供者
# ============================================================================

class TradingViewWatchlist:
    """TradingView 投資組合清單"""
    
    def __init__(self, watchlist_id: str = "118349730", session_id: str = 'b379eetq1pojcel6olyymmpo1rd41nng'):
        self.watchlist_id = watchlist_id
        self.session_id = session_id
        self.result = {}
        self.providers = {}
        self.industries = {}
        self._fetch_watchlist()
        
    def _fetch_watchlist(self):
        """從 TradingView 取得投資組合清單"""
        url = f'https://in.tradingview.com/api/v1/symbols_list/custom/{self.watchlist_id}'
        headers = {
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'cookie': f'sessionid={self.session_id}',
            'x-requested-with': 'XMLHttpRequest',
        }
        
        symbols = requests.get(url, headers=headers).json()["symbols"]
        result = {}
        current_key = None
        
        for item in symbols:
            if "###" in item:
                current_key = item.strip("###\u2064")
                result[current_key] = {}
            elif current_key:
                provider, code = item.split(":", 1)
                if provider not in result[current_key]:
                    result[current_key][provider] = []
                    
                if provider in ['NASDAQ', 'NYSE']:
                    result[current_key][provider].append(code)
                elif provider in ['TWSE']:
                    result[current_key][provider].append(f"{code}.TW")
        
        self.result = result
        self.providers = {
            code: provider 
            for industry in result 
            for provider in result[industry] 
            for code in result[industry][provider]
        }
        self.industries = {
            code: industry 
            for industry in result 
            for provider in result[industry] 
            for code in result[industry][provider]
        }
        
    def todict(self):
        return self.result
        
    def tolist(self):
        return [
            code
            for industry in self.result
            for provider in self.result[industry]
            for code in self.result[industry][provider]
        ]
        
    def get_provider(self, code):
        return self.providers.get(code)
        
    def get_industry(self, code):
        return self.industries.get(code)


class MarketDataProvider:
    """市場數據提供者 - 負責數據下載與指標計算"""
    
    def __init__(self, watchlist_id: str = None, session_id: str = None):
        if watchlist_id and session_id:
            self.watchlist = TradingViewWatchlist(watchlist_id, session_id)
        else:
            self.watchlist = TradingViewWatchlist()
            
    def get_watchlist(self):
        return self.watchlist
        
    def get_history_with_unified_datetime(self, ticker: str, period: str = "15y", interval: str = "1d") -> pd.DataFrame:
        """下載股票歷史數據"""
        df = yf.Ticker(ticker).history(period=period, interval=interval)
        df = df.tz_localize(None)
        df = df.sort_index()
        return df
        
    def calculate_rainbow_bands(self, df: pd.DataFrame) -> pd.DataFrame:
        """計算彩虹圖波段"""
        df = df.copy()
        
        # 對數-對數回歸
        df['days'] = (df.index - df.index.min()).days
        df = df[df['days'] > 0]
        df['ln_days'] = np.log(df['days'])
        df['log10_price'] = np.log10(df['Close'])
        
        a, b = np.polyfit(df['ln_days'], df['log10_price'], deg=1)
        df['log10_trend'] = a * df['ln_days'] + b
        df['resid'] = df['log10_price'] - df['log10_trend']
        
        # 計算分位數波段
        quantiles = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]
        resid_levels = np.quantile(df['resid'], quantiles)
        
        for i, rl in enumerate(resid_levels):
            band_log10 = df['log10_trend'] + rl
            df[f'Band_{i+1}'] = 10 ** band_log10
            
        df['Trend'] = 10 ** df['log10_trend']
        return df
        
    def calculate_statistical_indicators(self, df: pd.DataFrame, reverse: bool = False) -> pd.DataFrame:
        """計算波動率、Beta、權重"""
        df = df.copy()
        prices = df['Close'].astype(float)
        band_keys = sorted([c for c in df.columns if c.startswith('Band_')],
                          key=lambda k: int(k.split('_')[1]))
        
        # 計算波動率
        rets = np.log(prices).diff()
        vol = rets.expanding().std(ddof=0) * np.sqrt(252)
        vol.iloc[0] = np.nan
        
        # 計算區段
        segments = []
        n_bands = len(band_keys)
        for i, p in enumerate(prices.to_numpy()):
            seg = None
            for j in range(n_bands - 1):
                lower = df[band_keys[j]].iat[i]
                upper = df[band_keys[j + 1]].iat[i]
                if lower <= p < upper:
                    seg = j + 1
                    break
            if seg is None:
                seg = 0 if p < df[band_keys[0]].iat[i] else n_bands
            segments.append(seg)
        
        df['segments'] = segments
        if reverse:
            df['segments'] = 9 - df['segments']
            
        df['volatilities'] = vol.values
        
        # 計算 Beta 與權重
        vol_clean = vol.replace(0, np.nan)
        cum_avg = vol_clean.expanding().mean()
        cum_max = vol_clean.expanding().max()
        
        base_weights = 1.0 / cum_avg
        betas = vol / cum_max
        betas = betas.where(cum_max > 0)
        
        df['base_weights'] = base_weights.ffill()
        df['betas'] = betas.ffill()
        
        return df
        
    def calculate_sharpe(self, df: pd.DataFrame, price_col: str = 'Close', 
                        sharpe_window: int = 365, risk_free_rate: float = 0.04) -> pd.DataFrame:
        """計算夏普比率"""
        df = df.copy()
        df["Returns"] = df[price_col].pct_change()
        daily_rf_rate = risk_free_rate / sharpe_window
        excess_returns = df["Returns"] - daily_rf_rate
        rolling_mean = excess_returns.rolling(sharpe_window).mean()
        rolling_std = excess_returns.rolling(sharpe_window).std()
        df["Sharpe"] = rolling_mean / rolling_std * np.sqrt(sharpe_window)
        return df
        
    def calculate_slope(self, series: pd.Series, slope_window: int = 365) -> pd.Series:
        """計算斜率"""
        slopes = [np.nan] * slope_window
        for i in range(slope_window, len(series)):
            x = np.arange(slope_window)
            y = series[i-slope_window:i]
            slope, _, _, _, _ = linregress(x, y)
            slopes.append(slope)
        return pd.Series(slopes, index=series.index)
        
    def get_stock_full_info(self, ticker: str, sharpe_window: int = 365) -> pd.DataFrame:
        """取得單一股票完整資訊"""
        df = self.get_history_with_unified_datetime(ticker)
        df = self.calculate_rainbow_bands(df)
        df = self.calculate_statistical_indicators(df)
        df = self.calculate_sharpe(df, price_col='Close', sharpe_window=sharpe_window)
        return df
        
    def download_stock_data(self, df: pd.DataFrame, watchlist: TradingViewWatchlist, 
                           sharpe_window: int = 365) -> pd.DataFrame:
        """下載所有股票數據"""
        watchlist_dict = watchlist.todict()
        
        for industry in watchlist_dict:
            for provider in watchlist_dict[industry]:
                for code in watchlist_dict[industry][provider]:
                    try:
                        temp_df = self.get_stock_full_info(code, sharpe_window=sharpe_window)
                        df[f'{code}_Close'] = temp_df['Close']
                        df[f'{code}_Sharpe'] = temp_df['Sharpe']
                        df[f'{code}_Base'] = temp_df['base_weights']
                        df[f'{code}_Volatility'] = temp_df['volatilities']
                        df[f'{code}_Beta'] = temp_df['betas']
                    except Exception as e:
                        print(f"⚠️ Failed to download {code}: {e}")
                        
        return df.ffill()
        
    def integrate_industry_metrics(self, df: pd.DataFrame, watchlist: TradingViewWatchlist, 
                                   ma_period: int, slope_window: int = 365) -> pd.DataFrame:
        """整合產業指標"""
        watchlist_dict = watchlist.todict()
        
        for industry in watchlist_dict:
            sharpe_matrix = pd.DataFrame()
            for provider in watchlist_dict[industry]:
                for code in watchlist_dict[industry][provider]:
                    if f'{code}_Sharpe' in df.columns:
                        sharpe_matrix[code] = df[f'{code}_Sharpe']
                        
            df[f'{industry}_Integrated_Sharpe'] = sharpe_matrix.mean(axis=1, skipna=True)
            df[f'{industry}_Sharpe_Slope'] = self.calculate_slope(df[f'{industry}_Integrated_Sharpe'], slope_window=slope_window)
            df[f'{industry}_MA_Short'] = df[f'{industry}_Sharpe_Slope'].rolling(window=ma_period).mean()
            df[f'{industry}_MA_Long'] = df[f'{industry}_Sharpe_Slope'].rolling(window=ma_period * 4).mean()
            
        return df
        
    def find_turning_points(self, df: pd.DataFrame, watchlist: TradingViewWatchlist) -> pd.DataFrame:
        """偵測高低轉折點"""
        watchlist_dict = watchlist.todict()
        
        for industry in watchlist_dict:
            dir_series = df[f"{industry}_MA_Short"] > df[f"{industry}_MA_Long"]
            slope = df[f"{industry}_Sharpe_Slope"]
            highs = [i for i in find_peaks(slope)[0] if dir_series.iloc[i]]
            lows = [i for i in find_peaks(-slope)[0] if not dir_series.iloc[i]]
            cross = np.where(dir_series.shift(1) != dir_series)[0]
            
            hcp, lcp, used_h, used_l = [], [], set(), set()
            for j in cross:
                if j < 1:
                    continue
                if dir_series.iloc[j - 1]:
                    prev = [h for h in highs if h < j and h not in used_h]
                    if prev:
                        h = prev[-1]
                        hcp.append(h)
                        used_h.add(h)
                else:
                    prev = [l for l in lows if l < j and l not in used_l]
                    if prev:
                        l = prev[-1]
                        lcp.append(l)
                        used_l.add(l)
            
            cp = pd.Series(index=df.index, dtype="float")
            cp.iloc[hcp] = 1
            cp.iloc[lcp] = 0
            df[f'{industry}_CP'] = cp.ffill()
            
        return df
        
    def generate_crossover_state(self, s: pd.Series, l: pd.Series) -> pd.Series:
        """產生交叉狀態"""
        state = pd.Series(index=s.index, dtype=int)
        cur = int(s.iloc[0] > l.iloc[0])
        state.iloc[0] = cur
        
        for i in range(1, len(s)):
            if cur and s.iloc[i - 1] > l.iloc[i - 1] and s.iloc[i] <= l.iloc[i]:
                cur = 0
            elif not cur and s.iloc[i - 1] < l.iloc[i - 1] and s.iloc[i] >= l.iloc[i]:
                cur = 1
            else:
                cur = int(s.iloc[i] > l.iloc[i])
            state.iloc[i] = cur
            
        return state
        
    def summary_overall_state(self, df: pd.DataFrame, watchlist: TradingViewWatchlist) -> pd.DataFrame:
        """彙總整體狀態"""
        watchlist_dict = watchlist.todict()
        df['Trend'] = 0
        
        for industry in watchlist_dict:
            df[f"{industry}_Crossover_State"] = self.generate_crossover_state(
                df[f"{industry}_MA_Short"], 
                df[f"{industry}_MA_Long"]
            )
            df['Trend'] += df[f"{industry}_Crossover_State"]
            
        df['Trend'] = df['Trend'] / len(watchlist_dict.keys())
        return df
        
    def build_decline_prediction(self, df: pd.DataFrame, watchlist: TradingViewWatchlist) -> pd.DataFrame:
        """建立下跌預測模型"""
        watchlist_dict = watchlist.todict()
        
        data = pd.concat([
            pd.DataFrame({
                'Industry': industry,
                'Trend': df['Trend'],
                'State': df[f'{industry}_Crossover_State'],
                'Decline': df[f'{industry}_CP']
            }) for industry in watchlist_dict
        ]).dropna()
        
        model = LogisticRegression().fit(data[['Trend', 'State']], data['Decline'])
        
        for industry in watchlist_dict:
            X = pd.DataFrame({
                'Trend': df['Trend'], 
                'State': df[f'{industry}_Crossover_State']
            })
            df[f'{industry}_Decline'] = model.predict_proba(X)[:, 1]
            
        return df
        
    def build_portfolio_data(self, watchlist: TradingViewWatchlist, 
                            sharpe_window: int = 365, 
                            slope_window: int = 365, 
                            ma_period: int = 30) -> pd.DataFrame:
        """建立完整投資組合數據"""
        # 以大盤指數為基準建立時間序列
        df = self.get_stock_full_info('^IXIC', sharpe_window=sharpe_window)
        
        # 下載個股數據
        df = self.download_stock_data(df, watchlist, sharpe_window=sharpe_window)
        
        # 整合產業指標
        df = self.integrate_industry_metrics(df, watchlist, ma_period=ma_period, slope_window=slope_window)
        
        # 偵測轉折點
        df = self.find_turning_points(df, watchlist)
        
        # 彙總整體狀態
        df = self.summary_overall_state(df, watchlist)
        
        # 建立下跌預測
        df = self.build_decline_prediction(df, watchlist)
        
        # 清理數據
        df = df.ffill().iloc[912:, :]
        
        return df


# ============================================================================
# 模擬市場
# ============================================================================

class SimulatedMarket:
    """模擬市場環境 - 執行回測與生成交易建議"""
    
    def __init__(self, data_provider: MarketDataProvider = None, 
                 watchlist_id: str = None, session_id: str = None):
        if data_provider:
            self.data_provider = data_provider
        elif watchlist_id and session_id:
            self.data_provider = MarketDataProvider(watchlist_id=watchlist_id, session_id=session_id)
        else:
            self.data_provider = MarketDataProvider()
        
        self.portfolio_df = None
        self._traders = {}
        
    def build_portfolio_data(self, sharpe_window: int = 365, slope_window: int = 365, ma_period: int = 30):
        """建立投資組合數據"""
        watchlist = self.data_provider.get_watchlist()
        self.portfolio_df = self.data_provider.build_portfolio_data(
            watchlist, 
            sharpe_window=sharpe_window, 
            slope_window=slope_window, 
            ma_period=ma_period
        )
        print(f"✅ Portfolio data built: {self.portfolio_df.shape}")
        
    def run(self, trader_or_traders):
        """執行回測"""
        if self.portfolio_df is None:
            print("⚠️ No portfolio data. Building data first...")
            self.build_portfolio_data()
        
        # 統一轉換成列表
        traders = [trader_or_traders] if isinstance(trader_or_traders, Trader) else trader_or_traders
        
        # 執行回測
        for trader in traders:
            label = f"{trader.strategy.__class__.__name__}_{trader.rebalance_frequency}"
            self._traders[label] = trader
            self._run_single_trader(trader)
            
    def _run_single_trader(self, trader):
        """執行單一 trader 的回測"""
        watchlist = self.data_provider.get_watchlist()
        codes = watchlist.tolist()
        
        for date in self.portfolio_df.index:
            market_data = self.portfolio_df.loc[date]
            
            # 判斷是否該 rebalance
            if trader._should_rebalance(date):
                weights = trader.decide(market_data, codes)
                trader.execute_trades(weights, market_data)
            
            # 記錄每日狀態
            trader.update_daily_snapshot(market_data)
    
    def _calculate_average_drawdown(self, history: list, min_drawdown_threshold: float = 0.15):
        """計算平均回撤"""
        significant_drawdowns = []
        peak = history[0]
        
        for value in history:
            if value > peak:
                peak = value
            current_dd = (value - peak) / peak
            dd_abs = abs(current_dd)
            if dd_abs >= min_drawdown_threshold:
                significant_drawdowns.append(dd_abs)
        
        if significant_drawdowns:
            avg = sum(significant_drawdowns) / len(significant_drawdowns)
            return avg, len(significant_drawdowns)
        return 0, 0
    
    def _get_best_rebalance_frequency(self, strategy):
        """計算最佳再平衡頻率"""
        if not self._traders:
            return None
        
        # 找出相同策略的所有 traders
        strategy_name = strategy.__class__.__name__
        matching_traders = {}
        
        for label, trader in self._traders.items():
            if trader.strategy.__class__.__name__ == strategy_name:
                # 計算績效指標
                history = [snap.total_value for snap in trader.portfolio_history]
                dates = [snap.timestamp for snap in trader.portfolio_history]
                
                if len(history) < 2:
                    continue
                
                initial = trader.initial_balance
                final = history[-1]
                days = (dates[-1] - dates[0]).days
                
                # 年化報酬
                annual_return = (final / initial) ** (365 / days) - 1 if days > 0 else 0
                
                # 平均回撤 (使用固定門檻 0.15)
                avg_dd, dd_count = self._calculate_average_drawdown(history, min_drawdown_threshold=0.15)
                
                # 計算分數
                score = annual_return - avg_dd
                
                matching_traders[trader.rebalance_frequency] = {
                    'frequency': trader.rebalance_frequency,
                    'annual_return': annual_return,
                    'avg_drawdown': avg_dd,
                    'drawdown_count': dd_count,
                    'score': score
                }
        
        if not matching_traders:
            return None
        
        # 找出分數最高的
        best = max(matching_traders.values(), key=lambda x: x['score'])
        
        # 中文化頻率
        freq_map = {
            'daily': '每日',
            'weekly': '每週',
            'monthly': '每月',
            'quarterly': '每季',
            'yearly': '每年'
        }
        best['frequency'] = freq_map.get(best['frequency'], best['frequency'])
        
        return best
        
    def get_trading_recommendation(self, strategy, date: pd.Timestamp = None) -> str:
        """生成每日交易建議"""
        if self.portfolio_df is None:
            return "⚠️ 請先執行 build_portfolio_data() 建立數據"
        
        # 取得日期
        if date is None:
            date = self.portfolio_df.index[-1]
        elif date not in self.portfolio_df.index:
            return f"⚠️ 日期 {date} 不在數據範圍內"
        
        market_data = self.portfolio_df.loc[date]
        watchlist = self.data_provider.get_watchlist()
        codes = watchlist.tolist()
        watchlist_dict = watchlist.todict()
        
        # 取得策略建議權重
        weights = strategy.calculate_weights(market_data, codes)
        
        # 建立股票到產業的映射
        code_to_industry = {}
        for industry, providers in watchlist_dict.items():
            for provider_codes in providers.values():
                for code in provider_codes:
                    code_to_industry[code] = industry
        
        # 建立輸出
        lines = []
        lines.append("━" * 43)
        lines.append(f"📅 {date.strftime('%Y-%m-%d')} 每日交易建議")
        lines.append("━" * 43)
        
        strategy_name = strategy.__class__.__name__
        if hasattr(strategy, 'topk'):
            strategy_name += f" (topk={strategy.topk})"
        lines.append(f"策略：{strategy_name}")

        # 計算最佳再平衡頻率
        best_freq = self._get_best_rebalance_frequency(strategy)
        
        if best_freq:
            lines.append(f"更新週期：{best_freq['frequency']}")
            lines.append(f"年化收益：{best_freq['annual_return']:.2%}")
            lines.append(f"平均回撤幅度：{best_freq['avg_drawdown']:.2%}")
        
        lines.append("\n💼 推薦持倉配置：")
        
        # 排序權重並顯示
        sorted_weights = sorted([(k, v) for k, v in weights.items() if k != 'CASH' and v > 0], 
                               key=lambda x: x[1], reverse=True)
        
        for code, weight in sorted_weights:
            industry = code_to_industry.get(code, "Unknown")
            lines.append(f"  {code:8s}  ({industry})")
        
        if 'CASH' in weights:
            lines.append(f"  現金      {weights['CASH']*100:5.1f}%")
        
        # 市場概況
        lines.append("\n📊 市場概況：")
        trend = market_data.get('Trend', 0)
        trend_desc = "偏多" if trend > 0.6 else "偏空" if trend < 0.4 else "中性"
        lines.append(f"  整體趨勢：{trend:.2f} ({trend_desc})")
        
        segment = int(market_data.get('segments', 5))
        segment_desc = {
            1: "嚴重超跌", 2: "深度超跌", 3: "超跌整理",
            4: "低檔盤整", 5: "中性區間", 6: "偏強整理",
            7: "接近高點", 8: "突破新高", 9: "極度高估"
        }.get(segment, "未知")
        lines.append(f"  大盤位置：{segment_desc}")
        
        volatility = market_data.get('volatilities', 0)
        vol_desc = "低" if volatility < 0.15 else "高" if volatility > 0.25 else "中等"
        lines.append(f"  市場波動：{volatility:.2f} ({vol_desc})")
        
        # 操作建議
        lines.append("\n💡 操作建議：")
        
        bullish = []
        bearish = []
        
        for industry in watchlist_dict.keys():
            crossover_state = market_data.get(f'{industry}_Crossover_State', 0)
            if crossover_state == 1:
                bullish.append(industry)
            else:
                bearish.append(industry)
        
        if bullish:
            lines.append(f" • 優先配置{', '.join(bullish)} 產業")
        if bearish:
            lines.append(f" • 減持調整{', '.join(bearish)} 產業")

        return "\n".join(lines)
