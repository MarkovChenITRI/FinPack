"""
回測報告格式化模組

提供回測結果的格式化輸出功能。
支援 Money 類型的金額處理。
"""
import io
import logging
from typing import List, Dict, Any, Union

from core.currency import Money

logger = logging.getLogger(__name__)


def _get_amount(value: Union[Money, float, int]) -> float:
    """從 Money 或數值取得金額"""
    if isinstance(value, Money):
        return value.amount
    return float(value) if value is not None else 0.0


def format_backtest_report(
    result: Any,
    cash: Union[Money, float],
    current_holdings: List[Dict],
    initial_capital: Union[Money, float],
    amount_per_stock: Union[Money, float],
    max_positions: int,
    start_dt: Any,
    end_dt: Any,
    elapsed: float = 0.0
) -> str:
    """
    格式化回測報告
    
    Args:
        result: BacktestResult 實例
        cash: 現金餘額 (Money 或 float)
        current_holdings: 當前持倉列表
        initial_capital: 初始資金 (Money 或 float)
        amount_per_stock: 每檔投入金額 (Money 或 float)
        max_positions: 最大持倉數
        start_dt: 開始日期
        end_dt: 結束日期
        elapsed: 執行時間（秒）
    
    Returns:
        str: 格式化的報告字串
    """
    output = io.StringIO()
    summary = result.to_dict()
    
    # 轉換 Money 為數值
    cash_val = _get_amount(cash)
    initial_val = _get_amount(initial_capital)
    amount_val = _get_amount(amount_per_stock)
    final_val = _get_amount(result.final_equity)
    
    output.write("=" * 60 + "\n")
    output.write("FinPack 自動交易回測結果\n")
    output.write("=" * 60 + "\n\n")
    
    # 回測參數
    output.write("【回測參數】\n")
    output.write(f"  初始資金: ${initial_val:,.0f} TWD\n")
    output.write(f"  每檔投入: ${amount_val:,.0f} TWD\n")
    output.write(f"  最大持倉: {max_positions} 檔\n")
    output.write(f"  回測期間: {start_dt.strftime('%Y-%m-%d')} ~ {end_dt.strftime('%Y-%m-%d')}\n")
    if elapsed > 0:
        output.write(f"  執行時間: {elapsed:.1f} 秒\n")
    output.write("\n")
    
    # 六大績效指標
    output.write("【六大績效指標】\n")
    output.write(f"  1. 總報酬率:   {summary['total_return']}\n")
    output.write(f"  2. 年化報酬:   {summary['annualized_return']}\n")
    output.write(f"  3. 最大回撤:   {summary['max_drawdown']}\n")
    output.write(f"  4. 夏普比率:   {summary['sharpe_ratio']}\n")
    output.write(f"  5. 勝率:       {summary['win_rate']}\n")
    output.write(f"  6. 交易次數:   {summary['total_trades']}\n\n")
    
    # 資產摘要
    output.write("【資產摘要】\n")
    output.write(f"  初始資金: ${initial_val:,.0f} TWD\n")
    output.write(f"  最終資產: ${final_val:,.0f} TWD\n")
    output.write(f"  現金餘額: ${cash_val:,.0f} TWD\n")
    output.write(f"  持股市值: ${final_val - cash_val:,.0f} TWD\n\n")
    
    # 最新持有
    _format_holdings(output, current_holdings)
    
    # 交易紀錄
    _format_trades(output, result.trades)
    
    output.write("=" * 60 + "\n")

    report_str = output.getvalue()
    logger.info('\n%s', report_str)

    return report_str


def _format_holdings(output: io.StringIO, current_holdings: List[Dict]):
    """格式化當前持倉（支援 Money 類型）"""
    output.write(f"【最新持有】（共 {len(current_holdings)} 檔）\n")
    
    if current_holdings:
        output.write("-" * 70 + "\n")
        output.write(f"{'標的':<10} {'國家':<4} {'產業':<12} {'股數':>8} {'成本':>12} {'現價':>12} {'損益':>8}\n")
        output.write("-" * 70 + "\n")
        
        for h in current_holdings:
            pnl_str = f"{h['pnl_pct']:+.1%}"
            industry = h['industry'][:10] + '..' if len(h['industry']) > 12 else h['industry']
            country = h.get('country', 'US')[:2]
            
            # 處理 Money 類型
            avg_cost = h['avg_cost']
            current_price = h['current_price']
            
            if isinstance(avg_cost, Money):
                cost_str = str(avg_cost)
            else:
                cost_str = f"${avg_cost:,.2f}"
            
            if isinstance(current_price, Money):
                price_str = str(current_price)
            else:
                price_str = f"${current_price:,.2f}"
            
            output.write(
                f"{h['symbol']:<10} {country:<4} {industry:<12} "
                f"{h['shares']:>8} {cost_str:>12} "
                f"{price_str:>12} {pnl_str:>8}\n"
            )
        
        output.write("-" * 70 + "\n")
    else:
        output.write("  （無持倉）\n")
    
    output.write("\n")


