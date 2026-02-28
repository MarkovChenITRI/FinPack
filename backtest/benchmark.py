"""
回測基準 (Benchmark) 計算模組

提供 calculate_benchmark_curve() 函數，
供 CLI (run.py) 和 API (web/routes/backtest.py) 共用，
確保兩者輸出完全一致。
"""
import logging

logger = logging.getLogger(__name__)


def calculate_benchmark_curve(container, market: str, trading_dates: list,
                               initial_capital: float) -> tuple:
    """
    計算 benchmark 權益曲線（考慮匯率）

    使用策略的交易日期來取 benchmark 價格，確保 x 軸對齊。
    初始資金為 TWD，所以 US 市場需要考慮匯率變動。

    計算邏輯（以 TWD 計價）：
    - us: 初始資金換成 USD 買 NASDAQ，每天用當天匯率換回 TWD
    - tw: 初始資金直接買 TWII，無匯率問題
    - global: 50% 買 NASDAQ（含匯率）+ 50% 買 TWII

    Args:
        container: DataContainer 資料容器
        market: 'us' | 'tw' | 'global'
        trading_dates: 策略的交易日期列表（用於對齊，格式 'YYYY-MM-DD'）
        initial_capital: 初始資金（TWD）

    Returns:
        (benchmark_curve, benchmark_name): 權益曲線 list 與指數名稱
    """
    from core.currency import FX

    if not trading_dates:
        return [], ''

    fx = container.fx or FX(use_cache=True)

    if market == 'global':
        # 國際加權指數 = 50% NASDAQ + 50% TWII
        name = '國際加權指數'
        nasdaq_data = container.market_loader.get_weighted_kline('^IXIC', '6y', container.aligned_data)
        twii_data = container.market_loader.get_weighted_kline('^TWII', '6y', container.aligned_data)

        if not nasdaq_data or not twii_data:
            logger.warning('[BENCHMARK] 找不到 %s 指數資料', name)
            return [], name

        nasdaq_map = {d['time']: d['close'] for d in nasdaq_data}
        twii_map = {d['time']: d['close'] for d in twii_data}

        benchmark_curve = []
        first_nasdaq = None
        first_twii = None
        first_fx = None

        for date in trading_dates:
            nasdaq_price = nasdaq_map.get(date)
            twii_price = twii_map.get(date)
            if nasdaq_price and twii_price:
                current_fx = fx.rate(date)
                if first_nasdaq is None:
                    first_nasdaq = nasdaq_price
                    first_twii = twii_price
                    first_fx = current_fx

                # 50% 投資 NASDAQ（含匯率變動）+ 50% 投資 TWII
                us_equity = 0.5 * initial_capital * (nasdaq_price / first_nasdaq) * (current_fx / first_fx)
                tw_equity = 0.5 * initial_capital * (twii_price / first_twii)
                total_equity = us_equity + tw_equity

                benchmark_curve.append({
                    'date': date,
                    'equity': round(total_equity, 2)
                })

    elif market == 'tw':
        # 台灣加權指數（無匯率問題）
        name = '台灣加權指數'
        kline_data = container.market_loader.get_weighted_kline('^TWII', '6y', container.aligned_data)

        if not kline_data:
            logger.warning('[BENCHMARK] 找不到 %s 指數資料', name)
            return [], name

        price_map = {d['time']: d['close'] for d in kline_data}
        benchmark_curve = []
        first_price = None

        for date in trading_dates:
            price = price_map.get(date)
            if price:
                if first_price is None:
                    first_price = price
                equity = initial_capital * (price / first_price)
                benchmark_curve.append({
                    'date': date,
                    'equity': round(equity, 2)
                })

    else:  # us
        # NASDAQ（需考慮匯率：TWD → USD → 買指數 → 賣指數 → TWD）
        name = 'NASDAQ'
        kline_data = container.market_loader.get_weighted_kline('^IXIC', '6y', container.aligned_data)

        if not kline_data:
            logger.warning('[BENCHMARK] 找不到 %s 指數資料', name)
            return [], name

        price_map = {d['time']: d['close'] for d in kline_data}
        benchmark_curve = []
        first_price = None
        first_fx = None

        for date in trading_dates:
            price = price_map.get(date)
            if price:
                current_fx = fx.rate(date)
                if first_price is None:
                    first_price = price
                    first_fx = current_fx

                # 權益 = 初始資金 * (指數漲幅) * (匯率變動)
                # 匯率上升(TWD貶值) → 換回 TWD 更多
                equity = initial_capital * (price / first_price) * (current_fx / first_fx)
                benchmark_curve.append({
                    'date': date,
                    'equity': round(equity, 2)
                })

    logger.info('[BENCHMARK] %s 曲線計算完成: %d 筆', name, len(benchmark_curve))
    return benchmark_curve, name
