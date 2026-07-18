FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# 安装 uv（与本地开发一致的依赖管理，uv.lock 为唯一可信源）
RUN pip install --no-cache-dir uv

# 先复制依赖清单与锁文件，利用 Docker 层缓存
COPY pyproject.toml uv.lock ./

# 从 uv.lock 导出依赖并安装到系统 Python。
# 不再依赖已删除的 packages/ 离线缓存（早期版本用 --no-index --find-links=/packages）。
RUN uv export --frozen --no-dev --no-hashes -o /tmp/requirements-docker.txt \
    && uv pip install --system -r /tmp/requirements-docker.txt \
    && rm -f /tmp/requirements-docker.txt

# 复制全部源码（含 backend/graph、mcp_servers 等）
COPY . .

EXPOSE 8003

CMD ["sh", "-c", "python -m uvicorn backend.main:app --host 0.0.0.0 --port 8003"]
