# 步骤 1: 选择一个带有 Python 的官方基础镜像（我们的“毛坯房”）
FROM python:3.11-slim

# 步骤 2: 设置工作目录
# 在容器内部创建一个 /app 文件夹，并进入它
WORKDIR /app

# 步骤 3: 安装系统级别的依赖（我们在这里拥有权限！）
# 这就是我们解决问题的关键所在
RUN apt-get update && apt-get install -y gfortran && rm -rf /var/lib/apt/lists/*

# 步骤 4: 复制并安装 Python 依赖
# 先只复制 requirements.txt 文件，这样可以利用 Docker 的缓存机制，加快后续构建速度
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 步骤 5: 复制您项目的所有代码到容器中
COPY . .

# 步骤 6: 声明应用运行的命令
# 这会替代 Procfile 和 Render 上的 "Start Command"
# 注意：Render 会忽略端口设置，自动处理端口映射
CMD ["gunicorn", "app:create_app()"]