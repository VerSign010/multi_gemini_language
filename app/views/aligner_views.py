# app/views/aligner_views.py
from flask import Blueprint, render_template, request, jsonify, Response
from ..services.gemini_service import process_alignment_request
import logging
from ..services.doc_to_sheet_service import doc_to_sheet_automation_flow
from .sheets_views import get_credentials_from_session

aligner_bp = Blueprint('aligner', __name__)

@aligner_bp.route('/aligner')
def aligner_page():
    return render_template('aligner.html')

@aligner_bp.route('/process_doc_to_sheet', methods=['POST'])
def process_doc_to_sheet():
    creds = get_credentials_from_session()
    if not creds:
        return Response("用户未授权或凭证已过期。", status=401)

    params = request.get_json()
    
    # 确保 diagnostic_mode 也在检查范围内（虽然它是可选的，但这样更严谨）
    required_params = [
        'doc_url', 'sheet_url', 'sheet_name', 
        'model_name', 'temperature', 'batch_size',
        'interval_min', 'interval_max', 'diagnostic_mode'
    ]
    
    if not all(key in params for key in required_params):
        return Response("请求缺少必要参数。", status=400)

    return Response(
        doc_to_sheet_automation_flow(params, creds),
        mimetype='text/event-stream'
    )