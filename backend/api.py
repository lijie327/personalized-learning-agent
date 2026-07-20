"""
API 组合根（Composition Root）。

仅负责把各子路由（backend/routers/*）聚合到统一的 /api 前缀下，
并对外暴露 router 与 init_agents；具体端点逻辑已下沉到
backend/routers（端点）、backend/services（业务）、backend/schemas（模型）。
"""

from fastapi import APIRouter

from backend.runtime import init_agents
from backend.routers import (
    tutor,
    exercise,
    code,
    student,
    knowledge,
    session,
    mcp,
    upload,
)

router = APIRouter(prefix="/api")
router.include_router(tutor.router)
router.include_router(exercise.router)
router.include_router(code.router)
router.include_router(student.router)
router.include_router(knowledge.router)
router.include_router(session.router)
router.include_router(mcp.router)
router.include_router(upload.router)

__all__ = ["router", "init_agents"]
