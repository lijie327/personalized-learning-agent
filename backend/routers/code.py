"""在线代码执行接口（沙箱隔离）。"""

import asyncio
import time
from typing import Dict, Any

from fastapi import APIRouter

from backend.schemas.requests import ExecuteCodeRequest
from backend.tools import execute_python

router = APIRouter(tags=["code"])


@router.post("/execute-code")
async def execute_code(request: ExecuteCodeRequest) -> Dict[str, Any]:
    """
    在线执行 Python 代码（沙箱隔离）。

    接收前端代码块点击"运行"的请求，在安全沙箱中执行并返回结果。
    """
    # 只支持 Python
    if request.language.lower() not in ("python", "py"):
        return {
            "success": False,
            "output": "",
            "error": f"暂不支持 {request.language} 语言的在线执行，仅支持 Python。",
            "execution_time": 0,
        }

    start = time.time()
    # 子进程执行会阻塞，放到线程池避免阻塞事件循环
    result = await asyncio.to_thread(
        execute_python,
        code=request.code,
        timeout=request.timeout,
    )
    elapsed_ms = round((time.time() - start) * 1000)

    return {
        **result,
        "execution_time": elapsed_ms,
    }
