"""
FinPack API Server - 入口點

啟動 Flask 應用程式，載入所有資料模組並註冊 API 路由
"""
import os
from flask import Flask, send_from_directory, jsonify

# 載入資料容器與路由
from src import get_container
from routes import register_blueprints


def create_app():
    """工廠函數：建立 Flask 應用程式"""
    
    # 初始化 Flask
    app = Flask(__name__, 
                static_folder='static',
                template_folder='templates')
    
    print("=" * 50)
    print("🚀 FinPack API Server v2.0")
    print("=" * 50)
    
    # 預載資料
    print("\n📦 載入資料容器...")
    container = get_container()
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
        container = get_container()
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
    
    print(f"\n🌐 啟動伺服器: http://localhost:{port}")
    print(f"📝 Debug 模式: {debug_mode}")
    print("-" * 50)
    
    app.run(
        host='0.0.0.0',
        port=port,
        debug=debug_mode,
        threaded=True
    )
