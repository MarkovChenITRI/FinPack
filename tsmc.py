"""
TSMC 台股 vs ADR 溢價分析工具

比較 2330.TW (台積電台股) 與 TSM (台積電 ADR) 近 6 年的相對關係
分析 ADR 相對於台股的溢價/折價狀況
"""
import pickle
import pandas as pd
import yfinance as yf
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime, timedelta
from pathlib import Path

# ===== 設定 =====
BASE_DIR = Path(__file__).parent
CACHE_DIR = BASE_DIR / "cache"
TSMC_CACHE_FILE = CACHE_DIR / "tsmc_analysis.pkl"

# 台積電代碼
TSMC_TW = "2330.TW"  # 台股
TSMC_US = "TSM"      # ADR
ADR_RATIO = 5        # 1 ADR = 5 股台積電

DATA_PERIOD = "6y"
CACHE_MAX_AGE_DAYS = 1


def get_usd_twd_rate() -> pd.DataFrame:
    """
    獲取美元兌台幣匯率歷史數據
    
    Returns:
        DataFrame with exchange rate history
    """
    try:
        print("📥 抓取 USD/TWD 匯率歷史...")
        ticker = yf.Ticker("TWD=X")
        df = ticker.history(period=DATA_PERIOD, interval="1d")
        if not df.empty:
            df = df.tz_localize(None)
            df = df.sort_index()
            print(f"✅ 匯率資料: {len(df)} 筆")
            return df[['Close']].rename(columns={'Close': 'Rate'})
    except Exception as e:
        print(f"⚠️ 匯率抓取失敗: {e}")
    return pd.DataFrame()


def fetch_stock_data(ticker: str, period: str = DATA_PERIOD) -> pd.DataFrame:
    """
    下載單一股票歷史數據
    
    Args:
        ticker: 股票代碼
        period: 資料期間
        
    Returns:
        DataFrame with OHLCV data
    """
    try:
        print(f"📥 從 yfinance 抓取 {ticker}...")
        df = yf.Ticker(ticker).history(period=period, interval="1d")
        if df.empty:
            print(f"❌ {ticker}: 無資料")
            return pd.DataFrame()
        
        df = df.tz_localize(None)
        df = df.sort_index()
        print(f"✅ {ticker}: {len(df)} 筆")
        return df[['Open', 'High', 'Low', 'Close', 'Volume']]
    except Exception as e:
        print(f"⚠️ {ticker}: {e}")
        return pd.DataFrame()


def load_cache() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, datetime | None]:
    """
    從快取載入資料
    
    Returns:
        (tsmc_tw, tsmc_us, usd_twd, last_update)
    """
    if not TSMC_CACHE_FILE.exists():
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), None
    
    try:
        with open(TSMC_CACHE_FILE, 'rb') as f:
            cache = pickle.load(f)
        
        cache_time = cache.get('last_update')
        if cache_time:
            cache_age = datetime.now() - cache_time
            if cache_age > timedelta(days=CACHE_MAX_AGE_DAYS):
                print("⚠️ 快取已過期，將重新抓取")
                return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), None
        
        print(f"📂 載入快取 (更新於 {cache_time.strftime('%Y-%m-%d %H:%M')})")
        return (
            cache.get('tsmc_tw', pd.DataFrame()),
            cache.get('tsmc_us', pd.DataFrame()),
            cache.get('usd_twd', pd.DataFrame()),
            cache_time
        )
    except Exception as e:
        print(f"⚠️ 載入快取失敗: {e}")
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), None


def save_cache(tsmc_tw: pd.DataFrame, tsmc_us: pd.DataFrame, usd_twd: pd.DataFrame):
    """儲存資料到快取"""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    
    try:
        cache = {
            'tsmc_tw': tsmc_tw,
            'tsmc_us': tsmc_us,
            'usd_twd': usd_twd,
            'last_update': datetime.now()
        }
        with open(TSMC_CACHE_FILE, 'wb') as f:
            pickle.dump(cache, f)
        print(f"💾 已儲存快取至 {TSMC_CACHE_FILE}")
    except Exception as e:
        print(f"⚠️ 儲存快取失敗: {e}")


