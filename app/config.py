# app/config.py
import os
from dotenv import load_dotenv
import google.generativeai as genai

# 加载 .env 文件中的环境变量
load_dotenv()

class Config:
    """应用配置类 (服务账号模式)"""
    # Flask 的密钥仍然需要，用于其他潜在的加密需求
    SECRET_KEY = os.getenv('FLASK_SECRET_KEY', 'a_very_secret_key_for_development_service_account')
    
    # --- 服务账号配置 ---
    # Render 会将私密文件放在这个标准路径下
    # 对于本地开发，您可以将 service_account.json 放在项目根目录，并使用 'service_account.json'
    SERVICE_ACCOUNT_FILE = os.getenv('GOOGLE_APPLICATION_CREDENTIALS', '/etc/secrets/service_account.json')
    
    # 定义服务账号需要的权限范围
    SCOPES = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/documents.readonly'
    ]
    # --------------------

    # Gemini API 设置
    GEMINI_API_KEY = os.getenv("GOOGLE_API_KEY")

    @staticmethod
    def init_app(app):
        """初始化应用级的配置。"""
        # 不再需要动态创建 client_secret.json
        
        # 配置 Gemini API
        try:
            if Config.GEMINI_API_KEY:
                genai.configure(api_key=Config.GEMINI_API_KEY)
            else:
                app.logger.warning("GEMINI_API_KEY 未在环境变量中设置。")
        except Exception as e:
            app.logger.error(f"配置 Gemini API 失败: {e}")