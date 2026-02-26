"""
FinPack API Server - 入口點

啟動 Flask 應用程式

模組架構（相互獨立）：
- core: 資料層（DataContainer, Indicators, Currency）
- backtest: 回測引擎（BacktestEngine）
- web: Flask 路由（stock_bp, market_bp, backtest_bp）
"""
import os
import sys

# 強制 stdout 即時輸出（不緩衝）
sys.stdout.reconfigure(line_buffering=True)

from flask import Flask, send_from_directory, jsonify

from core import container
from web.routes import stock_bp, market_bp, backtest_bp


def register_blueprints(app):
    """註冊所有 Blueprint"""
    app.register_blueprint(market_bp, url_prefix='/api')
    app.register_blueprint(stock_bp, url_prefix='/api')
    app.register_blueprint(backtest_bp, url_prefix='/api')
    
    print("  ✓ market_bp → /api/market-data, /api/kline/<symbol>")
    print("  ✓ stock_bp → /api/stocks, /api/industry/data")
    print("  ✓ backtest_bp → /api/backtest/run, /api/backtest/config")


def get_resource_path(relative_path):
    """取得資源路徑（支援 PyInstaller 打包）"""
    if getattr(sys, 'frozen', False):
        # PyInstaller 打包後的路徑
        base_path = sys._MEIPASS
    else:
        # 開發模式的路徑
        base_path = os.path.abspath('.')
    return os.path.join(base_path, relative_path)


def create_app():
    """工廠函數：建立 Flask 應用程式"""
    
    # 取得靜態檔案和模板路徑
    static_path = get_resource_path('static')
    template_path = get_resource_path('templates')
    
    # 初始化 Flask
    app = Flask(__name__, 
                static_folder=static_path,
                template_folder=template_path)
    
    print("=" * 50)
    print("🚀 FinPack API Server v2.0")
    print("=" * 50)
    
    # 預載資料
    print("\n📦 載入資料容器...")
    # container 已在 import 時自動初始化
    print(f"✅ 資料載入完成: {len(container.get_all_tickers())} 檔股票")
    
    # 註冊 API 路由
    print("\n🔗 註冊 API 路由...")
    register_blueprints(app)
    
    # ===== 靜態檔案與首頁 =====
    
    @app.route('/')
    def index():
        """首頁"""
        return send_from_directory(app.template_folder, 'index.html')
    
    @app.route('/<path:filename>')
    def serve_static(filename):
        """靜態檔案"""
        return send_from_directory(app.static_folder, filename)
    
    # ===== 健康檢查 =====
    
    @app.route('/api/health')
    def health_check():
        """API 健康檢查"""
        return jsonify({
            'status': 'ok',
            'stocks_count': len(container.get_all_tickers()),
            'last_update': str(container.last_update) if container.last_update else None
        })
    
    print("\n" + "=" * 50)
    print("✅ 應用程式初始化完成")
    print("=" * 50)
    
    return app


# ===== 主程式入口 =====

if __name__ == '__main__':
    app = create_app()
    
    # 開發模式設定
    debug_mode = os.environ.get('FLASK_DEBUG', 'True').lower() == 'true'
    port = int(os.environ.get('PORT', 5000))
    # 設為 False 可避免 debug 模式下重複初始化
    use_reloader = os.environ.get('FLASK_RELOADER', 'False').lower() == 'true'
    
    print(f"\n🌐 啟動伺服器: http://localhost:{port}")
    print(f"📝 Debug 模式: {debug_mode}")
    print(f"🔄 自動重載: {use_reloader}")
    print("-" * 50)
    
    app.run(
        host='0.0.0.0',
        port=port,
        debug=debug_mode,
        use_reloader=use_reloader,
        threaded=True
    )
