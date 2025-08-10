# app/services/gemini_service.py
import logging
import time
import random
import re
import google.generativeai as genai
from functools import wraps
from ..config import Config # 导入 Config 以便访问备用Key
try:
    from google.api_core.exceptions import ServiceUnavailable, DeadlineExceeded, InternalServerError, TooManyRequests
except ImportError:
    class ServiceUnavailable(Exception): pass
    class DeadlineExceeded(Exception): pass
    class InternalServerError(Exception): pass
    class TooManyRequests(Exception): pass

def retry_on_api_error(max_retries=3, base_delay=5):
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
    try:
        with open('aligner_prompt.md', 'r', encoding='utf-8') as f:
            return {'aligner': f.read()}
    except FileNotFoundError:
        logging.error("指令文件未找到: aligner_prompt.md")
        return {'aligner': "错误：无法加载对齐指令。"}

INSTRUCTIONS = load_instructions()

# 移除全局模型缓存，因为 API Key 是动态的
# model_cache = {}

@retry_on_api_error(max_retries=3, base_delay=3)
def process_alignment_request(text, model_name, temperature=0.2, api_key=None):
    """
    处理三语对齐请求。
    现在可以接收用户提供的 api_key。
    """
    # --- 核心修改：动态配置 API Key ---
    # 优先使用用户提供的 Key，如果为空，则回退到环境变量中的 Key
    final_api_key = api_key if api_key and api_key.strip() else Config.GEMINI_API_KEY
    
    if not final_api_key:
        raise Exception("Gemini API Key 未提供。请在前端输入或在服务器环境变量中配置。")
    
    try:
        # 每次调用都使用正确的 Key 进行配置
        genai.configure(api_key=final_api_key)
    except Exception as e:
        raise Exception(f"配置 Gemini API 失败: {e}")
    # ------------------------------------

    system_instruction = INSTRUCTIONS.get('aligner', 'Please align the text.')
    prompt = f"---\n{text}\n---"
    
    # 因为 Key 是动态的，所以每次都重新创建模型实例
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
        
        error_info += "。这通常发生在输入文本过长（批次太大）、API Key无效或触发了内容安全策略时。请检查您的API Key并尝试减小批次大小后重试。"
        raise Exception(f"模型没有返回任何内容。终止原因: {error_info}")

    raw_result = response.text
    pattern = r"^\s*```(?:tsv)?\n?|\n?```\s*$"
    cleaned_result = re.sub(pattern, "", raw_result, flags=re.MULTILINE).strip()
    return cleaned_result