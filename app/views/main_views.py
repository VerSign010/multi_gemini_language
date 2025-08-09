# app/views/main_views.py
from flask import Blueprint, render_template, session, redirect, url_for, request, jsonify
from google_auth_oauthlib.flow import Flow
from google.auth.exceptions import OAuthError
from oauthlib.oauth2.rfc6749.errors import MismatchingStateError

from ..config import Config
from ..services.utils import to_plain_text
from ..services.gemini_service import INSTRUCTIONS
import google.generativeai as genai
import logging

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    # 检查 session 中是否有凭证，以决定显示 "进入工具" 还是 "登录"
    if 'credentials' in session:
        return render_template('index.html', logged_in=True)
    return render_template('index.html', logged_in=False)

@main_bp.route('/login')
def login():
    # 创建授权流程实例
    flow = Flow.from_client_secrets_file(
        Config.CLIENT_SECRETS_FILE,
        scopes=Config.SCOPES,
        redirect_uri=Config.REDIRECT_URI
    )
    
    # 获取授权 URL 和 state
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        prompt='consent',
        include_granted_scopes='true'
    )
    
    # 将 state 存储在 session 中，这是授权流程的关键部分
    session['state'] = state
    
    # 重定向到 Google 进行授权
    return redirect(authorization_url)

@main_bp.route('/callback')
def callback():
    # 从 session 中安全地弹出 state，这样它只能被使用一次
    # 如果 session 中没有 state，会返回 None，避免了 KeyError
    session_state = session.pop('state', None)

    # 1. 检查会话中是否存在 state
    if not session_state:
        error_msg = "会话状态 (session state) 丢失，授权流程中断。这可能是由于浏览器禁用了Cookie或会话已过期。"
        logging.error(f"Callback 失败: {error_msg}")
        return error_msg, 400

    # 2. 检查 Google 回调的 URL 中是否包含了 state 参数
    if 'state' not in request.args:
        error_msg = "Google 回调请求中缺少 state 参数。"
        logging.error(f"Callback 失败: {error_msg}")
        return error_msg, 400

    # 3. 严格比较 session 中的 state 和 URL 中的 state
    if request.args.get('state') != session_state:
        error_msg = "State 不匹配 (Mismatching state)，为防止 CSRF 攻击，授权已中止。"
        logging.error(f"Callback 失败: {error_msg}")
        return error_msg, 400
        
    try:
        # 重新创建 flow 实例，这次带上正确的 state
        flow = Flow.from_client_secrets_file(
            Config.CLIENT_SECRETS_FILE,
            scopes=Config.SCOPES,
            state=session_state, # 使用我们验证过的 state
            redirect_uri=Config.REDIRECT_URI
        )
        
        # 使用 Google 返回的完整 URL 来获取 token
        flow.fetch_token(authorization_response=request.url)
        
        # 将凭证信息序列化为 JSON 并存入 session
        credentials = flow.credentials
        session['credentials'] = credentials.to_json()
        
        # 授权成功，重定向到工具页面
        return redirect(url_for('sheets.google_sheets_tool_page'))
        
    except MismatchingStateError:
        # 这个异常理论上不会被触发，因为我们已经在前面手动检查了 state
        error_msg = "State 验证失败 (library check)，请求可能被篡改。"
        logging.error(f"Callback 失败: {error_msg}")
        return error_msg, 400
        
    except OAuthError as e:
        # 处理其他所有 OAuth 相关的错误
        error_msg = f"OAuth 认证错误: {e}"
        logging.error(f"Callback 失败: {error_msg}")
        return error_msg, 500
        
    except Exception as e:
        # 捕获其他未知错误
        logging.error(f"Callback 发生未知错误: {e}", exc_info=True)
        return "服务器发生未知内部错误，请稍后重试。", 500

@main_bp.route('/logout')
def logout():
    session.pop('credentials', None)
    session.pop('state', None)
    return redirect(url_for('main.index'))

# 其他路由保持不变...
@main_bp.route('/check_text', methods=['POST'])
def check_text():
    try:
        data = request.get_json()
        text = data.get('text')
        model_name = data.get('model_name', 'gemini-2.5-pro')
        temperature = float(data.get('temperature', 0.1))
        system_instruction = INSTRUCTIONS.get('full_review', 'Please review this text carefully.')
        model = genai.GenerativeModel(model_name=model_name, system_instruction=system_instruction, generation_config=genai.types.GenerationConfig(temperature=temperature))
        prompt = f"请严格遵循系统指令，审校以下文本：\n\n---\n{text}\n---"
        response = model.generate_content(prompt)
        usage = {"total_tokens": len(prompt.split()) + len(response.text.split())} 
        return jsonify({'result': to_plain_text(response.text), 'usage': usage})
    except Exception as e:
        logging.error(f"/check_text 错误: {e}")
        return jsonify({'error': str(e)}), 500