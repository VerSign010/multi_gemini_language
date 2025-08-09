# app/config.py
import os
import json
from dotenv import load_dotenv

# 加载 .env 文件中的环境变量
load_dotenv()

class Config:
    """应用配置类"""
    SECRET_KEY = os.getenv('FLASK_SECRET_KEY', 'a_very_secret_key_for_development')
    
    # Google OAuth 2.0 设置
    os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
    GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID')
    GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET')
    CLIENT_SECRETS_FILE = 'client_secret.json'
    
    # --- 这里是核心修改 ---
    # 新增了 Google Docs 的只读权限
    SCOPES = [
        'https://www.googleapis.com/auth/spreadsheets',       # 已有的 Sheets 权限 (读和写)
        'https://www.googleapis.com/auth/documents.readonly' # 新增的 Docs 只读权限
    ]
    # --------------------

    REDIRECT_URI = 'http://127.0.0.1:5000/callback'

    # Gemini API 设置
    GEMINI_API_KEY = os.getenv("GOOGLE_API_KEY")

    @staticmethod
    def init_app(app):
        # 动态创建 client_secret.json 文件
        try:
            client_config = {
                "web": {
                    "client_id": Config.GOOGLE_CLIENT_ID,
                    "client_secret": Config.GOOGLE_CLIENT_SECRET,
                    "redirect_uris": [Config.REDIRECT_URI],
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token"
                }
            }
            with open(Config.CLIENT_SECRETS_FILE, 'w') as f:
                json.dump(client_config, f)
        except Exception as e:
            app.logger.error(f"创建 client_secret.json 文件失败: {e}")

        # 配置 Gemini API
        try:
            import google.generativeai as genai
            genai.configure(api_key=Config.GEMINI_API_KEY)
        except Exception as e:
            app.logger.error(f"配置 Gemini API 失败: {e}")