# app/services/gemini_service.py

import logging
import time
import random
import re
import google.generativeai as genai
from functools import wraps
# 导入需要捕获的特定异常类型
try:
    from google.api_core.exceptions import ServiceUnavailable, DeadlineExceeded, InternalServerError, TooManyRequests
except ImportError:
    class ServiceUnavailable(Exception): pass
    class DeadlineExceeded(Exception): pass
    class InternalServerError(Exception): pass
    class TooManyRequests(Exception): pass

# --- retry_on_api_error 装饰器已移入此文件 ---
def retry_on_api_error(max_retries=3, base_delay=5):
    """
    一个装饰器，用于在捕获到指定的Google API错误时进行指数退避重试。
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            exceptions_to_catch = (ServiceUnavailable, DeadlineExceeded, InternalServerError, TooManyRequests)
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except exceptions_to_catch as e:
                    logging.warning(f"函数 '{func.__name__}' 遇到API错误 (尝试次数: {attempt + 1}/{max_retries}): {e}")
                    if attempt < max_retries - 1:
                        sleep_time = base_delay * (2 ** attempt) + random.uniform(0, 1)
                        logging.info(f"将在 {sleep_time:.2f} 秒后重试...")
                        time.sleep(sleep_time)
                    else:
                        logging.error(f"函数 '{func.__name__}' 所有重试均告失败。")
                        raise
        return wrapper
    return decorator

def load_instructions():
    """只加载对齐工具需要的指令。"""
    try:
        with open('aligner_prompt.md', 'r', encoding='utf-8') as f:
            return {'aligner': f.read()}
    except FileNotFoundError:
        logging.error("指令文件未找到: aligner_prompt.md")
        return {'aligner': "错误：无法加载对齐指令。"}

INSTRUCTIONS = load_instructions()

@retry_on_api_error(max_retries=3, base_delay=3)
def process_alignment_request(text, model_name, temperature=0.2):
    """处理三语对齐请求。"""
    system_instruction = INSTRUCTIONS.get('aligner', 'Please align the text.')
    prompt = f"---\n{text}\n---"
    
    model = genai.GenerativeModel(
        model_name=model_name,
        system_instruction=system_instruction,
        generation_config=genai.types.GenerationConfig(temperature=temperature)
    )
    
    logging.info(f"Aligner: 正在进行API调用 (Model: {model_name}, Temp: {temperature})...")
    response = model.generate_content(prompt)
    
    if not response.parts:
        error_info = "未知原因"
        if hasattr(response, 'prompt_feedback'):
            block_reason = getattr(response.prompt_feedback, 'block_reason', None)
            if block_reason:
                error_info = f"内容可能被拦截，原因: {block_reason}"
            else:
                safety_ratings = getattr(response.prompt_feedback, 'safety_ratings', [])
                if safety_ratings:
                    error_info = f"内容安全评级问题: {safety_ratings}"
        
        error_info += "。这通常发生在输入文本过长（批次太大）或触发了内容安全策略时。请尝试减小批次大小后重试。"
        raise Exception(f"模型没有返回任何内容。终止原因: {error_info}")

    raw_result = response.text
    pattern = r"^\s*```(?:tsv)?\n?|\n?```\s*$"
    cleaned_result = re.sub(pattern, "", raw_result, flags=re.MULTILINE).strip()
    return cleaned_result