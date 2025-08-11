# app/views/aligner_views.py
from flask import Blueprint, render_template, request, Response
import logging
from google.oauth2 import service_account
from ..config import Config
from ..services.doc_to_sheet_service import doc_to_sheet_automation_flow

aligner_bp = Blueprint('aligner', __name__)

def get_service_account_creds():
    render_secret_path = '/etc/secrets/service_account.json'
    local_secret_path = 'service_account.json'
    try:
        creds = service_account.Credentials.from_service_account_file(
            render_secret_path, scopes=Config.SCOPES
        )
        logging.info("成功从 Render 私密文件路径加载服务账号凭证。")
        return creds
    except FileNotFoundError:
        logging.warning(f"在 Render 路径 '{render_secret_path}' 未找到凭证，尝试本地路径...")
        try:
            creds = service_account.Credentials.from_service_account_file(
                local_secret_path, scopes=Config.SCOPES
            )
            logging.info(f"成功从本地路径 '{local_secret_path}' 加载服务账号凭证。")
            return creds
        except FileNotFoundError:
            logging.error(f"服务账号密钥文件在 Render 和本地路径均未找到。")
            return None
    except Exception as e:
        logging.error(f"加载服务账号凭证时发生未知错误: {e}")
        return None

@aligner_bp.route('/')
def aligner_page():
    return render_template('aligner.html')

@aligner_bp.route('/process_doc_to_sheet', methods=['POST'])
def process_doc_to_sheet():
    creds = get_service_account_creds()
    if not creds:
        error_message = "服务器端凭证配置错误。请检查服务账号密钥文件是否已正确部署。"
        def error_generator():
            yield f"data: [ERROR] {error_message}\n\n"
        return Response(error_generator(), mimetype='text/event-stream', status=500)

    params = request.get_json()
    
    # --- 核心修改：将 system_instruction 加入必要参数列表 ---
    required_params = [
        'gemini_api_key',
        'doc_url', 'sheet_url', 
        'model_name', 'temperature', 'batch_size',
        'interval_min', 'interval_max',
        'system_instruction' # 新增
    ]
    # -------------------------------------------------
    
    params.setdefault('diagnostic_mode', False)
    if not all(key in params for key in required_params):
        return Response("请求缺少必要参数。", status=400)

    return Response(
        doc_to_sheet_automation_flow(params, creds),
        mimetype='text/event-stream'
    )