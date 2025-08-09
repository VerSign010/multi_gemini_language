# app/views/sheets_views.py
from flask import Blueprint

# 这个蓝图目前没有路由，但我们保留文件结构以备未来扩展。
sheets_bp = Blueprint('sheets', __name__)

# get_credentials_from_session 函数已删除。