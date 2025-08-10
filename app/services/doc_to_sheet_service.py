# app/services/doc_to_sheet_service.py
# ... (所有顶部的函数 clean_text, extract_id_from_url, 等保持不变) ...
import re
import time
import random
import logging
import json
import unicodedata
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from .gemini_service import process_alignment_request

def clean_text(text):
    if not text: return ""
    text = re.sub(r'[\n\r\t\v\f]+', ' ', text)
    text = re.sub(r' +', ' ', text)
    text = ''.join(c for c in text if unicodedata.category(c)[0] != 'C')
    text = text.replace('\u00ad', '')
    return text.strip()

def extract_id_from_url(url):
    match = re.search(r'/d/([^/]+)', url)
    return match.group(1) if match else None

def extract_gid_from_url(url):
    match = re.search(r'#gid=(\d+)', url)
    return int(match.group(1)) if match else None

def _read_paragraph_elements(elements):
    text = ''
    for element in elements:
        if 'textRun' in element:
            text += element.get('textRun').get('content', '')
    return text

def read_text_from_doc_table(doc_id, creds):
    try:
        service = build('docs', 'v1', credentials=creds)
        doc = service.documents().get(documentId=doc_id).execute()
        content = doc.get('body').get('content')
        paragraphs_to_process = []
        for element in content:
            if 'table' in element:
                table = element.get('table')
                for row in table.get('tableRows'):
                    cell_texts = []
                    for cell in row.get('tableCells'):
                        cell_text = ""
                        for content_item in cell.get('content'):
                            if 'paragraph' in content_item:
                                cell_text += _read_paragraph_elements(content_item.get('paragraph').get('elements', []))
                        cleaned_cell_text = clean_text(cell_text)
                        cell_texts.append(cleaned_cell_text)
                    if any(cell_texts):
                        paragraphs_to_process.append("\n<--CELL_BREAK-->\n".join(cell_texts))
                break
        return paragraphs_to_process
    except HttpError as e:
        try:
            error_details = json.loads(e.content.decode('utf-8'))['error']
            if any(detail.get('reason') == 'SERVICE_DISABLED' for detail in error_details.get('details', [])):
                project_id = error_details['details'][0]['metadata']['consumer'].split('/')[-1]
                activation_url = f"https://console.developers.google.com/apis/api/docs.googleapis.com/overview?project={project_id}"
                raise Exception(f"Google Docs API 被禁用。请访问此链接开启: {activation_url}")
        except (json.JSONDecodeError, KeyError, IndexError): pass
        if e.resp.status == 403: raise Exception("无权访问该 Google Doc。请检查文件共享权限。")
        elif e.resp.status == 404: raise Exception("Google Doc 未找到。")
        else: raise e
    except Exception as e:
        logging.error(f"读取 Doc 时发生未知错误: {e}")
        raise

def get_sheet_name_from_url(sheet_url, creds):
    sheet_id = extract_id_from_url(sheet_url)
    gid = extract_gid_from_url(sheet_url)
    if not sheet_id:
        raise Exception("Google Sheet 链接无效。")
    try:
        service = build('sheets', 'v4', credentials=creds)
        spreadsheet_metadata = service.spreadsheets().get(
            spreadsheetId=sheet_id, fields='sheets(properties(sheetId,title))'
        ).execute()
        sheets = spreadsheet_metadata.get('sheets', [])
        if not sheets:
            raise Exception("目标电子表格中没有任何工作表。")
        if gid is not None:
            for sheet in sheets:
                if sheet.get('properties', {}).get('sheetId') == gid:
                    return sheet.get('properties', {}).get('title')
            raise Exception(f"链接中的 GID '{gid}' 无效或在目标表格中不存在。")
        else:
            first_sheet_title = sheets[0].get('properties', {}).get('title')
            if not first_sheet_title:
                raise Exception("无法获取第一个工作表的名称。")
            return first_sheet_title
    except HttpError as e:
        if e.resp.status == 403: raise Exception("无权访问该 Google Sheet 以获取工作表名称。")
        elif e.resp.status == 404: raise Exception("Google Sheet 未找到。")
        else: raise e
    except Exception as e:
        logging.error(f"获取工作表名称时发生未知错误: {e}")
        raise

