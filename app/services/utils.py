# app/services/utils.py

import markdown
from bs4 import BeautifulSoup
import re
import time
import random
import logging
from functools import wraps
# 导入需要捕获的特定异常类型，确保程序能够识别它们
try:
    from google.api_core.exceptions import ServiceUnavailable, DeadlineExceeded, InternalServerError, TooManyRequests
except ImportError:
    # 如果 google-api-core 没有安装或版本不同，提供一个备用方案，避免程序崩溃
    # 注意：在实际生产中，应确保所有依赖都已安装
    class ServiceUnavailable(Exception): pass
    class DeadlineExceeded(Exception): pass
    class InternalServerError(Exception): pass
    class TooManyRequests(Exception): pass


def to_plain_text(markdown_string):
    """将 Markdown 字符串转换为纯文本。"""
    if not markdown_string: return ""
    try:
        html = markdown.markdown(markdown_string)
        soup = BeautifulSoup(html, "html.parser")
        return soup.get_text().strip()
    except Exception:
        # 如果转换失败，返回原始字符串
        return markdown_string

def parse_gemini_reports(raw_text):
    """从 Gemini 返回的原始文本中解析出基于行号的报告。"""
    reports = {}
    # 正则表达式，用于匹配报告头，如 "[REPORT FOR LINE 123]"
    pattern = r'(\[REPORT FOR LINE \d+\])'
    parts = re.split(pattern, raw_text)
    if len(parts) > 1:
        # 从索引1开始，步长为2，来遍历匹配到的报告头和其对应的内容
        for i in range(1, len(parts), 2):
            header = parts[i]
            content = parts[i+1].strip() if (i + 1) < len(parts) else ""
            match = re.search(r'\d+', header)
            if match:
                line_num = match.group(0)
                reports[line_num] = content
    return reports

def retry_on_api_error(max_retries=3, base_delay=5):
    """
    一个装饰器，用于在捕获到指定的Google API错误时进行指数退避重试。
    
    Args:
        max_retries (int): 最大重试次数。
        base_delay (int): 基础延迟秒数。
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # 定义一个元组，包含所有需要捕获并重试的异常类型
            exceptions_to_catch = (ServiceUnavailable, DeadlineExceeded, InternalServerError, TooManyRequests)
            
            for attempt in range(max_retries):
                try:
                    # 尝试执行被装饰的原始函数（例如 process_alignment_request）
                    return func(*args, **kwargs)
                except exceptions_to_catch as e:
                    # 捕获到指定的异常后，记录警告信息
                    logging.warning(f"函数 '{func.__name__}' 遇到可重试的API错误 (尝试次数: {attempt + 1}/{max_retries}): {type(e).__name__} - {e}")
                    if attempt < max_retries - 1:
                        # 如果不是最后一次尝试，则执行“指数退避 + 抖动”策略
                        sleep_time = base_delay * (2 ** attempt) + random.uniform(0, 1)
                        logging.info(f"将在 {sleep_time:.2f} 秒后重试...")
                        time.sleep(sleep_time)
                    else:
                        # 如果是最后一次尝试，记录严重错误并重新抛出异常
                        logging.error(f"函数 '{func.__name__}' 所有重试均告失败。")
                        raise  # 重新抛出最后的异常，让上层代码可以捕获它
        return wrapper
    return decorator