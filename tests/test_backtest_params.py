"""
回測參數一致性測試

測試 Python 端（run.py）與 JS 端（backtest/*.js）的參數行為是否一致。
每個測試使用最小化配置，只啟用一個條件來驗證其行為。

使用方式:
    python tests/test_backtest_params.py
"""
import sys
import copy
from pathlib import Path

# 添加專案根目錄到 path
sys.path.insert(0, str(Path(__file__).parent.parent))

from datetime import datetime
import pandas as pd
from core.data import smart_load_or_fetch, filter_by_market
from core.align import align_close_prices
from core.indicator import Indicators
from core.currency import twd, usd, FX
from backtest import BacktestEngine

# 簡化版預設配置（只保留核心參數）
BASE_CONFIG = {
    'initial_capital': twd(1_000_000),
    'amount_per_stock': twd(100_000),
    'max_positions': 5,
    'market': 'us',
    'rebalance_freq': 'weekly',
    'buy_conditions': {
        'sharpe_rank': {'enabled': False, 'top_n': 15},
        'sharpe_threshold': {'enabled': False, 'threshold': 1.0},
        'sharpe_streak': {'enabled': False, 'days': 3},
        'growth_streak': {'enabled': False, 'days': 2},
        'growth_rank': {'enabled': False, 'top_n': 15},
        'sort_sharpe': {'enabled': False},
        'sort_industry': {'enabled': False, 'per_industry': 2},
    },
    'sell_conditions': {
        'sharpe_fail': {'enabled': False, 'periods': 2, 'top_n': 15},
        'growth_fail': {'enabled': False, 'days': 5, 'threshold': 0},
        'not_selected': {'enabled': False, 'periods': 3},
        'drawdown': {'enabled': False, 'threshold': 0.40},
        'weakness': {'enabled': False, 'rank_k': 20, 'periods': 3},
    },
    'rebalance_strategy': {
        'type': 'immediate',  # 最簡單的策略
        'top_n': 5,
        'sharpe_threshold': 0,
        'batch_ratio': 0.20,
        'concentrate_top_k': 3,
    }
}


def load_test_data():
    """載入測試資料（使用快取）"""
    print("[LOAD] 載入測試資料...")
    stock_data, watchlist, stock_info, last_update = smart_load_or_fetch(use_cache=True)
    stock_data, stock_info = filter_by_market(stock_data, stock_info, 'us')
    
    print(f"[OK] 載入 {len(stock_data)} 檔股票")
    
    close_df, _ = align_close_prices(stock_data)
    
    # 使用完整資料計算指標，但只回測最近 30 天
    # （Sharpe 計算需要 252 天歷史）
    print(f"[OK] 總資料: {len(close_df)} 天, 回測最後 30 天")
    
    return close_df, stock_info


def run_test(config: dict, close_df: pd.DataFrame, stock_info: dict, test_name: str, backtest_days: int = 30) -> dict:
    """執行單次測試"""
    indicators = Indicators(close_df, stock_info)
    fx = FX(use_cache=True)
    
    # 診斷：檢查指標是否正確計算
    dates = indicators.get_dates()  # 回傳字串格式
    all_sharpe_dates = list(indicators.sharpe_rank_by_country.keys())
    if dates:
        last_date = dates[-1]  # 字串格式
        print(f"  [診斷] 資料期間: {close_df.index[0].date()} ~ {close_df.index[-1].date()}")
        print(f"  [診斷] sharpe_rank_by_country 有 {len(all_sharpe_dates)} 天有效排名")
        # 檢查最後一天的排名
        sharpe_rank = indicators.sharpe_rank_by_country.get(last_date, {})
        us_rank = sharpe_rank.get('US', [])
        print(f"  [診斷] 最後日期 {last_date}, US Sharpe 排名: {us_rank[:5]}...")
    
    engine = BacktestEngine(close_df, indicators, stock_info, config, fx)
    
    # 只回測最後 N 天
    end_dt = close_df.index[-1]
    start_idx = max(0, len(close_df) - backtest_days)
    start_dt = close_df.index[start_idx]
    print(f"  [回測] 期間: {start_dt.date()} ~ {end_dt.date()} ({backtest_days} 天)")
    
    result = engine.run(start_date=start_dt, end_date=end_dt)
    
    return {
        'test_name': test_name,
        'total_trades': result.total_trades,
        'win_trades': result.win_trades,
        'final_equity': result.final_equity.amount,
        'positions_count': len(engine.positions),
    }


