"""SSE 流式辅导接口。"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from backend.schemas.requests import TutorStreamRequest
from backend.services import streaming

import backend.runtime as runtime

router = APIRouter(tags=["tutor"])


@router.post("/tutor")
async def tutor_stream(request: TutorStreamRequest):
    """
    SSE 流式辅导接口。

    接收学生请求，通过 Router 分类后调度对应 Tutor Agent，
    流式返回辅导回复（苏格拉底引导或直接讲解）。

    SSE 消息格式：
    - route: 路由信息（agent / subject / confidence）
    - token: 流式文本片段
    - done: 完成信号（含练习题推荐 / 薄弱点）
    - error: 错误信号
    """
    if runtime.router_agent is None:
        raise HTTPException(status_code=500, detail="Agent 未初始化")

    return StreamingResponse(
        streaming.stream_llm_response(
            question=request.question,
            student_id=request.student_id,
            session_id=request.session_id,
            mode=request.mode,
            code=request.code,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # 禁用 nginx 缓冲
        },
    )
