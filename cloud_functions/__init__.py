"""
FinPack Cloud Functions Package

獨立回測套件，可部署至 Google Cloud Functions

Usage:
    # 本地測試
    python -m cloud_functions.run
    
    # Cloud Functions 部署
    gcloud functions deploy finpack-backtest \
        --runtime python311 \
        --trigger-http \
        --entry-point main \
        --source ./cloud_functions
"""
from .run import main, run_backtest
from .config import DEFAULT_BACKTEST_CONFIG

__all__ = ['main', 'run_backtest', 'DEFAULT_BACKTEST_CONFIG']
__version__ = '1.0.0'
