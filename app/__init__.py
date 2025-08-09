# app/__init__.py

import logging
from flask import Flask
from flask_session import Session
from .config import Config

# 设置基础日志记录
logging.basicConfig(level=logging.INFO)

def create_app():
    """应用工厂函数"""
    logging.info("--- [INIT] Starting create_app()... ---")
    
    app = Flask(__name__)

    # 1. 从对象加载配置
    app.config.from_object(Config)
    logging.info("--- [INIT] App config loaded. ---")

    # 2. 强制检查 SECRET_KEY 是否存在且有效
    if not app.config.get('SECRET_KEY'):
        # 这是一个致命错误，如果 SECRET_KEY 无效，会话将永远无法工作
        logging.critical("--- [FATAL ERROR] SECRET_KEY is not set! App cannot run securely. ---")
        raise ValueError("A SECRET_KEY is required to run this application.")
    else:
        logging.info("--- [INIT] SECRET_KEY is set successfully. ---")

    # 3. 配置服务器端会话
    app.config['SESSION_TYPE'] = 'filesystem'
    app.config['SESSION_PERMANENT'] = False
    app.config['SESSION_USE_SIGNER'] = True
    logging.info(f"--- [INIT] Session type configured to: {app.config['SESSION_TYPE']} ---")
    
    # 4. 初始化 Session 扩展
    Session(app)
    logging.info("--- [INIT] Flask-Session initialized. ---")
    
    # 5. 调用配置类中的其他初始化逻辑
    Config.init_app(app)

    # 6. 注册所有的蓝图 (Blueprints)
    logging.info("--- [INIT] Registering blueprints... ---")
    from .views.main_views import main_bp
    from .views.sheets_views import sheets_bp
    from .views.translator_views import translator_bp
    from .views.aligner_views import aligner_bp
    
    app.register_blueprint(main_bp)
    app.register_blueprint(sheets_bp)
    app.register_blueprint(translator_bp)
    app.register_blueprint(aligner_bp)
    logging.info("--- [INIT] All blueprints registered. ---")
    
    logging.info("--- [INIT] create_app() finished successfully. ---")
    return app