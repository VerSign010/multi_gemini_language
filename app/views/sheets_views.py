# app/views/sheets_views.py
from flask import Blueprint, render_template, request, session, Response, redirect, url_for
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import json
import time
import random
import logging
from ..services.gemini_service import call_gemini_batch_for_sheets, INSTRUCTIONS
from ..services.utils import parse_gemini_reports
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request as GoogleAuthRequest
# --- 这里是核心修改 ---
# 导入 RefreshError 异常，以便我们可以捕获它
from google.auth.exceptions import RefreshError
# --------------------
from ..config import Config

sheets_bp = Blueprint('sheets', __name__)

def get_credentials_from_session():
    """
    从会话中安全地加载、检查和刷新凭证。
    如果刷新失败（特别是由于 scope 变化），会返回 None。
    """
    if 'credentials' not in session:
        return None
    
    try:
        creds_dict = json.loads(session['credentials'])
        # 使用我们 config 文件中最新的、包含所有权限的 SCOPES 来创建凭证对象
        creds = Credentials.from_authorized_user_info(creds_dict, Config.SCOPES)
        
        # 检查凭证是否已过期，并且是否包含 refresh_token
        if creds.expired and creds.refresh_token:
            logging.info("凭证已过期，正在尝试刷新...")
            # 使用最新的 SCOPES 来刷新 token
            creds.refresh(GoogleAuthRequest())
            # 将刷新后的新凭证存回会话
            session['credentials'] = creds.to_json()
            logging.info("凭证刷新成功。")
            
        return creds
        
    # --- 这里是核心修改 ---
    # 捕获 RefreshError，这通常在 scope 更改后发生
    except RefreshError as e:
        logging.warning(f"刷新 Token 失败 (可能是 scope 已更改): {e}")
        # 清除会话中无效的凭证，强制用户重新登录
        session.pop('credentials', None)
        session.pop('state', None)
        return None # 返回 None，让调用它的路由知道需要重定向到登录页面
    # --------------------
        
    except (json.JSONDecodeError, KeyError) as e:
        logging.error(f"从会话加载凭证失败: {e}")
        return None

@sheets_bp.route('/google_sheets_tool')
def google_sheets_tool_page():
    creds = get_credentials_from_session()
    # 如果 get_credentials_from_session 因为任何原因（包括刷新失败）返回了 None，
    # 就重定向到登录页面，强制用户重新授权。
    if not creds or not creds.valid:
        return redirect(url_for('main.login'))
    return render_template('google_sheets_tool.html')

@sheets_bp.route('/process_sheet', methods=['POST'])
def process_sheet():
    creds = get_credentials_from_session()
    if not creds:
        return Response("用户未授权或凭证已过期，请重新登录。", status=401)

    data = request.get_json()
    required_params = ['sheet_id', 'sheet_name', 'read_cols', 'write_col', 'start_row', 'end_row']
    if not all(param in data for param in required_params):
        return Response("请求缺少必要参数。", status=400)

    def generate():
        try:
            service = build('sheets', 'v4', credentials=creds)
            sheet = service.spreadsheets()
            sheet_id = data['sheet_id']
            sheet_name = data['sheet_name']
            read_cols = data['read_cols']
            write_col = data['write_col']
            start_row = int(data['start_row'])
            end_row = int(data['end_row'])
            model_name = data.get('model_name', 'gemini-1.5-pro-latest')
            batch_size = int(data.get('batch_size', 5))
            interval_min = int(data.get('interval_min', 3))
            interval_max = int(data.get('interval_max', 5))
            temperature = float(data.get('temperature', 0.1))
            check_type = data.get('check_type', 'full_review')
            system_instruction = INSTRUCTIONS.get(check_type, INSTRUCTIONS['full_review'])
            
            first_col = read_cols[0] if read_cols else 'A' # 确保 read_cols 不为空
            last_col = read_cols[-1] if read_cols else 'A'
            
            read_range = f"'{sheet_name}'!{first_col}{start_row}:{last_col}{end_row}"
            yield f"data: 任务类型 '{check_type}' - 正在从 {read_range} 读取数据...\n\n"
            result = sheet.values().get(spreadsheetId=sheet_id, range=read_range, valueRenderOption='UNFORMATTED_VALUE').execute()
            all_rows_from_sheet = result.get('values', [])
            if not all_rows_from_sheet:
                yield f"data: [ERROR] 在工作表 '{sheet_name}' 的指定范围内未找到任何数据。\n\n"
                return
            yield f"data: 成功读取 {len(all_rows_from_sheet)} 行数据。将以每批 {batch_size} 行的规模进行处理...\n\n"
            total_rows_to_process = len(all_rows_from_sheet)
            for i in range(0, total_rows_to_process, batch_size):
                batch_rows_data = all_rows_from_sheet[i:i + batch_size]
                current_batch_start_row = start_row + i
                yield f"data: 正在处理批次: 行 {current_batch_start_row} 到 {current_batch_start_row + len(batch_rows_data) - 1}...\n\n"
                texts_to_check = []
                line_numbers_in_batch = []
                for row_idx, row_data in enumerate(batch_rows_data):
                    if not row_data or not any(row_data): continue
                    line_num = str(row_data[0]) if row_data[0] else str(current_batch_start_row + row_idx)
                    line_numbers_in_batch.append(line_num)
                    content_to_join = [str(cell) for cell in row_data[1:]]
                    content = " | ".join(content_to_join)
                    texts_to_check.append(f"行号 {line_num}: {content}")
                if not texts_to_check:
                    yield f"data: 跳过空批次 (行 {current_batch_start_row})...\n\n"
                    continue
                raw_text_response = call_gemini_batch_for_sheets(texts_to_check, system_instruction, model_name, temperature)
                parsed_reports = parse_gemini_reports(raw_text_response)
                write_values = []
                for row_idx, row_data in enumerate(batch_rows_data):
                    if not row_data or not row_data[0]: continue
                    actual_line_num = str(row_data[0]) if row_data[0] else str(current_batch_start_row + row_idx)
                    result_text = parsed_reports.get(actual_line_num, "[报告缺失或行号不匹配]")
                    write_values.append([result_text])
                if not write_values:
                    yield f"data: 批次 (行 {current_batch_start_row}) 无有效数据可写回，跳过。\n\n"
                    continue
                write_range = f"'{sheet_name}'!{write_col}{current_batch_start_row}:{write_col}{current_batch_start_row + len(write_values) - 1}"
                body = {'values': write_values}
                sheet.values().update(spreadsheetId=sheet_id, range=write_range, valueInputOption='USER_ENTERED', body=body).execute()
                yield f"data: 批次 (行 {current_batch_start_row}-{current_batch_start_row + len(write_values) - 1}) 处理完成并已写回。\n\n"
                if i + batch_size < total_rows_to_process:
                    sleep_time = random.randint(interval_min, interval_max)
                    yield f"data: 等待 {sleep_time} 秒...\n\n"
                    time.sleep(sleep_time)
            yield "data: [DONE] 所有批次处理完毕！\n\n"
        except HttpError as err:
            error_details = json.loads(err.content.decode('utf-8'))['error']
            error_message = f"Google Sheets API 错误: {error_details.get('message', '未知错误')}"
            logging.error(error_message)
            yield f"data: [ERROR] {error_message}\n\n"
        except Exception as e:
            logging.error(f"未知服务器错误: {e}", exc_info=True)
            yield f"data: [ERROR] 未知服务器错误: {e}\n\n"
    return Response(generate(), mimetype='text/event-stream')