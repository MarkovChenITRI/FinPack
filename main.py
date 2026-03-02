"""
FinPackV2 API Server - BTC-USD SMC 版入口點

啟動 Flask 應用程式，提供 BTC-USD 市場數據與 SMC 策略回測 API。

模組架構：
- core:    資料層（BtcDataContainer, SmcIndicators）
- backtest: SMC 回測引擎（SmcEngine, SmcConfig）
- web:     Flask 路由（market_bp, backtest_bp）
"""
import logging
import os
import sys

from log_setup import setup_logging
setup_logging('main.log')

from flask import Flask, send_from_directory, jsonify

from core import container, smc_service
from web.routes import market_bp, backtest_bp

logger = logging.getLogger('main')


def get_resource_path(relative_path: str) -> str:
    """取得資源路徑（支援 PyInstaller 打包）"""
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.abspath('.')
    return os.path.join(base_path, relative_path)


def create_app() -> Flask:
    """工廠函數：建立 Flask 應用程式"""
    static_path   = get_resource_path('static')
    template_path = get_resource_path('templates')

    app = Flask(__name__,
                static_folder=static_path,
                template_folder=template_path)

    logger.info('=' * 50)
    logger.info('FinPackV2 API Server - BTC-USD SMC')
    logger.info('=' * 50)

    # 預載 BTC-USD 日線資料
    logger.info('[INIT] 載入 BTC-USD 日線資料...')
    container.load('1d')
    if container.initialized:
        logger.info('[INIT] BTC-USD 日線資料就緒，最新收盤: $%.2f', container.latest_close)
        # 預計算 1D SMC 信號（4H/1H 按需計算）
        logger.info('[INIT] 預計算 SMC 指標...')
        smc_service.precompute(container.get_ohlcv('1d'), '1d')
        logger.info('[INIT] SMC 指標預計算完成')
    else:
        logger.warning('[INIT] BTC-USD 資料載入失敗，API 部分功能不可用')

    # 註冊 API 路由
    logger.info('[INIT] 註冊 API 路由...')
    app.register_blueprint(market_bp, url_prefix='/api')
    app.register_blueprint(backtest_bp, url_prefix='/api')
    logger.info('[INIT]   market_bp   → /api/kline/btc, /api/market-status')
    logger.info('[INIT]   backtest_bp → /api/backtest/run, /api/backtest/config')

    @app.route('/')
    def index():
        return send_from_directory(app.template_folder, 'index.html')

    @app.route('/<path:filename>')
    def serve_static(filename):
        response = send_from_directory(app.static_folder, filename)
        if filename.endswith('.js'):
            response.headers['Cache-Control'] = 'no-store, must-revalidate'
        return response

    @app.route('/api/health')
    def health_check():
        return jsonify({
            'status':       'ok',
            'symbol':       'BTC-USD',
            'latest_close': container.latest_close,
            'initialized':  container.initialized,
        })

    logger.info('=' * 50)
    logger.info('[INIT] 應用程式初始化完成')
    logger.info('=' * 50)
    return app


if __name__ == '__main__':
    app = create_app()

    debug_mode   = os.environ.get('FLASK_DEBUG', 'True').lower() == 'true'
    port         = int(os.environ.get('PORT', 5000))
    use_reloader = os.environ.get('FLASK_RELOADER', 'False').lower() == 'true'

    logger.info('啟動伺服器: http://localhost:%d', port)
    app.run(
        host='0.0.0.0',
        port=port,
        debug=debug_mode,
        use_reloader=use_reloader,
        threaded=True,
    )
