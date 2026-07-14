"""
应用配置模块
从环境变量和 .env 文件中读取配置项，提供全局配置单例。
"""

import os
from pathlib import Path
from typing import List

from dotenv import load_dotenv

# 加载项目根目录下的 .env 文件
load_dotenv(Path(__file__).resolve().parent.parent / ".env")


# ---------- 阿里云百炼 (DashScope) API ----------
DASHSCOPE_API_KEY: str = os.getenv("DASHSCOPE_API_KEY", "")
DASHSCOPE_BASE_URL: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"

# ---------- 模型配置 ----------
LLM_MODEL: str = os.getenv("LLM_MODEL", "qwen-max")
EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "text-embedding-v2")
VISION_MODEL: str = os.getenv("VISION_MODEL", "qwen-vl-max")

# ---------- 服务配置 ----------
HOST: str = os.getenv("HOST", "0.0.0.0")
PORT: int = int(os.getenv("PORT", "8000"))

# CORS 允许的来源（逗号分隔）。设为 "*" 表示允许全部（此时不携带凭据）。
# 生产环境建议显式指定前端域名，例如 "https://app.example.com,https://admin.example.com"
ALLOWED_ORIGINS: List[str] = [
    o.strip() for o in os.getenv("ALLOWED_ORIGINS", "*").split(",") if o.strip()
]

# ---------- 文件上传 ----------
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_UPLOAD_DIR = str(_PROJECT_ROOT / "uploads")
UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", _DEFAULT_UPLOAD_DIR)
Path(UPLOAD_DIR).mkdir(parents=True, exist_ok=True)

# ---------- Redis 配置 ----------
REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB: int = int(os.getenv("REDIS_DB", "0"))
REDIS_PASSWORD: str = os.getenv("REDIS_PASSWORD", "")