def test_sharpe_rank():
    """測試 sharpe_rank 買入條件"""
    print("\n" + "="*60)
    print("測試: sharpe_rank (Sharpe 排名前 N 名)")
    print("="*60)
    
    close_df, stock_info = load_test_data()
    
    config = copy.deepcopy(BASE_CONFIG)
    config['buy_conditions']['sharpe_rank'] = {'enabled': True, 'top_n': 10}
    
    result = run_test(config, close_df, stock_info, "sharpe_rank")
    print(f"結果: 交易 {result['total_trades']} 次, 持倉 {result['positions_count']} 檔")
    return result


def test_sharpe_threshold():
    """測試 sharpe_threshold 買入條件"""
    print("\n" + "="*60)
    print("測試: sharpe_threshold (Sharpe >= 門檻)")
    print("="*60)
    
    close_df, stock_info = load_test_data()
    
    config = copy.deepcopy(BASE_CONFIG)
    config['buy_conditions']['sharpe_threshold'] = {'enabled': True, 'threshold': 0.5}
    
    result = run_test(config, close_df, stock_info, "sharpe_threshold")
    print(f"結果: 交易 {result['total_trades']} 次, 持倉 {result['positions_count']} 檔")
    return result


def test_growth_rank():
    """測試 growth_rank 買入條件"""
    print("\n" + "="*60)
    print("測試: growth_rank (Growth 排名前 N 名)")
    print("="*60)
    
    close_df, stock_info = load_test_data()
    
    config = copy.deepcopy(BASE_CONFIG)
    config['buy_conditions']['growth_rank'] = {'enabled': True, 'top_n': 10}
    
    result = run_test(config, close_df, stock_info, "growth_rank")
    print(f"結果: 交易 {result['total_trades']} 次, 持倉 {result['positions_count']} 檔")
    return result


def test_growth_streak():
    """測試 growth_streak 買入條件"""
    print("\n" + "="*60)
    print("測試: growth_streak (Growth 連續 N 天在排名前 50%)")
    print("="*60)
    
    close_df, stock_info = load_test_data()
    
    config = copy.deepcopy(BASE_CONFIG)
    config['buy_conditions']['growth_streak'] = {'enabled': True, 'days': 3, 'percentile': 50}
    
    result = run_test(config, close_df, stock_info, "growth_streak")
    print(f"結果: 交易 {result['total_trades']} 次, 持倉 {result['positions_count']} 檔")
    return result


def test_sharpe_streak():
    """測試 sharpe_streak 買入條件（已修正使用自己的 top_n）"""
    print("\n" + "="*60)
    print("測試: sharpe_streak (連續 N 天在 Sharpe Top-K)")
    print("="*60)
    
    close_df, stock_info = load_test_data()
    
    config = copy.deepcopy(BASE_CONFIG)
    # 注意：sharpe_streak 現在使用自己的 top_n，不是從 sharpe_rank 取
    config['buy_conditions']['sharpe_streak'] = {'enabled': True, 'days': 3, 'top_n': 15}
    
    result = run_test(config, close_df, stock_info, "sharpe_streak")
    print(f"結果: 交易 {result['total_trades']} 次, 持倉 {result['positions_count']} 檔")
    return result


def test_sort_sharpe():
    """測試 sort_sharpe 選股方式"""
    print("\n" + "="*60)
    print("測試: sort_sharpe (按 Sharpe 排序選股)")
    print("="*60)
    
    close_df, stock_info = load_test_data()
    
    config = copy.deepcopy(BASE_CONFIG)
    config['buy_conditions']['sharpe_rank'] = {'enabled': True, 'top_n': 20}
    config['buy_conditions']['sort_sharpe'] = {'enabled': True}
    
    result = run_test(config, close_df, stock_info, "sort_sharpe")
    print(f"結果: 交易 {result['total_trades']} 次, 持倉 {result['positions_count']} 檔")
    return result


