import numpy as np
import pandas as pd
import yfinance as yf
from scipy.signal import argrelextrema
from linebot import LineBotApi
from linebot.models import TextSendMessage

def unify_datetime_index(ticker, period="12y", interval="1d"):
  df = yf.Ticker(ticker).history(period=period, interval=interval)
  df = df.tz_localize(None)
  df = df.sort_index()
  return df

def compute_log_log_regression(df):
  df = df.copy()
  df['days'] = (df.index - df.index.min()).days
  df = df[df['days'] > 0]
  df['ln_days'] = np.log(df['days'])
  df['log10_price'] = np.log10(df['Close'])

  # log-log regression
  a, b = np.polyfit(df['ln_days'], df['log10_price'], deg=1)
  df['log10_trend'] = a * df['ln_days'] + b

  # residuals
  df['resid'] = df['log10_price'] - df['log10_trend']
  return df

def compute_quantile_bands(df, quantiles=[0.1,0.2,0.3,0.4,0.5,0.6,0.7,0.8,0.9]):
  resid_levels = np.quantile(df['resid'], quantiles)
  bands = {}
  for i, rl in enumerate(resid_levels):
    band_log10 = df['log10_trend'] + rl
    bands[f'Band_{i+1}'] = 10 ** band_log10
  return bands

def compute_rainbow_bands(ticker):
    """
    Compute rainbow bands using log-log regression + residual quantiles
    """
    df = unify_datetime_index(ticker)
    df = compute_log_log_regression(df)
    bands = compute_quantile_bands(df)

    bands_df = pd.DataFrame(bands, index=df.index)
    bands_df['Price'] = df['Close']
    bands_df['Trend'] = 10 ** df['log10_trend']  # 加入趨勢線
    last_day_bands = bands_df.iloc[-1][['Band_1', 'Band_9']]
    last_day_bands.index = ['MIN', 'MAX']

    print(ticker)#; display(last_day_bands)
    return bands_df

def plot_rebalance_index(bands_df, verbose=False):
  price_series = bands_df['Price'].iloc[-500:]

  # 找局部高低點
  local_max_idx = argrelextrema(price_series.values, np.greater, order=5)[0]
  local_min_idx = argrelextrema(price_series.values, np.less, order=5)[0]

  # 過濾「真正的」高低點
  global_max_idx, global_min_idx, high, low = [], [], -np.inf, np.inf
  for i, p in enumerate(price_series):
      if i in local_max_idx and p > high:
          global_max_idx.append(i); high, low = p, np.inf
      if i in local_min_idx and p < low:
          global_min_idx.append(i); low, high = p, -np.inf
  global_max_idx, global_min_idx = np.array(global_max_idx), np.array(global_min_idx)

  # 計算 rebalance
  rebalance = [
      np.min(price / price_series[global_max_idx[global_max_idx < i][-5:]] - 1)
      if np.any(global_max_idx < i) else 0 for i, price in enumerate(price_series)
  ]
  if verbose == True:
    fig = plt.figure(figsize=(20, 3))
    ax1, ax2 = fig.add_subplot(1, 2, 1), fig.add_subplot(1, 2, 2)

    ax1.plot(price_series.values, label='Price')
    ax1.scatter(global_max_idx, price_series.iloc[global_max_idx], color='orange', label='High')
    ax1.scatter(global_min_idx, price_series.iloc[global_min_idx], color='red', label='Low')
    ax1.set_title("Price with High/Low"); ax1.grid(True); ax1.legend()

    ax2.plot(rebalance, label='rebalance')
    ax2.axhline(0.1, color='gray', linestyle='--', label='threshold +10%')
    ax2.axhline(-0.1, color='gray', linestyle='--', label='threshold -10%')
    ax2.set_title("Rebalance"); ax2.grid(True); ax2.legend()

    plt.tight_layout()
    plt.show()
  return rebalance[-1]

def find_key_factor(bands_df, window=60):
  prices = list(bands_df['Price'])
  rets = np.diff(np.log(prices))
  if len(rets) < window:
    window = len(rets)
  volatility = float(np.std(rets[-window:]) * np.sqrt(252))
  band_keys = sorted([c for c in bands_df.columns if c.startswith('Band_')], key=lambda k: int(k.split('_')[1]))
  for i in range(len(band_keys) - 1):
      lower_band = bands_df[band_keys[i]].iloc[-1]
      upper_band = bands_df[band_keys[i+1]].iloc[-1]
      if lower_band <= prices[-1] < upper_band:
          return volatility, i + 1

  if prices[-1] < bands_df[band_keys[0]].iloc[-1]:
      return volatility, 0
  else:
      return volatility, len(band_keys)

def compute_statistic(volatilities):
    assets = list(volatilities.keys())
    inv_vol = {a: 1/volatilities[a] for a in assets}
    total_inv = sum(inv_vol.values())
    base_weights = {a: float(inv_vol[a]/total_inv) for a in assets}

    max_vol = max(volatilities.values())
    betas = {a: float(volatilities[a]/max_vol) for a in assets}
    return base_weights, betas

