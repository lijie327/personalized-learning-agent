"""
数据模型定义
包含请求/响应模型、Agent 类型枚举和学习者画像。
"""

from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class AgentType(str, Enum):
    """Agent 类型枚举，用于路由和标识不同的教学 Agent。"""

    ROUTER = "router"
    MATH = "math"
    PROGRAMMING = "programming"
    KNOWLEDGE = "knowledge"
    ASSESSOR = "assessor"


class StudentRequest(BaseModel):
    """学生提问请求模型。"""

    question: str = Field(..., description="学生提出的问题")
    session_id: str = Field(..., description="会话唯一标识")
    student_id: str = Field(..., description="学生唯一标识")
    subject: Optional[str] = Field(None, description="科目（如 math / programming / physics）")


class TutorResponse(BaseModel):
    """辅导系统响应模型。"""

    reply: str = Field(..., description="给学生的回复内容")
    agent_used: AgentType = Field(..., description="处理该请求所使用的 Agent")
    socratic_guided: bool = Field(
        default=False,
        description="是否采用了苏格拉底式引导（启发提问而非直接给答案）",
    )
    exercises: List[str] = Field(
        default_factory=list,
        description="推荐的练习题列表",
    )


class LearningProfile(BaseModel):
    """学习者画像，用于追踪学生的薄弱环节和知识图谱。"""

    student_id: str = Field(..., description="学生唯一标识")
    weak_points: List[str] = Field(
        default_factory=list,
        description="学生的薄弱知识点列表",
    )
    knowledge_graph: dict = Field(
        default_factory=dict,
        description="学生知识图谱（节点为知识点，边为掌握程度）",
    )
