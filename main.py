"""
FinPack API Server - 入口點

啟動 Flask 應用程式

模組架構（相互獨立）：
- core: 資料層（DataContainer, Indicators, Currency）
- backtest: 回測引擎（BacktestEngine）
- web: Flask 路由（stock_bp, market_bp, backtest_bp）
"""
# ===== 最優先：設定日誌系統（必須在 from core import ... 之前）=====
import logging
from log_setup import setup_logging
setup_logging('main.log')

# ===== 其他 import =====
import os
import sys

from flask import Flask, send_from_directory, jsonify

from core import container
from web.routes import stock_bp, market_bp, backtest_bp

logger = logging.getLogger('main')


def register_blueprints(app):
    """註冊所有 Blueprint"""
    app.register_blueprint(market_bp, url_prefix='/api')
    app.register_blueprint(stock_bp, url_prefix='/api')
    app.register_blueprint(backtest_bp, url_prefix='/api')

    logger.info('  market_bp  → /api/market-data, /api/kline/<symbol>')
    logger.info('  stock_bp   → /api/stocks, /api/industry/data')
    logger.info('  backtest_bp → /api/backtest/run, /api/backtest/config')


def get_resource_path(relative_path):
    """取得資源路徑（支援 PyInstaller 打包）"""
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.abspath('.')
    return os.path.join(base_path, relative_path)


def create_app():
    """工廠函數：建立 Flask 應用程式"""

    static_path = get_resource_path('static')
    template_path = get_resource_path('templates')

    app = Flask(__name__,
                static_folder=static_path,
                template_folder=template_path)

    logger.info('=' * 50)
    logger.info('FinPack API Server v2.0')
    logger.info('=' * 50)

    # container 已在 import 時自動初始化
    logger.info('資料載入完成: %d 檔股票', len(container.get_all_tickers()))

    # 預載市場資料（更新快取，有 max_staleness_days 保護避免重複抓取）
    logger.info('開始預載市場資料...')
    container.market_loader.preload_all(aligned_data=container.aligned_data)

    # 註冊 API 路由
    logger.info('註冊 API 路由...')
    register_blueprints(app)

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
            'status': 'ok',
            'stocks_count': len(container.get_all_tickers()),
            'last_update': str(container.last_update) if container.last_update else None
        })

    logger.info('=' * 50)
    logger.info('應用程式初始化完成')
    logger.info('=' * 50)

    return app


# ===== 主程式入口 =====

if __name__ == '__main__':
    app = create_app()

    debug_mode = os.environ.get('FLASK_DEBUG', 'True').lower() == 'true'
    port = int(os.environ.get('PORT', 5000))
    use_reloader = os.environ.get('FLASK_RELOADER', 'False').lower() == 'true'

    logger.info('啟動伺服器: http://localhost:%d', port)
    logger.info('Debug 模式: %s', debug_mode)
    logger.info('自動重載: %s', use_reloader)
    logger.info('-' * 50)

    app.run(
        host='0.0.0.0',
        port=port,
        debug=debug_mode,
        use_reloader=use_reloader,
        threaded=True
    )