def _format_trades(output: io.StringIO, trades: List[Dict], max_recent: int = 30):
    """格式化交易紀錄（支援 Money 類型）"""
    recent_trades = trades[-max_recent:] if len(trades) > max_recent else trades
    
    output.write(f"【交易紀錄】（最近 {len(recent_trades)} 筆，共 {len(trades)} 筆）\n")
    output.write("-" * 75 + "\n")
    output.write(f"{'日期':<12} {'類型':<6} {'標的':<10} {'股數':>8} {'價格':>14} {'金額(TWD)':>12} {'原因':<12}\n")
    output.write("-" * 75 + "\n")
    
    for t in reversed(recent_trades):
        type_str = "買入" if t['type'] == 'buy' else "賣出"
        # price 和 amount_twd 現在是字串格式
        price_str = t['price'] if isinstance(t['price'], str) else f"${t['price']:,.2f}"
        amount_twd_str = t.get('amount_twd', '')
        
        output.write(
            f"{t['date']:<12} {type_str:<6} {t['symbol']:<10} "
            f"{t['shares']:>8} {price_str:>14} {amount_twd_str:>12} {t['reason']:<12}\n"
        )
    
    output.write("-" * 75 + "\n\n")


def format_holdings_summary(holdings: List[Dict]) -> str:
    """
    格式化持倉摘要（簡短版）
    
    Args:
        holdings: 持倉列表
    
    Returns:
        str: 摘要字串
    """
    if not holdings:
        return "無持倉"
    
    total_value = sum(
        _get_amount(h.get('market_value', 0)) 
        for h in holdings
    )
    symbols = [h['symbol'] for h in holdings[:5]]
    
    summary = f"{len(holdings)} 檔, 市值 ${total_value:,.0f}"
    if symbols:
        summary += f" ({', '.join(symbols)}"
        if len(holdings) > 5:
            summary += f" +{len(holdings)-5}更多"
        summary += ")"
    
    return summary


def format_backtest_line_message(
    result: Any,
    current_holdings: List[Dict],
    start_dt: Any,
    end_dt: Any,
) -> str:
    """
    格式化 LINE 訊息（適合手機閱讀的精簡版本）

    包含：回測期間、六大績效、近三日買賣訊號、目前持股清單

    Args:
        result: BacktestResult 實例
        current_holdings: 當前持倉列表
        start_dt: 回測開始日期
        end_dt: 回測結束日期

    Returns:
        tuple[str, bool]: (LINE 訊息字串, 近三日是否有交易訊號)
    """
    from datetime import timedelta

    summary = result.to_dict()
    SEP = '─' * 22

    lines = []

    # ── 標題 ──────────────────────────────────────────────
    lines.append(f'📊 {end_dt.strftime("%Y-%m-%d")} 每日建議')
    lines.append(f'設立日：{start_dt.strftime("%Y-%m-%d")}')
    lines.append(SEP)

    # ── 六大績效 ──────────────────────────────────────────
    lines.append('【系統績效】')
    lines.append(f'總報酬  {summary["total_return"]}')
    lines.append(f'年化    {summary["annualized_return"]}')
    lines.append(f'最大回撤 {summary["max_drawdown"]}')
    lines.append(f'Sharpe  {summary["sharpe_ratio"]}')
    lines.append(f'勝率    {summary["win_rate"]}')
    lines.append(f'交易    {summary["total_trades"]} 筆')
    lines.append(SEP)

    # ── 近三日買賣訊號 ────────────────────────────────────
    lines.append('【交易訊號 (近三日)】')
    cutoff = (end_dt - timedelta(days=3)).strftime('%Y-%m-%d')
    recent = [t for t in result.trades if t['date'] >= cutoff]
    has_recent_trades = bool(recent)
    if recent:
        for t in recent:
            icon = '🟢' if t['type'] == 'buy' else '🔴'
            action = '買入' if t['type'] == 'buy' else '賣出'
            date_short = t['date'][5:]   # MM-DD
            lines.append(f'{icon} {date_short} {action} {t["symbol"]}')
    else:
        lines.append('（無訊號）')
    lines.append(SEP)

    # ── 目前持股 ──────────────────────────────────────────
    lines.append('現有倉位')
    if current_holdings:
        sorted_holdings = sorted(current_holdings, key=lambda h: h['pnl_pct'], reverse=True)
        for h in sorted_holdings:
            pnl = h['pnl_pct']  # 小數，如 0.052
            pnl_str = f'{pnl:+.1%}'
            country_flag = '🇹🇼' if h.get('country') == 'TW' else '🇺🇸'
            lines.append(f'{country_flag} {h["symbol"]:<8} {pnl_str}')
    else:
        lines.append('（無持倉）')

    return '\n'.join(lines), has_recent_trades


def format_performance_summary(result: Any) -> str:
    """
    格式化績效摘要（單行版）
    
    Args:
        result: BacktestResult 實例
    
    Returns:
        str: 摘要字串
    """
    summary = result.to_dict()
    return (
        f"報酬 {summary['total_return']} | "
        f"年化 {summary['annualized_return']} | "
        f"回撤 {summary['max_drawdown']} | "
        f"Sharpe {summary['sharpe_ratio']}"
    )
