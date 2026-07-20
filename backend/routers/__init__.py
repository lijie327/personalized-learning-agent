"""API 子路由集合。

各子路由不携带 /api 前缀，由 backend/api.py 的组合根
（APIRouter(prefix="/api")）统一挂载，最终路径与旧版完全一致。
"""
