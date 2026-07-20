"""练习题生成与评估接口。"""

import asyncio
from typing import Dict, Optional

from fastapi import APIRouter

from backend.schemas.requests import ExerciseGenerateRequest, ExerciseEvaluateRequest
from backend.services.mcp_bridge import call_mcp_tool_async
from backend.tools import evaluate_answer, generate_exercise

import backend.runtime as runtime

router = APIRouter(tags=["exercise"])


@router.post("/exercise/generate")
async def exercise_generate(request: ExerciseGenerateRequest):
    """
    生成练习题。

    优先使用 MCP 预设题库，题库未覆盖时回退到 LLM 动态生成。
    """
    # 映射难度格式
    difficulty_map = {"easy": "简单", "medium": "中等", "hard": "困难"}
    mcp_difficulty = difficulty_map.get(request.difficulty, "中等")

    exercises = []

    # 优先尝试 MCP 工具
    for _ in range(request.count):
        mcp_result = await call_mcp_tool_async(
            "generate_exercise",
            topic=request.topic,
            difficulty=mcp_difficulty,
        )
        if mcp_result and "error" not in mcp_result:
            exercises.append(mcp_result)

    # MCP 没有覆盖时，回退到 LLM 动态生成
    if len(exercises) < request.count:
        remaining = request.count - len(exercises)
        local_result = await asyncio.to_thread(
            generate_exercise,
            topic=request.topic,
            difficulty=request.difficulty,
            subject=request.subject,
            count=remaining,
        )
        if "error" not in local_result:
            exercises.extend(local_result.get("exercises", []))

    if not exercises:
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail="练习生成失败，请稍后重试。")

    return {
        "topic": request.topic,
        "difficulty": request.difficulty,
        "exercises": exercises,
        "source": "mcp" if len(exercises) >= request.count else "hybrid",
    }


@router.post("/exercise/evaluate")
async def exercise_evaluate(request: ExerciseEvaluateRequest):
    """
    评估学生答案。

    从正确性、完整性等维度评估，给出得分和改进建议。
    如果提供了 student_id 和 topic，还会更新学生薄弱点记录。
    """
    # 评估涉及 LLM 调用，放到线程池避免阻塞事件循环
    result = await asyncio.to_thread(
        evaluate_answer,
        question=request.question,
        student_answer=request.student_answer,
        correct_answer=request.correct_answer,
    )

    # 更新学生薄弱点记录（如果提供了 student_id 和 topic）
    if runtime.memory and request.student_id and request.topic:
        score = result.get("score", 0) / 100.0  # 转为 0-1 范围
        runtime.memory.update_weak_point(
            student_id=request.student_id,
            topic=request.topic,
            score=score,
            subject=request.subject,
        )

    return result
