FROM python:3.13-slim

WORKDIR /app

# 安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目
COPY . .

# 根据环境变量启动对应课程实例
ENV COURSE_NAME=python

EXPOSE 8003

CMD ["sh", "-c", "python -m uvicorn backend.main:app --host 0.0.0.0 --port 8003"]