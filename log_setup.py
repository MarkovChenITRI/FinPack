"""
日誌系統設定工具

供 run.py 和 main.py 在啟動時呼叫，設定統一的日誌格式與輸出目標。

【重要】必須在所有其他 import 之前呼叫，以確保 container 初始化時的
日誌（core.container / core.market 等）也能被捕獲並寫入指定的 log 檔案。

使用方式（放在 run.py / main.py 最頂部）：
    import logging
    from log_setup import setup_logging
    setup_logging('run.log')          # 必須在 from core import ... 之前
    # 之後才 import core / web / backtest
"""
import logging
import sys

LOG_FORMAT = '%(asctime)s [%(levelname)-5s] %(name)-25s %(message)s'
DATE_FORMAT = '%Y-%m-%d %H:%M:%S'


def setup_logging(log_file: str, level: int = logging.INFO) -> None:
    """
    設定全域日誌系統（檔案 + 終端機雙輸出）

    Args:
        log_file: 日誌檔案路徑（如 'run.log', 'main.log'）
        level:    日誌等級（預設 INFO）
    """
    handlers = [
        logging.FileHandler(log_file, encoding='utf-8', mode='w'),
        logging.StreamHandler(sys.stdout),
    ]

    logging.basicConfig(
        level=level,
        format=LOG_FORMAT,
        datefmt=DATE_FORMAT,
        handlers=handlers,
        force=True,
    )

    # 抑制第三方套件的冗余日誌
    for noisy in ('yfinance', 'urllib3', 'peewee', 'werkzeug', 'requests',
                  'curl_cffi', 'hpack', 'httpcore', 'httpx'):
        logging.getLogger(noisy).setLevel(logging.WARNING)
