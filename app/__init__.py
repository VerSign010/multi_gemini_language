# app/__init__.py
from flask import Flask
from .config import Config

def create_app():
    """
    应用工厂函数 (最终精简版)。
    这个版本直接将对齐工具作为应用的根页面。
    """
    app = Flask(__name__)
    app.config.from_object(Config)
    Config.init_app(app)

    # 导入对齐工具的蓝图
    from .views.aligner_views import aligner_bp
    
    # --- 核心修改 ---
    # 将 aligner_bp 注册到应用的根URL ("/") 上
    # 这意味着访问 "your-app.onrender.com/" 就会直接显示对齐工具
    app.register_blueprint(aligner_bp, url_prefix='/')
    # ----------------

    return app