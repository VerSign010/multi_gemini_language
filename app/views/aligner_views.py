# app/views/aligner_views.py
from flask import Blueprint, render_template, request, Response
import logging
from google.oauth2 import service_account
from ..config import Config
from ..services.doc_to_sheet_service import doc_to_sheet_automation_flow

aligner_bp = Blueprint('aligner', __name__)

def get_service_account_creds():
    """
    从文件加载服务账号凭证。
    它会首先尝试Render的私密文件路径，如果失败，则尝试本地路径，方便开发。
    """
    # Render 上的标准路径
    render_secret_path = '/etc/secrets/service_account.json'
    # 本地开发时的路径 (假设文件在项目根目录)
    local_secret_path = 'service_account.json'
    
    try:
        # 优先尝试 Render 路径
        creds = service_account.Credentials.from_service_account_file(
            render_secret_path, scopes=Config.SCOPES
        )
        logging.info("成功从 Render 私密文件路径加载服务账号凭证。")
        return creds
    except FileNotFoundError:
        logging.warning(f"在 Render 路径 '{render_secret_path}' 未找到凭证，尝试本地路径...")
        try:
            # 如果失败，尝试本地路径
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

@aligner_bp.route('/aligner')
def aligner_page():
    """
    对齐工具页面，现在无需登录即可访问。
    """
    return render_template('aligner.html')

@aligner_bp.route('/process_doc_to_sheet', methods=['POST'])
def process_doc_to_sheet():
    """
    处理从 Doc 到 Sheet 的自动化流程的后端端点。
    """
    # 1. 直接从文件获取服务账号凭证
    creds = get_service_account_creds()
    if not creds:
        # 如果凭证加载失败，返回一个明确的服务器错误
        error_message = "服务器端凭证配置错误，无法执行任务。请检查服务账号密钥文件是否已正确部署。"
        def error_generator():
            yield f"data: [ERROR] {error_message}\n\n"
        return Response(error_generator(), mimetype='text/event-stream', status=500)

    # 2. 从请求中获取参数，后续逻辑保持不变
    params = request.get_json()
    required_params = [
        'doc_url', 'sheet_url', 'sheet_name', 
        'model_name', 'temperature', 'batch_size',
        'interval_min', 'interval_max', 'diagnostic_mode'
    ]
    
    if not all(key in params for key in required_params):
        return Response("请求缺少必要参数。", status=400)

    # 3. 调用核心处理流程
    return Response(
        doc_to_sheet_automation_flow(params, creds),
        mimetype='text/event-stream'
    )