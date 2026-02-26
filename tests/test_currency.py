"""
測試貨幣模組
"""
from core.currency import (
    Money, Currency, CurrencyMismatchError,
    twd, usd, money,
    ExchangeRateService, get_fx_service, init_fx_service,
    convert_to_twd, convert_to_usd,
    calculate_shares, calculate_cost
)


def test_money_creation():
    """測試 Money 建立"""
    print("=" * 60)
    print("測試 Money 建立")
    print("=" * 60)
    
    # 使用工廠函數
    m1 = twd(1_000_000)
    m2 = usd(150.50)
    m3 = money(500, 'TWD')
    m4 = money(100, Currency.USD)
    
    print(f"twd(1_000_000) = {m1}")
    print(f"usd(150.50) = {m2}")
    print(f"money(500, 'TWD') = {m3}")
    print(f"money(100, Currency.USD) = {m4}")
    
    assert m1.is_twd()
    assert m2.is_usd()
    print("✅ Money 建立測試通過")


def test_same_currency_operations():
    """測試同幣別運算"""
    print("\n" + "=" * 60)
    print("測試同幣別運算")
    print("=" * 60)
    
    a = twd(100_000)
    b = twd(50_000)
    
    # 加法
    result = a + b
    print(f"{a} + {b} = {result}")
    assert result.amount == 150_000
    
    # 減法
    result = a - b
    print(f"{a} - {b} = {result}")
    assert result.amount == 50_000
    
    # 乘法（與數字）
    result = a * 3
    print(f"{a} * 3 = {result}")
    assert result.amount == 300_000
    
    # 除法（與數字）
    result = a / 2
    print(f"{a} / 2 = {result}")
    assert result.amount == 50_000
    
    # 除法（Money / Money = 比率）
    ratio = a / b
    print(f"{a} / {b} = {ratio}")
    assert ratio == 2.0
    
    # sum()
    total = sum([twd(100), twd(200), twd(300)])
    print(f"sum([100, 200, 300] TWD) = {total}")
    assert total.amount == 600
    
    print("✅ 同幣別運算測試通過")


def test_different_currency_error():
    """測試不同幣別運算報錯"""
    print("\n" + "=" * 60)
    print("測試不同幣別運算報錯")
    print("=" * 60)
    
    twd_amount = twd(100_000)
    usd_amount = usd(3_000)
    
    # 測試加法報錯
    try:
        result = twd_amount + usd_amount
        print("❌ 應該報錯但沒有")
        assert False
    except CurrencyMismatchError as e:
        print(f"✅ 加法報錯: {e}")
    
    # 測試減法報錯
    try:
        result = twd_amount - usd_amount
        assert False
    except CurrencyMismatchError as e:
        print(f"✅ 減法報錯: {e}")
    
    # 測試比較報錯
    try:
        result = twd_amount > usd_amount
        assert False
    except CurrencyMismatchError as e:
        print(f"✅ 比較報錯: {e}")
    
    print("✅ 不同幣別報錯測試通過")


def test_exchange_rate_service():
    """測試匯率服務"""
    print("\n" + "=" * 60)
    print("測試匯率服務")
    print("=" * 60)
    
    # 建立服務並載入歷史匯率
    fx = ExchangeRateService(default_rate=32.0)
    
    history = {
        '2024-01-01': 31.00,
        '2024-01-02': 31.25,
        '2024-01-03': 31.50,
        '2024-01-04': 31.75,
        '2024-01-05': 32.00,
    }
    fx.load_history(history)
    
    print(f"匯率服務: {fx}")
    
    # 測試取得匯率
    rate_0103 = fx.get_rate('2024-01-03')
    print(f"2024-01-03 匯率: {rate_0103}")
    assert rate_0103 == 31.50
    
    # 測試找不到日期時往前找
    rate_0110 = fx.get_rate('2024-01-10')
    print(f"2024-01-10 匯率（往前找最近）: {rate_0110}")
    assert rate_0110 == 32.00  # 用 01-05 的
    
    # 測試換匯
    usd_price = usd(100)
    twd_price = fx.convert(usd_price, Currency.TWD, '2024-01-03')
    print(f"換匯: {usd_price} -> {twd_price} (2024-01-03)")
    assert twd_price.amount == 3150.0
    
    # 反向換匯
    twd_amount = twd(31500)
    usd_converted = fx.convert(twd_amount, Currency.USD, '2024-01-03')
    print(f"反向換匯: {twd_amount} -> {usd_converted}")
    assert abs(usd_converted.amount - 1000) < 0.01
    
    print("✅ 匯率服務測試通過")


