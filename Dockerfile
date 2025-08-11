# Dockerfile

# 1. 选择一个官方的 Python 基础镜像
FROM python:3.12-slim

# 2. 设置工作目录
WORKDIR /app

# 3. 复制依赖清单文件
COPY requirements.txt .

# 4. 安装所有依赖项
RUN pip install --no-cache-dir -r requirements.txt

# 5. 复制整个项目代码到工作目录
COPY . .

# 6. 暴露 Render 期望的端口
#    Render 会自动将 PORT 环境变量设置为 10000
EXPOSE 10000

# 7. 定义容器启动时要执行的命令
#    --- 这里是核心修改 ---
#    让 Gunicorn 从 Render 提供的 $PORT 环境变量中读取端口
CMD ["gunicorn", "--worker-class", "gevent", "--timeout", "300", "--workers", "1", "--bind", "0.0.0.0:$PORT", "run:app"]