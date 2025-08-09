# app/__init__.py
from flask import Flask
from .config import Config

def create_app():
    """
    应用工厂函数 (最终修正版)。
    """
    app = Flask(__name__)
    app.config.from_object(Config)
    Config.init_app(app)

    # 导入对齐工具的蓝图
    from .views.aligner_views import aligner_bp
    
    # --- 核心修改 ---
    # 我们不再使用 url_prefix，而是直接注册蓝图。
    # 具体的URL路径将完全由视图函数自己决定。
    app.register_blueprint(aligner_bp)
    # ----------------

    return app