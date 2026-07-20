"""Pydantic 请求模型（API 入参）。"""

from typing import Optional

from pydantic import BaseModel, Field


class TutorStreamRequest(BaseModel):
    """辅导请求（SSE 流式）"""

    question: str = Field(..., description="学生提问内容")
    session_id: str = Field(..., description="会话 ID")
    student_id: str = Field(..., description="学生 ID")
    subject: Optional[str] = Field(None, description="科目（可选）")
    mode: str = Field(default="direct", description="教学模式：socratic / direct")
    code: Optional[str] = Field(None, description="学生代码（编程题可选）")


class ExerciseGenerateRequest(BaseModel):
    """练习题生成请求"""

    topic: str = Field(..., description="知识点")
    difficulty: str = Field(default="medium", description="难度：easy / medium / hard")
    subject: str = Field(default="python", description="科目")
    count: int = Field(default=3, ge=1, le=10, description="题目数量")


class ExerciseEvaluateRequest(BaseModel):
    """答案评估请求"""

    question: str = Field(..., description="题目内容")
    student_answer: str = Field(..., description="学生答案")
    correct_answer: str = Field(..., description="标准答案")
    student_id: Optional[str] = Field(None, description="学生ID（可选，用于更新薄弱点）")
    topic: Optional[str] = Field(None, description="知识点（可选）")
    subject: str = Field(default="general", description="科目（用于归类薄弱点，默认 general）")


class StudyPlanRequest(BaseModel):
    """学习计划请求"""

    student_id: str = Field(..., description="学生 ID")
    target_subject: Optional[str] = Field(None, description="目标科目")


class ExecuteCodeRequest(BaseModel):
    """代码执行请求"""

    code: str = Field(..., description="待执行的 Python 代码")
    language: str = Field(default="python", description="编程语言")
    timeout: int = Field(default=30, ge=1, le=60, description="执行超时时间（秒）")