def test_global_fx_service():
    """測試全域匯率服務"""
    print("\n" + "=" * 60)
    print("測試全域匯率服務")
    print("=" * 60)
    
    # 初始化全域服務
    history = {
        '2024-06-01': 32.50,
        '2024-06-02': 32.60,
    }
    init_fx_service(history, default_rate=32.0)
    
    # 使用便捷函數
    twd_amount = convert_to_twd(100, 'USD', '2024-06-01')
    print(f"100 USD -> {twd_amount:.2f} TWD (2024-06-01)")
    assert twd_amount == 3250.0
    
    usd_amount = convert_to_usd(3260, 'TWD', '2024-06-02')
    print(f"3260 TWD -> {usd_amount:.2f} USD (2024-06-02)")
    assert usd_amount == 100.0
    
    # 同幣別不變
    same = convert_to_twd(1000, 'TWD')
    assert same == 1000
    
    print("✅ 全域匯率服務測試通過")


def test_calculate_shares():
    """測試股數計算"""
    print("\n" + "=" * 60)
    print("測試股數計算")
    print("=" * 60)
    
    # 初始化匯率服務
    init_fx_service({'2024-01-01': 32.0}, default_rate=32.0)
    
    # 用 TWD 預算買美股
    budget = twd(100_000)
    us_price = 150.0  # USD
    shares = calculate_shares(budget, us_price, 'US')
    print(f"預算 {budget}, 美股價 ${us_price} USD -> 可買 {shares} 股")
    # 100000 / 32 = 3125 USD, 3125 / 150 = 20.83 -> 20 股
    assert shares == 20
    
    # 用 TWD 預算買台股
    tw_price = 500.0  # TWD
    shares = calculate_shares(budget, tw_price, 'TW')
    print(f"預算 {budget}, 台股價 ${tw_price} TWD -> 可買 {shares} 股")
    assert shares == 200
    
    # 用 USD 預算買美股
    budget_usd = usd(3000)
    shares = calculate_shares(budget_usd, us_price, 'US')
    print(f"預算 {budget_usd}, 美股價 ${us_price} USD -> 可買 {shares} 股")
    assert shares == 20
    
    print("✅ 股數計算測試通過")


def test_calculate_cost():
    """測試成本計算"""
    print("\n" + "=" * 60)
    print("測試成本計算")
    print("=" * 60)
    
    init_fx_service({'2024-01-01': 32.0}, default_rate=32.0)
    
    # 美股成本（轉為 TWD）
    cost = calculate_cost(10, 150.0, 'US', Currency.TWD)
    print(f"10 股 * $150 USD = {cost}")
    assert cost.amount == 48000.0  # 10 * 150 * 32
    
    # 台股成本
    cost = calculate_cost(100, 500.0, 'TW', Currency.TWD)
    print(f"100 股 * $500 TWD = {cost}")
    assert cost.amount == 50000.0
    
    print("✅ 成本計算測試通過")


def test_comparison():
    """測試比較運算"""
    print("\n" + "=" * 60)
    print("測試比較運算")
    print("=" * 60)
    
    a = twd(100)
    b = twd(200)
    c = twd(100)
    
    assert a < b
    assert b > a
    assert a <= c
    assert a >= c
    assert a == c
    assert a != b
    
    print(f"{a} < {b}: {a < b}")
    print(f"{a} == {c}: {a == c}")
    print("✅ 比較運算測試通過")


def test_practical_scenario():
    """實際場景測試：買入美股"""
    print("\n" + "=" * 60)
    print("實際場景測試：買入美股")
    print("=" * 60)
    
    # 初始化
    history = {
        '2024-01-15': 31.50,
        '2024-01-16': 31.60,
    }
    fx = init_fx_service(history)
    
    # 初始資金（TWD）
    capital = twd(1_000_000)
    print(f"初始資金: {capital}")
    
    # 每檔投入金額（TWD）
    amount_per_stock = twd(100_000)
    print(f"每檔投入: {amount_per_stock}")
    
    # 買入 AAPL @ $180 USD
    stock_price_usd = 180.0
    date = '2024-01-15'
    rate = fx.get_rate(date)
    
    # 計算可買股數
    budget_usd = fx.to_usd(amount_per_stock, date)
    shares = int(budget_usd.amount / stock_price_usd)
    print(f"\n{date} 匯率: {rate}")
    print(f"預算: {amount_per_stock} = {budget_usd}")
    print(f"AAPL 股價: ${stock_price_usd} USD")
    print(f"可買股數: {shares} 股")
    
    # 計算實際成本（TWD）
    actual_cost_usd = usd(shares * stock_price_usd)
    actual_cost_twd = fx.to_twd(actual_cost_usd, date)
    print(f"實際成本: {actual_cost_usd} = {actual_cost_twd}")
    
    # 更新資金
    capital = capital - actual_cost_twd
    print(f"剩餘資金: {capital}")
    
    # 驗證
    assert shares == 17  # 3174.60 USD / 180 = 17.64 -> 17 股
    assert abs(actual_cost_twd.amount - (17 * 180 * 31.50)) < 0.01
    
    print("\n✅ 實際場景測試通過")


if __name__ == '__main__':
    test_money_creation()
    test_same_currency_operations()
    test_different_currency_error()
    test_exchange_rate_service()
    test_global_fx_service()
    test_calculate_shares()
    test_calculate_cost()
    test_comparison()
    test_practical_scenario()
    
    print("\n" + "=" * 60)
    print("🎉 所有測試通過！")
    print("=" * 60)