def test_sort_industry():
    """測試 sort_industry 選股方式（產業分散）"""
    print("\n" + "="*60)
    print("測試: sort_industry (產業分散選股)")
    print("="*60)
    
    close_df, stock_info = load_test_data()
    
    config = copy.deepcopy(BASE_CONFIG)
    config['buy_conditions']['sharpe_rank'] = {'enabled': True, 'top_n': 20}
    config['buy_conditions']['sort_industry'] = {'enabled': True, 'per_industry': 2}
    
    result = run_test(config, close_df, stock_info, "sort_industry")
    print(f"結果: 交易 {result['total_trades']} 次, 持倉 {result['positions_count']} 檔")
    return result


def test_sell_sharpe_fail():
    """測試 sharpe_fail 賣出條件"""
    print("\n" + "="*60)
    print("測試: sharpe_fail (連續 N 期掉出 Sharpe Top-K)")
    print("="*60)
    
    close_df, stock_info = load_test_data()
    
    config = copy.deepcopy(BASE_CONFIG)
    config['buy_conditions']['sharpe_rank'] = {'enabled': True, 'top_n': 15}
    config['sell_conditions']['sharpe_fail'] = {'enabled': True, 'periods': 2, 'top_n': 15}
    
    result = run_test(config, close_df, stock_info, "sharpe_fail")
    print(f"結果: 交易 {result['total_trades']} 次, 持倉 {result['positions_count']} 檔")
    return result


def test_sell_growth_fail():
    """測試 growth_fail 賣出條件"""
    print("\n" + "="*60)
    print("測試: growth_fail (近 N 天 Growth 平均 < 門檻)")
    print("="*60)
    
    close_df, stock_info = load_test_data()
    
    config = copy.deepcopy(BASE_CONFIG)
    config['buy_conditions']['sharpe_rank'] = {'enabled': True, 'top_n': 15}
    config['sell_conditions']['growth_fail'] = {'enabled': True, 'days': 5, 'threshold': 0}
    
    result = run_test(config, close_df, stock_info, "growth_fail")
    print(f"結果: 交易 {result['total_trades']} 次, 持倉 {result['positions_count']} 檔")
    return result


def test_sell_drawdown():
    """測試 drawdown 賣出條件"""
    print("\n" + "="*60)
    print("測試: drawdown (回撤超過 40% 停損)")
    print("="*60)
    
    close_df, stock_info = load_test_data()
    
    config = copy.deepcopy(BASE_CONFIG)
    config['buy_conditions']['sharpe_rank'] = {'enabled': True, 'top_n': 15}
    config['sell_conditions']['drawdown'] = {'enabled': True, 'threshold': 0.40}
    
    result = run_test(config, close_df, stock_info, "drawdown")
    print(f"結果: 交易 {result['total_trades']} 次, 持倉 {result['positions_count']} 檔")
    return result


def test_sell_weakness():
    """測試 weakness 賣出條件"""
    print("\n" + "="*60)
    print("測試: weakness (Sharpe AND Growth 排名同時 > K)")
    print("="*60)
    
    close_df, stock_info = load_test_data()
    
    config = copy.deepcopy(BASE_CONFIG)
    config['buy_conditions']['sharpe_rank'] = {'enabled': True, 'top_n': 15}
    config['sell_conditions']['weakness'] = {'enabled': True, 'rank_k': 20, 'periods': 3}
    
    result = run_test(config, close_df, stock_info, "weakness")
    print(f"結果: 交易 {result['total_trades']} 次, 持倉 {result['positions_count']} 檔")
    return result


def test_rebalance_delayed():
    """測試 delayed 再平衡策略"""
    print("\n" + "="*60)
    print("測試: delayed (Sharpe Top-5 平均 > 0 才買入)")
    print("="*60)
    
    close_df, stock_info = load_test_data()
    
    config = copy.deepcopy(BASE_CONFIG)
    config['buy_conditions']['sharpe_rank'] = {'enabled': True, 'top_n': 15}
    config['rebalance_strategy'] = {
        'type': 'delayed',
        'top_n': 5,
        'sharpe_threshold': 0,
    }
    
    result = run_test(config, close_df, stock_info, "delayed")
    print(f"結果: 交易 {result['total_trades']} 次, 持倉 {result['positions_count']} 檔")
    return result


