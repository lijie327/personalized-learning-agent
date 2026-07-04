"""
多Agent教育系统 —— Agent 模块
导出所有教学Agent和路由Agent，统一入口。
"""

from backend.agents.base_tutor import BaseTutor
from backend.agents.router_agent import RouterAgent
from backend.agents.programming_tutor import ProgrammingTutor
from backend.agents.math_tutor import MathTutor
from backend.agents.knowledge_agent import KnowledgeAgent
from backend.agents.assessor_agent import AssessorAgent

__all__ = [
    # 基础类
    "BaseTutor",
    # 路由
    "RouterAgent",
    # 学科辅导
    "ProgrammingTutor",
    "MathTutor",
    "KnowledgeAgent",
    # 评估
    "AssessorAgent",
]
