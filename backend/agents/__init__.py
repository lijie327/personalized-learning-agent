"""
多Agent教育系统 —— Agent 模块
导出路由 Agent，统一入口。

说明：原 math/programming/knowledge/assessor 四个旧 Agent 类（及 BaseTutor）
已被 LangGraph supervisor 架构淘汰，其系统提示词已迁移至 backend/graph/agents.py
的 standalone 函数；知识检索由 backend/graph/tools.rag_search 与 /knowledge/search
端点直接基于 EducationKnowledgeBase 实现，不再依赖旧 Agent 实现。
"""

from backend.agents.router_agent import RouterAgent

__all__ = [
    "RouterAgent",
]
