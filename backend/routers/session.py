"""会话管理接口。"""

from typing import Optional

from fastapi import APIRouter, HTTPException

import backend.runtime as runtime

router = APIRouter(tags=["session"])


@router.delete("/session/{session_id}")
async def clear_session(session_id: str):
    """
    清除指定会话的短期记忆。
    """
    if runtime.memory is None:
        raise HTTPException(status_code=500, detail="Memory 未初始化")

    runtime.memory.cleanup_session(session_id)

    return {"success": True, "session_id": session_id}


@router.get("/session/{session_id}/history")
async def get_session_history(session_id: str, last_n: int = 20):
    """
    获取会话对话历史。
    """
    if runtime.memory is None:
        raise HTTPException(status_code=500, detail="Memory 未初始化")

    history = runtime.memory.short_term.get_history(session_id, last_n)

    return {
        "session_id": session_id,
        "history": history,
        "count": len(history),
    }