def write_to_sheet(sheet_id, sheet_name, values, creds):
    try:
        if not values:
            logging.warning("写入操作被跳过，因为传入的数据列表为空。")
            return None
        rows_to_write = [line.split('\t') for line in values if isinstance(line, str) and line.strip()]
        if not rows_to_write:
            logging.warning("写入操作被跳过，因为过滤后没有有效的行可供写入。")
            return None
        service = build('sheets', 'v4', credentials=creds)
        body = {'values': rows_to_write}
        result = service.spreadsheets().values().append(
            spreadsheetId=sheet_id, range=f"'{sheet_name}'!A1",
            valueInputOption='USER_ENTERED', insertDataOption='INSERT_ROWS', body=body
        ).execute()
        logging.info(f"Google Sheets API 返回的完整响应: {result}")
        return result
    except HttpError as e:
        if e.resp.status == 403: raise Exception("无权访问或编辑该 Google Sheet。")
        elif e.resp.status == 404: raise Exception("Google Sheet 未找到。")
        else: raise e
    except Exception as e:
        logging.error(f"写入 Sheet 时发生未知错误: {e}")
        raise

def doc_to_sheet_automation_flow(params, creds):
    try:
        yield "data: 正在解析链接和参数...\n\n"
        doc_id = extract_id_from_url(params['doc_url'])
        sheet_id = extract_id_from_url(params['sheet_url'])
        batch_size = params['batch_size']

        if not doc_id: yield "data: [ERROR] Google Doc 链接无效。\n\n"; return
        if not sheet_id: yield "data: [ERROR] Google Sheet 链接无效。\n\n"; return

        try:
            yield "data: 正在从URL智能检测目标工作表名称...\n\n"
            sheet_name = get_sheet_name_from_url(params['sheet_url'], creds)
            yield f"data: ✅ 将写入工作表: '{sheet_name}'\n\n"
        except Exception as e:
            yield f"data: ❌ [ERROR] 检测工作表名称失败: {e}\n\n"; return

        yield f"data: 正在读取并净化 Google Doc 内容...\n\n"
        paragraphs = read_text_from_doc_table(doc_id, creds)
        if not paragraphs: yield "data: [ERROR] Doc 中未找到表格或表格为空。\n\n"; return

        total_paragraphs = len(paragraphs)
        total_batches = (total_paragraphs + batch_size - 1) // batch_size
        yield f"data: 读取成功！共 {total_paragraphs} 个段落，将分为 {total_batches} 个批次处理。\n\n"

        all_aligned_lines = []
        
        for i in range(total_batches):
            batch_start_index = i * batch_size
            batch_end_index = batch_start_index + batch_size
            batch_paragraphs = paragraphs[batch_start_index:batch_end_index]
            start_para_num = batch_start_index + 1
            end_para_num = min(batch_end_index, total_paragraphs)
            
            yield f"data: 正在处理第 {i + 1}/{total_batches} 批 (段落 {start_para_num}-{end_para_num})...\n\n"
            batch_text_to_process = "\n\n<--PARAGRAPH_BREAK-->\n\n".join(batch_paragraphs)
            
            if not batch_text_to_process.strip():
                yield f"data: 跳过批次 {i + 1} (空批次)。\n\n"; continue
            
            try:
                # --- 核心修改：将 api_key 传递给处理函数 ---
                aligned_text = process_alignment_request(
                    text=batch_text_to_process, 
                    model_name=params['model_name'], 
                    temperature=params['temperature'],
                    api_key=params['gemini_api_key'] # 新增
                )
                # -----------------------------------------
                if aligned_text and aligned_text.strip():
                    lines = aligned_text.strip().split('\n')
                    all_aligned_lines.extend(lines)
                    yield f"data: ✅ 批次 {i + 1} 处理完成，生成了 {len(lines)} 行对齐文本。\n\n"
                else:
                    yield f"data: ⚠️ [WARNING] 批次 {i + 1} 处理后返回空结果，已跳过。\n\n"
            except Exception as e:
                error_message = f"批次 {i + 1} 处理失败: {e}"
                yield f"data: ❌ [ERROR] {error_message}\n\n"
                all_aligned_lines.append(f"错误：{error_message}")
            
            if i < total_batches - 1:
                sleep_time = random.randint(params['interval_min'], params['interval_max'])
                yield f"data: ⏳ 等待 {sleep_time} 秒...\n\n"; time.sleep(sleep_time)

        if not all_aligned_lines:
            yield "data: [DONE] 没有可写入的数据，任务结束。\n\n"; return
            
        yield f"data: 所有批次处理完毕，正在将 {len(all_aligned_lines)} 行结果写入 Google Sheet...\n\n"
        result = write_to_sheet(sheet_id, sheet_name, all_aligned_lines, creds)
        if result and result.get('updates', {}).get('updatedCells', 0) > 0:
            yield f"data: [DONE] 数据写入成功！Google API 报告已写入 {result['updates']['updatedCells']} 个单元格。\n\n"
        else:
            yield f"data: [WARNING] API调用看似成功，但没有数据被实际写入。请检查后端日志。\n\n"
        
    except Exception as e:
        logging.error(f"自动化流程发生错误: {e}", exc_info=True)
        yield f"data: ❌ [ERROR] 流程意外终止: {e}\n\n"