def rainbow_allocation(segments, volatilities):
    assets = list(segments.keys())
    base_weights, betas = compute_statistic(volatilities)
    v = {a: (segments[a] - 4.5) / 4.5 for a in assets}
    raw_weights = {a: base_weights[a] * (1 - betas[a] * v[a]) for a in assets}
    total = sum(raw_weights.values())
    norm_weights = {a: raw_weights[a]/total for a in assets}
    return norm_weights

def format_allocation_for_line(allocation_dict, rebalance_index, segments, volatilities, threshold=0.1):
    """格式化資產配置訊息"""
    lines = []
    lines.append("💰 資產保護策略配置")
    
    # 顯示配置比例
    lines.append("\n📊 建議配置比例：")
    sorted_allocation = sorted(allocation_dict.items(), key=lambda x: x[1], reverse=True)
    
    for asset, weight in sorted_allocation:
        percentage = weight * 100
        lines.append(f"  {asset:8s}  {percentage:5.1f}%")
    
    # 顯示市場狀態
    lines.append("\n📈 資產市場狀態：")
    asset_names = {"BTC": "加密貨幣", "Gold": "黃金", "Bond": "債券"}
    segment_desc = {
        0: "極度低估", 1: "嚴重超跌", 2: "深度超跌", 3: "超跌整理",
        4: "低檔盤整", 5: "中性區間", 6: "偏強整理",
        7: "接近高點", 8: "突破新高", 9: "極度高估", 10: "歷史高點"
    }
    
    for asset in allocation_dict.keys():
        if asset in segments and asset in volatilities:
            seg = segments[asset]
            vol = volatilities[asset]
            name = asset_names.get(asset, asset)
            seg_text = segment_desc.get(seg, "未知")
            vol_text = "低" if vol < 0.3 else "高" if vol > 0.6 else "中等"
            lines.append(f"  {name}：{seg_text} | 波動率 {vol_text}")
    
    # 檢查再平衡訊號
    lines.append("\n💡 操作建議：")
    
    # 收集所有資產的波動情況
    asset_list = list(allocation_dict.keys())
    asset_name_map = {"BTC": "加密貨幣", "Gold": "黃金", "Bond": "債券"}
    
    # 分類資產波動等級
    high_volatility = []  # >20%
    medium_volatility = []  # 15-20%
    low_volatility = []  # 10-15%
    
    for i in range(len(rebalance_index)):
        rebalance = abs(rebalance_index[i])
        asset = asset_list[i]
        asset_name = asset_name_map.get(asset, asset)
        
        if rebalance > 0.20:
            high_volatility.append((asset_name, rebalance))
        elif rebalance > 0.15:
            medium_volatility.append((asset_name, rebalance))
        elif rebalance > threshold:
            low_volatility.append((asset_name, rebalance))
    
    # 根據波動情況生成建議
    if high_volatility:
        lines.append(f"  🚨 資產出現大幅波動：")
        for asset_name, rebalance in high_volatility:
            lines.append(f"    • {asset_name}：{rebalance*100:.1f}%")
        if medium_volatility or low_volatility:
            lines.append(f"  其他波動：")
            for asset_name, rebalance in medium_volatility + low_volatility:
                lines.append(f"    • {asset_name}：{rebalance*100:.1f}%")
        lines.append(f"  強烈建議調整配置以控制風險")
    elif medium_volatility:
        lines.append(f"  ⚠️ 資產出現明顯波動：")
        for asset_name, rebalance in medium_volatility:
            lines.append(f"    • {asset_name}：{rebalance*100:.1f}%")
        if low_volatility:
            lines.append(f"  其他波動：")
            for asset_name, rebalance in low_volatility:
                lines.append(f"    • {asset_name}：{rebalance*100:.1f}%")
        lines.append(f"  建議考慮調整配置")
    elif low_volatility:
        lines.append(f"  ⚡ 資產出現輕微波動：")
        for asset_name, rebalance in low_volatility:
            lines.append(f"    • {asset_name}：{rebalance*100:.1f}%")
        lines.append(f"  可持續觀察，暫無需調整")
    else:
        lines.append(f"  ✅ 各資產價格穩定，維持當前配置")
    
    return "\n".join(lines)

def LineBotMessage(text='Test'):
  line_bot_api = LineBotApi('aKRtdIDqU8HQ9N/bHaXNOMtbEZAoIctjuyzsOcY+AHTf9cqQh18aMOJoPbx55VOl/qvS3LAB6I3tO/fbRCuL6TsrT08X9kb0IkncE0C/1pdIqQ/Oqi1zuWwUNaNNrFrPbIvxHHt1+ROP5d3EpfasqwdB04t89/1O/w1cDnyilFU=')
  line_bot_api.push_message('C09ca18b7360b50eb65697210a41805ad', TextSendMessage(text=text))