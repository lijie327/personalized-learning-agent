#!/usr/bin/env python
"""
启动脚本
直接运行此文件启动 Tutor Agent 服务。
"""

import sys
from pathlib import Path

# Windows: 强制 UTF-8 输出，避免 emoji 等字符导致 UnicodeEncodeError
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# 确保项目根目录在路径中
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

if __name__ == "__main__":
    import uvicorn
    from backend.config import HOST, PORT

    print("=" * 50)
    print("🚀 启动 Tutor Agent 教学辅导系统")
    print("=" * 50)
    print(f"   服务地址: http://{HOST}:{PORT}")
    print(f"   API 文档: http://{HOST}:{PORT}/docs")
    print("=" * 50)

    uvicorn.run(
        "backend.main:app",
        host=HOST,
        port=PORT,
        reload=True,
        log_level="info",
    )