def load_or_fetch_data() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    載入或抓取資料（優先使用快取）
    
    Returns:
        (tsmc_tw, tsmc_us, usd_twd)
    """
    # 嘗試從快取載入
    tsmc_tw, tsmc_us, usd_twd, last_update = load_cache()
    
    if not tsmc_tw.empty and not tsmc_us.empty and not usd_twd.empty:
        return tsmc_tw, tsmc_us, usd_twd
    
    # 從 yfinance 抓取
    print("\n" + "=" * 50)
    print("📊 開始抓取 TSMC 資料")
    print("=" * 50)
    
    tsmc_tw = fetch_stock_data(TSMC_TW)
    tsmc_us = fetch_stock_data(TSMC_US)
    usd_twd = get_usd_twd_rate()
    
    # 儲存快取
    if not tsmc_tw.empty and not tsmc_us.empty:
        save_cache(tsmc_tw, tsmc_us, usd_twd)
    
    return tsmc_tw, tsmc_us, usd_twd


def align_data(tsmc_tw: pd.DataFrame, tsmc_us: pd.DataFrame, usd_twd: pd.DataFrame) -> pd.DataFrame:
    """
    對齊台股與 ADR 的日期
    
    由於台股與美股交易日不同，只取兩者都有交易的日期
    
    Args:
        tsmc_tw: 台積電台股資料
        tsmc_us: 台積電 ADR 資料
        usd_twd: 匯率資料
        
    Returns:
        對齊後的合併 DataFrame
    """
    # 找出共同交易日
    common_dates = tsmc_tw.index.intersection(tsmc_us.index)
    
    if usd_twd is not None and not usd_twd.empty:
        common_dates = common_dates.intersection(usd_twd.index)
    
    print(f"\n📅 日期對齊:")
    print(f"  台股資料: {len(tsmc_tw)} 筆")
    print(f"  ADR 資料: {len(tsmc_us)} 筆")
    print(f"  共同交易日: {len(common_dates)} 筆")
    
    # 建立合併 DataFrame
    aligned = pd.DataFrame(index=common_dates)
    aligned['TW_Close'] = tsmc_tw.loc[common_dates, 'Close']
    aligned['US_Close'] = tsmc_us.loc[common_dates, 'Close']
    aligned['US_Volume'] = tsmc_us.loc[common_dates, 'Volume']
    aligned['TW_Volume'] = tsmc_tw.loc[common_dates, 'Volume']
    
    # 匯率處理
    if usd_twd is not None and not usd_twd.empty:
        aligned['USD_TWD'] = usd_twd.loc[common_dates, 'Rate']
    else:
        # 使用固定匯率
        aligned['USD_TWD'] = 32.0
        print("  ⚠️ 使用固定匯率 32.0")
    
    # 填補缺失匯率
    aligned['USD_TWD'] = aligned['USD_TWD'].ffill().bfill()
    
    return aligned.dropna()


def calculate_premium(aligned: pd.DataFrame) -> pd.DataFrame:
    """
    計算 ADR 溢價率
    
    公式: 溢價率 = (ADR換算台幣價 - 台股價) / 台股價 * 100
    
    ADR換算台幣價 = ADR價格 * 匯率 / ADR比例 (1 ADR = 5 股)
    
    Args:
        aligned: 對齊後的資料
        
    Returns:
        加入溢價率計算的 DataFrame
    """
    df = aligned.copy()
    
    # ADR 換算成台股等價價格 (1 ADR = 5 股台積電)
    df['ADR_TWD'] = df['US_Close'] * df['USD_TWD'] / ADR_RATIO
    
    # 溢價率 (%)
    df['Premium'] = (df['ADR_TWD'] - df['TW_Close']) / df['TW_Close'] * 100
    
    # 正規化價格 (以第一天為基準 = 100)
    df['TW_Normalized'] = df['TW_Close'] / df['TW_Close'].iloc[0] * 100
    df['ADR_Normalized'] = df['ADR_TWD'] / df['ADR_TWD'].iloc[0] * 100
    
    return df


def plot_analysis(df: pd.DataFrame, save_path: str = None):
    """
    繪製 TSMC 台股 vs ADR 分析圖表
    
    包含:
    1. 價格走勢對比 (正規化)
    2. ADR 溢價率
    3. 實際價格對比 (TWD)
    
    Args:
        df: 計算完成的 DataFrame
        save_path: 存檔路徑 (可選)
    """
    # 設定中文字體
    plt.rcParams['font.sans-serif'] = ['Microsoft JhengHei', 'SimHei', 'Arial']
    plt.rcParams['axes.unicode_minus'] = False
    
    # 建立圖表
    fig, axes = plt.subplots(3, 1, figsize=(14, 12), sharex=True)
    fig.suptitle('TSMC 台股 vs ADR 溢價分析 (近 6 年)', fontsize=16, fontweight='bold')
    
    # ===== 圖 1: 正規化價格走勢 =====
    ax1 = axes[0]
    ax1.plot(df.index, df['TW_Normalized'], label='2330.TW (台股)', 
             color='#E74C3C', linewidth=1.5)
    ax1.plot(df.index, df['ADR_Normalized'], label='TSM (ADR 換算TWD)', 
             color='#3498DB', linewidth=1.5, alpha=0.8)
    
    ax1.set_ylabel('正規化價格 (起始=100)', fontsize=11)
    ax1.set_title('價格走勢對比 (正規化)', fontsize=12)
    ax1.legend(loc='upper left')
    ax1.grid(True, alpha=0.3)
    ax1.axhline(y=100, color='gray', linestyle='--', alpha=0.5)
    
    # 標註最終報酬
    tw_return = (df['TW_Normalized'].iloc[-1] - 100)
    adr_return = (df['ADR_Normalized'].iloc[-1] - 100)
    ax1.annotate(f'台股: {tw_return:+.1f}%', 
                 xy=(df.index[-1], df['TW_Normalized'].iloc[-1]),
                 xytext=(10, 0), textcoords='offset points',
                 fontsize=10, color='#E74C3C')
    ax1.annotate(f'ADR: {adr_return:+.1f}%', 
                 xy=(df.index[-1], df['ADR_Normalized'].iloc[-1]),
                 xytext=(10, 0), textcoords='offset points',
                 fontsize=10, color='#3498DB')
    
    # ===== 圖 2: ADR 溢價率 =====
    ax2 = axes[1]
    
    # 填充正負區域
    ax2.fill_between(df.index, df['Premium'], 0, 
                     where=(df['Premium'] >= 0),
                     color='#E74C3C', alpha=0.3, label='ADR 溢價')
    ax2.fill_between(df.index, df['Premium'], 0, 
                     where=(df['Premium'] < 0),
                     color='#27AE60', alpha=0.3, label='ADR 折價')
    
    ax2.plot(df.index, df['Premium'], color='#2C3E50', linewidth=1)
    
    # 移動平均線
    ma_20 = df['Premium'].rolling(20).mean()
    ax2.plot(df.index, ma_20, color='#9B59B6', linewidth=2, 
             linestyle='--', label='20日均線', alpha=0.8)
    
    ax2.axhline(y=0, color='black', linewidth=1)
    ax2.set_ylabel('溢價率 (%)', fontsize=11)
    ax2.set_title('ADR 相對台股溢價率', fontsize=12)
    ax2.legend(loc='upper right')
    ax2.grid(True, alpha=0.3)
    
    # 標註統計資訊
    premium_mean = df['Premium'].mean()
    premium_std = df['Premium'].std()
    premium_max = df['Premium'].max()
    premium_min = df['Premium'].min()
    current_premium = df['Premium'].iloc[-1]
    
    stats_text = f'平均: {premium_mean:.2f}%  |  標準差: {premium_std:.2f}%  |  當前: {current_premium:.2f}%'
    ax2.text(0.02, 0.95, stats_text, transform=ax2.transAxes, fontsize=10,
             verticalalignment='top', bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
    
    # ===== 圖 3: 實際價格 (TWD) =====
    ax3 = axes[2]
    ax3.plot(df.index, df['TW_Close'], label='2330.TW (台股價格)', 
             color='#E74C3C', linewidth=1.5)
    ax3.plot(df.index, df['ADR_TWD'], label='TSM (ADR 換算 TWD)', 
             color='#3498DB', linewidth=1.5, alpha=0.8)
    
    ax3.set_xlabel('日期', fontsize=11)
    ax3.set_ylabel('價格 (TWD)', fontsize=11)
    ax3.set_title('實際價格對比 (ADR 換算為台幣)', fontsize=12)
    ax3.legend(loc='upper left')
    ax3.grid(True, alpha=0.3)
    
    # 標註當前價格
    ax3.annotate(f'NT${df["TW_Close"].iloc[-1]:.0f}', 
                 xy=(df.index[-1], df['TW_Close'].iloc[-1]),
                 xytext=(10, 5), textcoords='offset points',
                 fontsize=10, color='#E74C3C')
    ax3.annotate(f'NT${df["ADR_TWD"].iloc[-1]:.0f}', 
                 xy=(df.index[-1], df['ADR_TWD'].iloc[-1]),
                 xytext=(10, -15), textcoords='offset points',
                 fontsize=10, color='#3498DB')
    
    # 設定 X 軸日期格式
    ax3.xaxis.set_major_locator(mdates.YearLocator())
    ax3.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
    ax3.xaxis.set_minor_locator(mdates.MonthLocator(bymonth=[1, 7]))
    
    plt.tight_layout()
    
    # 儲存或顯示
    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        print(f"\n📊 圖表已儲存至: {save_path}")
    
    plt.show()


def print_summary(df: pd.DataFrame):
    """
    輸出分析摘要
    """
    print("\n" + "=" * 60)
    print("📊 TSMC 台股 vs ADR 分析摘要")
    print("=" * 60)
    
    # 基本資訊
    print(f"\n📅 分析期間: {df.index[0].strftime('%Y-%m-%d')} ~ {df.index[-1].strftime('%Y-%m-%d')}")
    print(f"   共 {len(df)} 個交易日")
    
    # 當前狀況
    print(f"\n💰 當前價格:")
    print(f"   台股 (2330.TW): NT${df['TW_Close'].iloc[-1]:.2f}")
    print(f"   ADR (TSM):      US${df['US_Close'].iloc[-1]:.2f}")
    print(f"   匯率 (USD/TWD): {df['USD_TWD'].iloc[-1]:.2f}")
    print(f"   ADR 換算 TWD:   NT${df['ADR_TWD'].iloc[-1]:.2f}")
    print(f"   當前溢價率:     {df['Premium'].iloc[-1]:.2f}%")
    
    # 溢價統計
    premium = df['Premium']
    print(f"\n📈 溢價率統計:")
    print(f"   平均值:   {premium.mean():.2f}%")
    print(f"   標準差:   {premium.std():.2f}%")
    print(f"   最高值:   {premium.max():.2f}% ({premium.idxmax().strftime('%Y-%m-%d')})")
    print(f"   最低值:   {premium.min():.2f}% ({premium.idxmin().strftime('%Y-%m-%d')})")
    print(f"   中位數:   {premium.median():.2f}%")
    
    # 報酬率比較
    tw_return = (df['TW_Close'].iloc[-1] / df['TW_Close'].iloc[0] - 1) * 100
    adr_return = (df['ADR_TWD'].iloc[-1] / df['ADR_TWD'].iloc[0] - 1) * 100
    
    print(f"\n📊 期間報酬率:")
    print(f"   台股報酬率:     {tw_return:.2f}%")
    print(f"   ADR 報酬率:     {adr_return:.2f}% (換算 TWD)")
    print(f"   報酬差異:       {adr_return - tw_return:.2f}%")
    
    # 溢價/折價天數
    premium_days = (premium > 0).sum()
    discount_days = (premium < 0).sum()
    print(f"\n📉 溢價/折價分布:")
    print(f"   溢價天數: {premium_days} ({premium_days/len(premium)*100:.1f}%)")
    print(f"   折價天數: {discount_days} ({discount_days/len(premium)*100:.1f}%)")
    
    # 當前溢價位置
    percentile = (premium < df['Premium'].iloc[-1]).sum() / len(premium) * 100
    print(f"\n📍 當前溢價率位於歷史 {percentile:.1f}% 分位數")
    
    print("\n" + "=" * 60)


def main():
    """主程式"""
    print("=" * 60)
    print("🔍 TSMC 台股 vs ADR 溢價分析工具")
    print("   比較 2330.TW 與 TSM 的價格關係")
    print("=" * 60)
    
    # 1. 載入或抓取資料
    tsmc_tw, tsmc_us, usd_twd = load_or_fetch_data()
    
    if tsmc_tw.empty or tsmc_us.empty:
        print("❌ 無法取得資料，請檢查網路連線")
        return
    
    # 2. 對齊資料
    aligned = align_data(tsmc_tw, tsmc_us, usd_twd)
    
    if aligned.empty:
        print("❌ 資料對齊失敗")
        return
    
    # 3. 計算溢價
    df = calculate_premium(aligned)
    
    # 4. 輸出摘要
    print_summary(df)
    
    # 5. 繪製圖表
    output_path = BASE_DIR / "tsmc_premium_analysis.png"
    plot_analysis(df, save_path=str(output_path))
    
    return df


if __name__ == "__main__":
    result_df = main()