def test_rebalance_batch():
    """測試 batch 再平衡策略"""
    print("\n" + "="*60)
    print("測試: batch (每次投入 20% 可用資金)")
    print("="*60)
    
    close_df, stock_info = load_test_data()
    
    config = copy.deepcopy(BASE_CONFIG)
    config['buy_conditions']['sharpe_rank'] = {'enabled': True, 'top_n': 15}
    config['rebalance_strategy'] = {
        'type': 'batch',
        'batch_ratio': 0.20,
    }
    
    result = run_test(config, close_df, stock_info, "batch")
    print(f"結果: 交易 {result['total_trades']} 次, 持倉 {result['positions_count']} 檔")
    return result


def test_rebalance_immediate():
    """測試 immediate 再平衡策略"""
    print("\n" + "="*60)
    print("測試: immediate (立即投入)")
    print("="*60)
    
    close_df, stock_info = load_test_data()
    
    config = copy.deepcopy(BASE_CONFIG)
    config['buy_conditions']['sharpe_rank'] = {'enabled': True, 'top_n': 15}
    config['rebalance_strategy'] = {'type': 'immediate'}
    
    result = run_test(config, close_df, stock_info, "immediate")
    print(f"結果: 交易 {result['total_trades']} 次, 持倉 {result['positions_count']} 檔")
    return result


def test_rebalance_concentrated():
    """測試 concentrated 再平衡策略（已修正加入領先判斷）"""
    print("\n" + "="*60)
    print("測試: concentrated (集中投資前 K 名，需明確領先)")
    print("="*60)
    
    close_df, stock_info = load_test_data()
    
    config = copy.deepcopy(BASE_CONFIG)
    config['buy_conditions']['sharpe_rank'] = {'enabled': True, 'top_n': 15}
    config['rebalance_strategy'] = {
        'type': 'concentrated',
        'concentrate_top_k': 3,
        'lead_margin': 0.3,  # 領先差距 30%
    }
    
    result = run_test(config, close_df, stock_info, "concentrated")
    print(f"結果: 交易 {result['total_trades']} 次, 持倉 {result['positions_count']} 檔")
    return result


def test_rebalance_none():
    """測試 none 再平衡策略"""
    print("\n" + "="*60)
    print("測試: none (不主動再平衡)")
    print("="*60)
    
    close_df, stock_info = load_test_data()
    
    config = copy.deepcopy(BASE_CONFIG)
    config['buy_conditions']['sharpe_rank'] = {'enabled': True, 'top_n': 15}
    config['rebalance_strategy'] = {'type': 'none'}
    
    result = run_test(config, close_df, stock_info, "none")
    print(f"結果: 交易 {result['total_trades']} 次, 持倉 {result['positions_count']} 檔")
    return result


def main():
    print("="*60)
    print("回測參數一致性測試")
    print("="*60)
    
    results = []
    
    # === 買入條件測試 ===
    print("\n>>> 買入條件測試 <<<")
    results.append(test_sharpe_rank())
    results.append(test_sharpe_threshold())
    results.append(test_sharpe_streak())
    results.append(test_growth_rank())
    results.append(test_growth_streak())
    results.append(test_sort_sharpe())
    results.append(test_sort_industry())
    
    # === 賣出條件測試 ===
    print("\n>>> 賣出條件測試 <<<")
    results.append(test_sell_sharpe_fail())
    results.append(test_sell_growth_fail())
    results.append(test_sell_drawdown())
    results.append(test_sell_weakness())
    
    # === 再平衡策略測試 ===
    print("\n>>> 再平衡策略測試 <<<")
    results.append(test_rebalance_immediate())
    results.append(test_rebalance_batch())
    results.append(test_rebalance_delayed())
    results.append(test_rebalance_concentrated())
    results.append(test_rebalance_none())
    
    # 總結
    print("\n" + "="*60)
    print("測試總結")
    print("="*60)
    
    for r in results:
        print(f"  [{r['test_name']:20}] 交易: {r['total_trades']:3} 次, 持倉: {r['positions_count']} 檔")
    
    print("\n✅ 所有測試完成")


if __name__ == '__main__':
    main()
