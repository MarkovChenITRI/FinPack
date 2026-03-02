"""
BTC-USD Smart Money Concepts 策略回測 CLI 入口

使用方式：
    python run_btc.py                        # 使用預設參數
    python run_btc.py --start 2023-01-01     # 自訂起始日期
    python run_btc.py --timeframe 1d         # 時間框架
    python run_btc.py --debug                # 使用本地快取
    python run_btc.py --short                # 啟用做空
    python run_btc.py --risk 0.01            # 每筆風險 1%
"""
import argparse
import logging
import sys
from pathlib import Path

# 確保 root 目錄在 sys.path
sys.path.insert(0, str(Path(__file__).parent))

from log_setup import setup_logging
from core.data import smart_load_btc, slice_ohlcv
from backtest.smc_config import load_smc_config
from backtest.smc_engine import SmcEngine

logger = logging.getLogger(__name__)


# =============================================================================
# 報告格式化
# =============================================================================

def format_smc_report(result, config: dict) -> str:
    """格式化 SMC 回測報告（純文字）"""
    lines = []
    sep   = '=' * 55

    lines.append(sep)
    lines.append('  BTC-USD SMC 策略回測報告')
    lines.append(sep)

    # 策略設定
    lines.append(f'\n策略設定')
    lines.append(f'  交易對    : {config["symbol"]}')
    lines.append(f'  時間框架  : {config["timeframe"]}')
    lines.append(f'  回測期間  : {config["start_date"]} ~ {config.get("end_date") or "最新"}')
    lines.append(f'  初始資金  : ${config["initial_capital"]:,.2f}')
    lines.append(f'  每筆風險  : {config["risk_per_trade"]:.1%}')
    lines.append(f'  方向      : {"多空雙向" if config["allow_long"] and config["allow_short"] else "做多" if config["allow_long"] else "做空"}')

    # 績效摘要
    r = result.to_dict()
    lines.append(f'\n績效摘要')
    lines.append(f'  初始資金  : {r["initial_capital"]}')
    lines.append(f'  最終資產  : {r["final_equity"]}')
    lines.append(f'  總報酬率  : {r["total_return"]}')
    lines.append(f'  年化報酬  : {r["annualized_return"]}')
    lines.append(f'  最大回撤  : {r["max_drawdown"]}')
    lines.append(f'  Sharpe    : {r["sharpe_ratio"]}')

    # 交易統計
    lines.append(f'\n交易統計')
    lines.append(f'  總交易數  : {r["total_trades"]}')
    lines.append(f'  勝場 / 敗場: {r["win_trades"]} / {r["loss_trades"]}')
    lines.append(f'  勝率      : {r["win_rate"]}')
    lines.append(f'  平均風報比: {r["avg_rr"]}')

    # 最近 5 筆交易
    if result.trades:
        lines.append(f'\n最近交易（最後 5 筆）')
        for t in result.trades[-5:]:
            lines.append(
                f'  {t["entry_date"]} → {t["exit_date"]} '
                f'[{t["direction"]:5}] '
                f'進@{t["entry_price"]:>10} 出@{t["exit_price"]:>10} '
                f'PnL: {t["pnl"]:>12}  ({t["reason"]})'
            )

    lines.append('\n' + sep)
    return '\n'.join(lines)


# =============================================================================
# CLI 主函數
# =============================================================================

def parse_args():
    parser = argparse.ArgumentParser(
        description='BTC-USD Smart Money Concepts 策略回測'
    )
    parser.add_argument('--start',     default=None,  help='回測起始日期 YYYY-MM-DD')
    parser.add_argument('--end',       default=None,  help='回測結束日期 YYYY-MM-DD')
    parser.add_argument('--timeframe', default='1d',  choices=['1d', '4h', '1h'],
                        help='時間框架（預設 1d）')
    parser.add_argument('--capital',   type=float,    default=10_000,
                        help='初始資金 USD（預設 10000）')
    parser.add_argument('--risk',      type=float,    default=0.02,
                        help='每筆風險百分比（預設 0.02 = 2%%）')
    parser.add_argument('--short',     action='store_true',
                        help='啟用做空（預設只做多）')
    parser.add_argument('--debug',     action='store_true',
                        help='使用本地快取（debug 模式）')
    parser.add_argument('--pivot',     type=int, default=5,
                        help='Pivot 確認根數（預設 5）')
    return parser.parse_args()


def main():
    args = parse_args()
    setup_logging()

    logger.info('=== BTC-USD SMC 回測啟動 ===')

    # 建立配置
    user_params = {
        'timeframe':    args.timeframe,
        'initial_capital': args.capital,
        'risk_per_trade':  args.risk,
        'allow_short':  args.short,
        'pivot_lookback': args.pivot,
    }
    if args.start:
        user_params['start_date'] = args.start
    if args.end:
        user_params['end_date'] = args.end

    config = load_smc_config(user_params)

    # 抓取資料
    logger.info(f'[DATA] 載入 {config["symbol"]} {config["timeframe"]} 資料...')
    ohlcv = smart_load_btc(
        symbol    = config['symbol'],
        timeframe = config['timeframe'],
        use_cache = args.debug,
    )

    if ohlcv.empty:
        logger.error('無法取得 BTC-USD 資料，請確認網路或快取')
        sys.exit(1)

    logger.info(f'[DATA] 共 {len(ohlcv)} 根 K 線 '
                f'({str(ohlcv.index[0])[:10]} ~ {str(ohlcv.index[-1])[:10]})')

    # 執行回測
    engine = SmcEngine(ohlcv, config)
    result = engine.run(
        start_date = config['start_date'],
        end_date   = config.get('end_date'),
    )

    # 輸出報告
    report = format_smc_report(result, config)
    print(report)

    # 比較基準：BTC Buy & Hold
    start_ts  = ohlcv.index.searchsorted(config['start_date'])
    end_ts    = len(ohlcv) - 1
    bh_start  = ohlcv['Close'].iloc[start_ts]
    bh_end    = ohlcv['Close'].iloc[end_ts]
    bh_return = (bh_end - bh_start) / bh_start
    print(f'\n  [基準] BTC Buy & Hold 報酬率: {bh_return:.2%}')
    print(f'  [策略] 超額報酬: {result.total_return - bh_return:+.2%}')
    print()


if __name__ == '__main__':
    main()
