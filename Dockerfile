# Dockerfile

# 1. 选择一个官方的 Python 基础镜像
FROM python:3.12-slim

# 2. 设置工作目录
WORKDIR /app

# 3. 复制依赖清单文件
COPY requirements.txt .

# 4. 安装所有依赖项
#    确保 gevent 也被安装
RUN pip install --no-cache-dir -r requirements.txt

# 5. 复制整个项目代码到工作目录
COPY . .

# 6. 暴露应用运行的端口
#    Render 会自动检测端口，但明确写出是好习惯
EXPOSE 10000

# 7. 定义容器启动时要执行的命令
#    --- 这里是核心修改 ---
#    使用新的、带有超时和 gevent 工作模式的命令
CMD ["gunicorn", "--worker-class", "gevent", "--timeout", "300", "--workers", "1", "--bind", "0.0.0.0:10000", "run:app"]