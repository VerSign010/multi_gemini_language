# app/__init__.py

from flask import Flask
from .config import Config

def create_app():
    """
    应用工厂函数 (服务账号模式)。
    这个函数创建并配置Flask应用实例。
    """
    app = Flask(__name__)
    
    # 1. 从 config.py 文件中的 Config 类加载配置
    app.config.from_object(Config)

    # 2. 初始化应用级的服务，例如配置 Gemini API
    Config.init_app(app)

    # 3. 注册所有的蓝图 (Blueprints)
    #    蓝图用于将应用的不同部分模块化。
    from .views.main_views import main_bp
    from .views.sheets_views import sheets_bp
    from .views.translator_views import translator_bp
    from .views.aligner_views import aligner_bp
    
    app.register_blueprint(main_bp)
    app.register_blueprint(sheets_bp)
    app.register_blueprint(translator_bp)
    app.register_blueprint(aligner_bp)

    # 4. 返回创建好的应用实例
    return app