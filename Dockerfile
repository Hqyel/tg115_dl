# 使用轻量级 Python 基础镜像
FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 设置环境变量
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=Asia/Shanghai

# 安装系统依赖（如果不再需要 gcc 等，可以只安装必要的运行时库）
# 这里安装 git 是因为某些 pip 包可能需要从 git 安装，如果不需要可以移除
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# 复制项目依赖文件
COPY requirements.txt .

# 安装 Python 依赖
# 使用清华源加速（可选）
RUN pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt

# 复制项目代码
COPY . .

# 创建数据目录
RUN mkdir -p data && chmod 777 data

# 暴露端口
EXPOSE 5000

# 启动命令
CMD ["python", "run_web.py", "--host", "0.0.0.0", "--port", "5000"]

