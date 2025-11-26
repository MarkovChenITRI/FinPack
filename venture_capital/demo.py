import functions_framework
from utils import *

@functions_framework.http
def venture_capital_http(request):
    gold_bands_df = compute_rainbow_bands('GC=F')
    crypto_bands_df = compute_rainbow_bands('BTC-USD')
    stock_bands_df = compute_rainbow_bands('^IXIC')

    # 注意：資產順序必須一致 [Gold, BTC, Bond]
    rebalance_index = [plot_rebalance_index(bands_df) for bands_df in [gold_bands_df, crypto_bands_df, stock_bands_df]]

    segments, volatilities, assets = {}, {}, ["Gold", "BTC", "Bond"]
    for i, df in enumerate([gold_bands_df, crypto_bands_df, stock_bands_df]):
        volatilities[assets[i]], segments[assets[i]] = find_key_factor(df)
        if assets[i] == "Bond":
           segments[assets[i]] = 9 - segments[assets[i]]

    w = rainbow_allocation(segments, volatilities)
    message = format_allocation_for_line(w, rebalance_index, segments, volatilities)
    print(message)
    
    LineBotMessage(message)
    return ""