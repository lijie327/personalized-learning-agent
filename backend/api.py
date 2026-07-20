"""
API 路由层
提供 SSE 流式辅导、练习题生成/评估、学生画像等 RESTful 接口。
"""

import json
import asyncio
import uuid
import os
from datetime import datetime
from pathlib import Path
from typing import AsyncGenerator, Dict, List, Optional, Any

from fastapi import APIRouter, HTTPException, Request, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from backend.config import UPLOAD_DIR

from backend.models import StudentRequest, AgentType
from backend.agents.router_agent import RouterAgent
from backend.memory import LearningMemory
from backend.rag import EducationKnowledgeBase
from backend.tools import generate_exercise, evaluate_answer, execute_python, check_syntax
from backend.llm import QwenLLM, QwenVisionLLM


# ===================================================================
#  全局实例（在 main.py 中通过 lifespan 初始化）
# ===================================================================

# 声明全局变量，实际实例由 main.py 的 lifespan 赋值
router_agent: RouterAgent = None
memory: LearningMemory = None
knowledge_base: EducationKnowledgeBase = None
mcp_tools: List = []  # MCP 工具列表


def init_agents(
    router: RouterAgent,
    mem: LearningMemory,
    kb: EducationKnowledgeBase,
    mcp_tool_list: Optional[List] = None,
):
    """
    初始化全局实例（由 main.py 调用）。
    router_agent 用于问题分类；memory / knowledge_base / mcp_tools 供各 API 端点使用。
    specialist Agent 已由 LangGraph 编译图内部按需构建，无需在此独立实例化。
    """
    global router_agent, memory, knowledge_base, mcp_tools

    router_agent = router
    memory = mem
    knowledge_base = kb
    mcp_tools = mcp_tool_list or []


# ===================================================================
#  Pydantic 请求/响应模型
# ===================================================================


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


# ===================================================================
#  SSE 流式响应工具函数
# ===================================================================


def sse_format(data: Dict[str, Any]) -> str:
    """
    格式化 SSE 消息。

    SSE 格式要求：`data: {json}\n\n`
    """
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


def _build_mcp_tool_context() -> str:
    """构建 MCP 工具描述文本，供 LLM prompt 使用。"""
    if not mcp_tools:
        return ""
    lines = ["\n## 可用的 MCP 工具\n"]
    for tool in mcp_tools:
        name = getattr(tool, "name", str(tool))
        desc = (getattr(tool, "description", "") or "无描述")[:100]
        lines.append(f"- **{name}**: {desc}")
    return "\n".join(lines) + "\n"


def _build_student_context(profile: Dict[str, Any]) -> str:
    """
    从学生画像构建上下文文本，注入到 LLM prompt 中。

    包含薄弱点、已掌握知识点和知识图谱统计，
    帮助 LLM 了解学生状况并个性化教学。
    """
    parts = []

    weak_detail = profile.get("weak_points_detail", [])
    if weak_detail:
        lines = ["\n## 该学生的学习薄弱点（需要重点帮助）"]
        for wp in weak_detail[:5]:
            lines.append(
                f"- {wp['topic']}（{wp.get('subject', '')}），"
                f"掌握程度 {wp['score']:.0%}，已尝试 {wp.get('attempts', 0)} 次"
            )
        parts.append("\n".join(lines))

    strong_detail = profile.get("strengths_detail", [])
    if strong_detail:
        lines = ["\n## 该学生已掌握的知识点（可跳过基础讲解）"]
        for s in strong_detail[:5]:
            lines.append(
                f"- {s['topic']}（{s.get('subject', '')}），"
                f"掌握程度 {s['score']:.0%}"
            )
        parts.append("\n".join(lines))

    kg = profile.get("knowledge_graph", {})
    stats = kg.get("statistics", {})
    if stats and stats.get("total_nodes", 0) > 0:
        lines = ["\n## 知识图谱统计"]
        lines.append(f"- 总知识点数: {stats.get('total_nodes', 0)}")
        lines.append(f"- 平均掌握度: {stats.get('avg_mastery', 0):.0%}")
        lines.append(f"- 已掌握（≥80%）: {stats.get('mastered', 0)} 个")
        lines.append(f"- 需加强（<60%）: {stats.get('needs_work', 0)} 个")
        parts.append("\n".join(lines))

    return "\n".join(parts) + "\n" if parts else ""


# ===================================================================
#  意图识别：检测学生的对话意图类型
# ===================================================================

# 问候语
_GREETING_KEYWORDS = [
    "你好", "嗨", "hello", "hi", "在吗", "早上好", "下午好", "晚上好",
    "老师好", "哈喽", "hey",
]

# 询问自己的名字/身份（优先级高于自我介绍）
_NAME_QUERY_KEYWORDS = [
    "我叫什么", "我叫啥", "我的名字是什么", "我的名字叫啥",
    "我是谁", "还记得我吗", "你知道我是谁", "知道我叫什么",
    "我的名字是啥", "我名字是什么", "我名字叫啥",
    "你记得我吗", "你认识我吗", "知道我是谁吗",
    "猜猜我是谁",
]

# 自我介绍（提供名字）
_SELF_INTRO_KEYWORDS = [
    "我叫", "我是", "我的名字", "我姓", "我叫作",
]

# 对话历史引用
_HISTORY_REF_KEYWORDS = [
    "上面讲了", "刚才说了", "之前讲了", "你刚才", "你之前",
    "还记得吗", "回顾一下", "再说一遍", "重复一遍", "复习一下",
    "之前那个", "上一次", "上次那个", "刚刚那个",
]

# 自我查询关键词：学生询问自己的学习状况
_SELF_QUERY_KEYWORDS = [
    "我的薄弱", "我的弱项", "我哪里不好", "我不会", "我不懂",
    "我的学习", "我的掌握", "我的进度", "我还需要", "我哪些",
    "我薄弱", "我不太会", "我搞不懂", "我不理解", "还有什么薄弱",
    "薄弱点", "弱点", "弱项", "学习情况", "学习状况",
    "已掌握", "强项", "我的强项", "我擅长", "我学会",
    "知识图谱", "学习统计", "我的水平",
]

# 已知教学科目（模块级别常量，避免每次函数调用时重复创建）
_KNOWN_SUBJECTS = (
    "python", "programming", "编程", "math", "数学",
    "data_structures", "数据结构", "assessment", "评估",
    "general",  # 通用但可能是教学相关，继续走教学流程
)

# 意图类型
from enum import Enum

class _IntentType(Enum):
    NAME_QUERY = "name_query"       # 询问自己的名字/身份
    SELF_INTRO = "self_intro"       # 自我介绍（提供了名字）
    HISTORY_REF = "history_ref"      # 引用对话历史
    SELF_QUERY = "self_query"        # 询问学习状况
    GREETING = "greeting"            # 打招呼
    NORMAL = "normal"                # 普通学习问题


def _detect_intent(question: str) -> _IntentType:
    """
    检测学生问题的意图类型。

    按优先级从高到低检测：
    1. 询问名字（"我叫什么" / "我的名字是什么"）
    2. 对话历史引用（"上面讲了什么"）
    3. 自我介绍（"我叫张三"）—— 注意：必须在名字询问之后检测
    4. 自我查询（"我的薄弱点"）
    5. 问候（"你好"）
    6. 普通问题
    """
    # 优先级最高：询问自己的名字（必须在自我介绍之前，因为"我叫什么"也包含"我叫"）
    if any(kw in question for kw in _NAME_QUERY_KEYWORDS):
        return _IntentType.NAME_QUERY

    # 对话历史引用
    if any(kw in question for kw in _HISTORY_REF_KEYWORDS):
        return _IntentType.HISTORY_REF

    # 自我介绍：匹配关键词且能提取到有效姓名
    if any(kw in question for kw in _SELF_INTRO_KEYWORDS):
        name = _extract_name_from_intro(question)
        if name:
            return _IntentType.SELF_INTRO
        # 有关键词但提取不到名字（如"我是谁"），归为名字询问
        return _IntentType.NAME_QUERY

    # 自我查询
    if any(kw in question for kw in _SELF_QUERY_KEYWORDS):
        return _IntentType.SELF_QUERY

    # 问候
    stripped = question.strip().lower()
    if any(kw in stripped for kw in _GREETING_KEYWORDS):
        return _IntentType.GREETING

    return _IntentType.NORMAL


def _extract_name_from_intro(question: str) -> Optional[str]:
    """从自我介绍中提取学生姓名（支持中文和英文名）。"""
    import re
    patterns = [
        r"我叫\s*([一-龥]{2,4})",
        r"我是\s*([一-龥]{2,4})",
        r"我的名字\s*(?:是|叫)?\s*([一-龥]{2,4})",
        r"我姓\s*([一-龥]{1,2})",
        # 英文名支持
        r"我叫\s*([A-Za-z]{2,20})",
        r"我是\s*([A-Za-z]{2,20})",
        r"我的名字\s*(?:是|叫)?\s*([A-Za-z]{2,20})",
        r"[Mm]y\s+name\s+is\s+([A-Za-z]{2,20})",
        r"[Ii]'?[Mm]\s+([A-Za-z]{2,20})",
    ]
    for pat in patterns:
        m = re.search(pat, question)
        if m:
            return m.group(1)
    return None


def _build_greeting_response() -> str:
    """生成问候回复（不走 LLM，即时响应）。"""
    return (
        "👋 你好！我是你的 AI 辅导老师，很高兴见到你！\n\n"
        "我可以帮你：\n"
        "- 📖 讲解 Python 编程知识（函数、变量、类、异常处理等）\n"
        "- 📖 讲解数据结构（数组、链表、栈、队列、树等）\n"
        "- 📝 出练习题并评估你的答案\n"
        "- 📊 分析你的学习薄弱点\n\n"
        "直接问我问题就可以开始学习啦！比如：「讲讲 Python 的函数」"
    )


def _build_self_intro_response(name: str) -> str:
    """生成自我介绍确认回复。"""
    return f"你好 **{name}**！我已经记住你的名字了。\n\n有什么想学习的吗？可以直接问我问题哦！"


def _build_history_ref_response(context: Optional[str]) -> str:
    """
    根据会话上下文生成回顾回复。

    如果无上下文，提示学生当前没有对话历史。
    """
    if not context:
        return (
            "🤔 目前我们还没有聊过什么呢，这是一个新的对话。\n\n"
            "你想学习什么内容？直接告诉我吧！"
        )
    return (
        f"📝 **我们刚才聊了这些内容：**\n\n{context}\n\n"
        "有什么不清楚的地方吗？可以继续问我！"
    )


def _build_name_query_response(student_name: str) -> str:
    """
    根据记忆中存储的学生姓名生成回复。

    如果系统记得学生名字，直接告知；否则提示学生自我介绍。
    """
    if student_name:
        return (
            f"你之前告诉我你叫 **{student_name}**，我一直记得呢！😊\n\n"
            "有什么想学习的吗？"
        )
    else:
        return (
            "我好像还不知道你的名字呢 🤔\n\n"
            "你可以告诉我，比如：「我叫张三」"
        )


def _build_self_query_response(profile: Dict[str, Any]) -> str:
    """
    根据学生记忆数据直接生成自我查询回复。

    不走 LLM，直接用存储的学生画像数据构建回答，
    确保薄弱点等信息准确、全面。
    """
    weak_detail = profile.get("weak_points_detail", [])
    strong_detail = profile.get("strengths_detail", [])
    kg = profile.get("knowledge_graph", {})
    stats = kg.get("statistics", {})

    parts = ["📊 **你的学习状况总结**\n"]

    # 薄弱点
    if weak_detail:
        parts.append("## ⚠️ 需要加强的知识点\n")
        for i, wp in enumerate(weak_detail, 1):
            score_pct = wp['score'] * 100
            attempts = wp.get('attempts', 0)
            subject = wp.get('subject', '')
            emoji = "🔴" if wp['score'] < 0.4 else "🟡"
            parts.append(
                f"{i}. {emoji} **{wp['topic']}**（{subject}）— "
                f"掌握度 {score_pct:.0f}%，已练习 {attempts} 次"
            )
        parts.append("")
    else:
        parts.append("## ⚠️ 需要加强的知识点\n\n暂无记录，继续学习吧！\n")

    # 强项
    if strong_detail:
        parts.append("## ✅ 已掌握的知识点\n")
        for i, s in enumerate(strong_detail, 1):
            score_pct = s['score'] * 100
            subject = s.get('subject', '')
            parts.append(f"{i}. 🟢 **{s['topic']}**（{subject}）— 掌握度 {score_pct:.0f}%")
        parts.append("")

    # 知识图谱统计
    if stats and stats.get("total_nodes", 0) > 0:
        parts.append("## 📈 学习统计\n")
        parts.append(f"- 总知识点数: **{stats.get('total_nodes', 0)}** 个")
        parts.append(f"- 平均掌握度: **{stats.get('avg_mastery', 0) * 100:.0f}%**")
        parts.append(f"- 已掌握（≥80%）: **{stats.get('mastered', 0)}** 个")
        parts.append(f"- 需加强（<60%）: **{stats.get('needs_work', 0)}** 个")
        parts.append("")

    # 建议
    if weak_detail:
        parts.append("## 💡 学习建议\n")
        top_weak = weak_detail[0]['topic']
        parts.append(
            f"建议优先攻克 **{top_weak}**，这是你目前最薄弱的知识点。"
            f"可以直接问我：「请讲解 {top_weak}」开始学习！"
        )

    return "\n".join(parts)


async def _call_mcp_tool_async(tool_name: str, **kwargs) -> Optional[Dict[str, Any]]:
    """
    异步调用指定 MCP 工具并返回结果。

    Args:
        tool_name: MCP 工具名称。
        **kwargs: 传递给工具的参数。

    Returns:
        工具返回结果字典，工具不存在或调用失败返回 None。
    """
    for tool in mcp_tools:
        if getattr(tool, "name", "") == tool_name:
            try:
                if hasattr(tool, "ainvoke"):
                    return await tool.ainvoke(kwargs)
                elif hasattr(tool, "invoke"):
                    return tool.invoke(kwargs)
                else:
                    return tool(**kwargs)
            except Exception as e:
                print(f"   ⚠️ MCP 工具 '{tool_name}' 调用失败: {e}")
                return {"error": str(e)}
    return None


def _call_mcp_tool_sync(tool_name: str, **kwargs) -> Optional[Dict[str, Any]]:
    """
    同步调用指定 MCP 工具并返回结果（用于非 async 上下文）。

    Args:
        tool_name: MCP 工具名称。
        **kwargs: 传递给工具的参数。

    Returns:
        工具返回结果字典，工具不存在或调用失败返回 None。
    """
    for tool in mcp_tools:
        if getattr(tool, "name", "") == tool_name:
            try:
                if hasattr(tool, "ainvoke"):
                    import asyncio
                    return asyncio.run(tool.ainvoke(kwargs))
                elif hasattr(tool, "invoke"):
                    return tool.invoke(kwargs)
                else:
                    return tool(**kwargs)
            except Exception as e:
                print(f"   ⚠️ MCP 工具 '{tool_name}' 调用失败: {e}")
                return {"error": str(e)}
    return None


async def stream_llm_response(
    question: str,
    student_id: str,
    session_id: str,
    mode: str = "direct",
    code: Optional[str] = None,
) -> AsyncGenerator[str, None]:
    """
    SSE 流式生成辅导回复。

    流程：
    1. 获取学生画像（薄弱点）
    2. Router 分类路由
    3. 调度对应 Tutor Agent
    4. 构建对话上下文
    5. 构建 MCP 工具上下文
    6. 根据模式（苏格拉底/直接）生成回复
    7. 流式返回 token
    8. 结束时返回练习题推荐和薄弱点更新
    """
    # 1. 获取学生画像
    profile = memory.get_student_profile(student_id, session_id)
    weak_points = profile.get("weak_points", [])
    student_context = _build_student_context(profile)

    # 1.5 构建对话历史（供意图处理和 Router/LLM 使用）
    raw_history = memory.short_term.get_history(session_id, last_n=10)
    chat_history = [{"role": m["role"], "content": m["content"]} for m in raw_history]

    # 2. 意图识别：根据学生意图选择最合适的处理方式
    intent = _detect_intent(question)
    session_context = memory.short_term.get_context(session_id, last_n=10)
    print(f"\n[Intent] question='{question}' | intent={intent.value} | weak_points={weak_points}")

    # --- 处理名字询问 ---
    if intent == _IntentType.NAME_QUERY:
        stored_name = profile.get("name", "")
        name_response = _build_name_query_response(stored_name)
        yield sse_format({
            "type": "route", "agent": "memory", "subject": "name_query",
            "confidence": 1.0, "reasoning": "学生询问自己的名字，从记忆数据查找",
            "weak_points": weak_points,
        })
        for char in name_response:
            yield sse_format({"type": "token", "token": char, "agent": "memory", "mode": "direct"})
            await asyncio.sleep(0.005)
        memory.add_session_message(session_id, {"role": "user", "content": question, "timestamp": datetime.now().isoformat()})
        memory.add_session_message(session_id, {"role": "assistant", "content": name_response, "agent": "memory", "timestamp": datetime.now().isoformat()})
        yield sse_format({
            "type": "done", "done": True, "exercises": [],
            "weak_points": weak_points, "agent": "memory",
            "suggested_topics": [],
        })
        return

    # --- 处理自我介绍 ---
    if intent == _IntentType.SELF_INTRO:
        student_name = _extract_name_from_intro(question)
        if student_name:
            # 更新学生的名字到中期记忆中
            memory.set_metadata(student_id, "name", student_name)
            intro_response = _build_self_intro_response(student_name)
        else:
            intro_response = "你好！请问你的名字是什么？"
        yield sse_format({
            "type": "route", "agent": "memory", "subject": "self_intro",
            "confidence": 1.0, "reasoning": "学生自我介绍，更新档案",
            "weak_points": weak_points,
        })
        for char in intro_response:
            yield sse_format({"type": "token", "token": char, "agent": "memory", "mode": "direct"})
            await asyncio.sleep(0.005)
        memory.add_session_message(session_id, {"role": "user", "content": question, "timestamp": datetime.now().isoformat()})
        memory.add_session_message(session_id, {"role": "assistant", "content": intro_response, "agent": "memory", "timestamp": datetime.now().isoformat()})
        yield sse_format({
            "type": "done", "done": True, "exercises": [],
            "weak_points": weak_points, "agent": "memory",
            "suggested_topics": [wp["topic"] for wp in profile.get("weak_points_detail", [])[:3]],
        })
        return

    # --- 处理问候 ---
    if intent == _IntentType.GREETING:
        greeting_response = _build_greeting_response()
        yield sse_format({
            "type": "route", "agent": "memory", "subject": "greeting",
            "confidence": 1.0, "reasoning": "学生打招呼，友好回应",
            "weak_points": weak_points,
        })
        for char in greeting_response:
            yield sse_format({"type": "token", "token": char, "agent": "memory", "mode": "direct"})
            await asyncio.sleep(0.005)
        memory.add_session_message(session_id, {"role": "user", "content": question, "timestamp": datetime.now().isoformat()})
        memory.add_session_message(session_id, {"role": "assistant", "content": greeting_response, "agent": "memory", "timestamp": datetime.now().isoformat()})
        yield sse_format({
            "type": "done", "done": True, "exercises": [],
            "weak_points": weak_points, "agent": "memory",
            "suggested_topics": [],
        })
        return

    # --- 处理对话历史引用 ---
    if intent == _IntentType.HISTORY_REF:
        history_response = _build_history_ref_response(session_context)
        yield sse_format({
            "type": "route", "agent": "memory", "subject": "history_ref",
            "confidence": 1.0, "reasoning": "学生询问之前讨论过的内容，直接展示会话历史",
            "weak_points": weak_points,
        })
        for char in history_response:
            yield sse_format({"type": "token", "token": char, "agent": "memory", "mode": "direct"})
            await asyncio.sleep(0.005)
        memory.add_session_message(session_id, {"role": "user", "content": question, "timestamp": datetime.now().isoformat()})
        memory.add_session_message(session_id, {"role": "assistant", "content": history_response, "agent": "memory", "timestamp": datetime.now().isoformat()})
        yield sse_format({
            "type": "done", "done": True, "exercises": [],
            "weak_points": weak_points, "agent": "memory",
            "suggested_topics": [],
        })
        return

    # --- 处理自我查询（薄弱点等） ---
    if intent == _IntentType.SELF_QUERY:
        self_response = _build_self_query_response(profile)
        yield sse_format({
            "type": "route",
            "agent": "memory",
            "subject": "self_query",
            "confidence": 1.0,
            "reasoning": "学生询问自身学习状况，直接使用记忆数据",
            "weak_points": weak_points,
        })
        # 流式输出记忆数据（按段落拆分模拟 token 流）
        for char in self_response:
            yield sse_format({
                "type": "token",
                "token": char,
                "agent": "memory",
                "mode": "direct",
            })
            await asyncio.sleep(0.005)
        # 记录对话
        memory.add_session_message(session_id, {
            "role": "user", "content": question, "timestamp": datetime.now().isoformat(),
        })
        memory.add_session_message(session_id, {
            "role": "assistant", "content": self_response, "agent": "memory",
            "timestamp": datetime.now().isoformat(),
        })
        yield sse_format({
            "type": "done", "done": True, "exercises": [],
            "weak_points": weak_points, "agent": "memory",
            "suggested_topics": [wp["topic"] for wp in profile.get("weak_points_detail", [])[:3]],
        })
        return

    # --- 普通问题：走 Router → Tutor Agent 流程 ---

    # 2. Router 分类（传入对话历史上下文，帮助理解模糊问题如"举个例子"）
    classification = await router_agent.aclassify(question, profile, chat_history)
    routed_agent_type = classification.get("agent_type", AgentType.KNOWLEDGE)
    subject = classification.get("subject", "general")
    reasoning = classification.get("reasoning", "")
    confidence = classification.get("confidence", 0.5)

    # 发送路由信息
    yield sse_format({
        "type": "route",
        "agent": routed_agent_type.value,
        "subject": subject,
        "confidence": confidence,
        "reasoning": reasoning,
        "weak_points": weak_points,
    })

    # 2.5 判断是否与教学内容相关：subject 不匹配已知科目时，直接调用 LLM 自由回答
    subject_lower = subject.lower()
    is_known_subject = any(s in subject_lower for s in _KNOWN_SUBJECTS)
    is_code_related = (
        routed_agent_type == AgentType.PROGRAMMING
        or any(kw in question.lower() for kw in [
            "代码", "编程", "函数", "写一个", "实现", "算法", "python",
            "def ", "class ", "import", "怎么写",
        ])
    )

    if not is_known_subject and not is_code_related:
        # subject 不匹配已知教学科目，直接调用大模型自由回答
        llm = QwenLLM()
        off_topic_prompt = f"""{question}
{student_context}"""
        system_prompt = "你是一个智能助手。请直接、自然地回答用户的问题。用中文回答。"
        full_response = ""
        try:
            async for token in llm.astream_with_history(off_topic_prompt, system_prompt=system_prompt, history=chat_history):
                full_response += token
                yield sse_format({
                    "type": "token", "token": token,
                    "agent": "general", "mode": "chat",
                })
        except Exception as e:
            yield sse_format({"type": "error", "error": str(e)})
            return

        memory.add_session_message(session_id, {"role": "user", "content": question, "timestamp": datetime.now().isoformat()})
        memory.add_session_message(session_id, {"role": "assistant", "content": full_response, "agent": "general", "timestamp": datetime.now().isoformat()})
        yield sse_format({
            "type": "done", "done": True, "exercises": [],
            "weak_points": weak_points, "agent": "general",
            "suggested_topics": [],
        })
        return

    # 3. 路由到 LangGraph supervisor 多 Agent 图，由其调度 specialist 子图并流式返回
    async for sse in _stream_via_graph(
        question=question,
        student_id=student_id,
        session_id=session_id,
        mode=mode,
        code=code,
        profile=profile,
        chat_history=chat_history,
        classification=classification,
        weak_points=weak_points,
    ):
        yield sse
    return


# ---------------------------------------------------------------------------
#  LangGraph 流式封装：把编译图的事件映射为 SSE
# ---------------------------------------------------------------------------

async def _stream_via_graph(
    question: str,
    student_id: str,
    session_id: str,
    mode: str,
    code: Optional[str],
    profile: Dict[str, Any],
    chat_history: List[Dict[str, Any]],
    classification: Dict[str, Any],
    weak_points: List[str],
) -> AsyncGenerator[str, None]:
    """
    驱动编译好的 LangGraph 多 Agent 图，并把事件翻译为 SSE 消息。

    - on_chat_model_stream → token 事件（逐字流式）
    - on_tool_end（rag_search）→ sources 事件（前端可展示来源）
    - generate_exercises 节点结束 → 捕获推荐练习题，用于 done 事件
    """
    from backend.graph.builder import get_compiled_graph

    graph = get_compiled_graph()

    agent_type = classification.get("agent_type", "knowledge")
    agent_type = agent_type.value if hasattr(agent_type, "value") else agent_type

    student_context = _build_student_context(profile)
    user_msg = f"{student_context}\n\n学生问题：{question}"
    if code:
        user_msg += f"\n\n学生提交的代码：\n```python\n{code}\n```"

    initial_state = {
        "question": question,
        "student_id": student_id,
        "session_id": session_id,
        "mode": mode,
        "code": code,
        "intent": "NORMAL",
        "profile": profile,
        "chat_history": chat_history,
        "classification": classification,
        "weak_points": weak_points,
        "rag_sources": [],
        "rag_context": "",
        "response": "",
        "exercises": [],
        "messages": [{"role": "user", "content": user_msg}],
    }

    exercises: List[Dict[str, Any]] = []
    try:
        async for event in graph.astream_events(initial_state, version="v2"):
            ev = event.get("event", "")
            if ev == "on_chat_model_stream":
                chunk = event["data"]["chunk"]
                token = chunk.content if isinstance(chunk.content, str) else ""
                if token:
                    yield sse_format({
                        "type": "token",
                        "token": token,
                        "agent": agent_type,
                        "mode": mode,
                    })
            elif ev == "on_tool_end" and event.get("name") == "rag_search":
                try:
                    sources = json.loads(event["data"]["output"])
                except Exception:
                    sources = []
                yield sse_format({
                    "type": "sources",
                    "sources": sources,
                    "agent": agent_type,
                })
            elif ev == "on_chain_end" and event.get("name") == "generate_exercises":
                exercises = event["data"]["output"].get("exercises", [])
    except Exception as e:
        yield sse_format({"type": "error", "error": str(e)})
        return

    yield sse_format({
        "type": "done",
        "done": True,
        "exercises": exercises,
        "weak_points": weak_points,
        "agent": agent_type,
        "suggested_topics": classification.get("suggested_tools", []),
    })


# ===================================================================
#  API Router 定义
# ===================================================================

router = APIRouter(prefix="/api", tags=["tutor"])


# ------------------------------------------------------------------
#  SSE 流式辅导接口
# ------------------------------------------------------------------


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
    if router_agent is None:
        raise HTTPException(status_code=500, detail="Agent 未初始化")

    return StreamingResponse(
        stream_llm_response(
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


# ------------------------------------------------------------------
#  练习题接口
# ------------------------------------------------------------------


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
        mcp_result = await _call_mcp_tool_async(
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
    if memory and request.student_id and request.topic:
        score = result.get("score", 0) / 100.0  # 转为 0-1 范围
        memory.update_weak_point(
            student_id=request.student_id,
            topic=request.topic,
            score=score,
            subject=request.subject,
        )

    return result


# ------------------------------------------------------------------
#  代码执行接口
# ------------------------------------------------------------------


@router.post("/execute-code")
async def execute_code(request: ExecuteCodeRequest):
    """
    在线执行 Python 代码（沙箱隔离）。

    接收前端代码块点击"运行"的请求，在安全沙箱中执行并返回结果。
    """
    import time

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


# ------------------------------------------------------------------
#  学生画像接口
# ------------------------------------------------------------------


@router.get("/student/{student_id}/profile")
async def get_student_profile(student_id: str, session_id: Optional[str] = None):
    """
    获取学生完整画像。

    整合三层记忆：
    - 短期：当前会话上下文
    - 中期：跨学科薄弱点追踪
    - 长期：知识图谱概览
    """
    if memory is None:
        raise HTTPException(status_code=500, detail="Memory 未初始化")

    profile = memory.get_student_profile(student_id, session_id)

    # 添加格式化统计
    profile["summary"] = {
        "total_weak_points": len(profile.get("weak_points", [])),
        "total_strengths": len(profile.get("strengths", [])),
        "subjects_covered": profile.get("knowledge_graph", {}).get("statistics", {}).get("subjects", []),
        "avg_mastery": profile.get("knowledge_graph", {}).get("statistics", {}).get("avg_mastery", 0),
    }

    return profile


@router.get("/student/{student_id}/study-plan")
async def get_study_plan(student_id: str, target_subject: Optional[str] = None):
    """
    获取个性化学习计划。

    根据学生薄弱点和知识图谱，生成针对性的学习建议。
    """
    if memory is None:
        raise HTTPException(status_code=500, detail="Memory 未初始化")

    profile = memory.get_student_profile(student_id)
    weak_points = profile.get("weak_points_detail", [])
    strengths = profile.get("strengths_detail", [])
    knowledge_graph = profile.get("knowledge_graph", {})

    # 构建学习计划
    plan = {
        "student_id": student_id,
        "generated_at": datetime.now().isoformat(),
        "priority_topics": [],
        "review_topics": [],
        "new_topics": [],
        "daily_schedule": [],
        "estimated_duration": "2-3 周",
    }

    # 优先攻克薄弱点
    for wp in weak_points[:5]:  # 最多 5 个优先项
        topic = wp.get("topic", "")
        score = wp.get("score", 0)
        subject = wp.get("subject", "")

        if target_subject and subject != target_subject:
            continue

        plan["priority_topics"].append({
            "topic": topic,
            "subject": subject,
            "current_mastery": score,
            "target_mastery": 0.8,
            "recommended_exercises": 5,
            "priority": "high" if score < 0.4 else "medium",
        })

    # 复习已掌握但可能遗忘的知识点
    for s in strengths[:3]:
        topic = s.get("topic", "")
        subject = s.get("subject", "")

        if target_subject and subject != target_subject:
            continue

        plan["review_topics"].append({
            "topic": topic,
            "subject": subject,
            "review_frequency": "每周 1 次",
        })

    # 建议新知识点（从知识库中获取）
    if knowledge_base:
        available_subjects = knowledge_base.list_subjects()
        for subj in available_subjects:
            if target_subject and subj != target_subject:
                continue

            topics = knowledge_base.list_topics(subj)
            for topic in topics:
                # 排除已学过的
                if topic not in [wp.get("topic") for wp in weak_points] and \
                   topic not in [s.get("topic") for s in strengths]:
                    plan["new_topics"].append({
                        "topic": topic,
                        "subject": subj,
                        "difficulty": "easy",  # 新知识点建议从简单开始
                    })

    # 生成每日学习计划（示例）
    if plan["priority_topics"]:
        plan["daily_schedule"] = [
            {
                "day": "周一",
                "focus": plan["priority_topics"][0].get("topic", "基础概念"),
                "duration": "45 分钟",
                "activities": ["观看讲解", "做练习题", "提交答案"],
            },
            {
                "day": "周二",
                "focus": "巩固复习",
                "duration": "30 分钟",
                "activities": ["回顾前一天内容", "做拓展练习"],
            },
            {
                "day": "周三",
                "focus": plan["priority_topics"][1].get("topic", "进阶内容") if len(plan["priority_topics"]) > 1 else "自由练习",
                "duration": "45 分钟",
                "activities": ["观看讲解", "做练习题"],
            },
        ]

    return plan


@router.post("/student/{student_id}/update-weak-point")
async def update_weak_point(
    student_id: str,
    topic: str,
    score: float,
    subject: str = "general",
):
    """
    更新学生知识点得分。

    用于记录学生练习成绩，更新薄弱点追踪。
    """
    if memory is None:
        raise HTTPException(status_code=500, detail="Memory 未初始化")

    memory.update_weak_point(
        student_id=student_id,
        topic=topic,
        score=score,  # 0-1，越高越好
        subject=subject,
    )

    return {
        "success": True,
        "student_id": student_id,
        "topic": topic,
        "new_score": score,
        "subject": subject,
    }


# ------------------------------------------------------------------
#  知识图谱可视化接口（供前端 D3.js 使用）
# ------------------------------------------------------------------


@router.get("/student/{student_id}/knowledge-graph")
async def get_knowledge_graph_data(student_id: str):
    """
    获取学生知识图谱可视化数据。

    数据来源：
    1. 节点 = 知识库 (knowledge_base) 中的全部课程知识点（作为"应学范围"）
    2. 学生掌握度 = 中期记忆 (WeakPointTracker) 中该学生的实际得分
       - 有数据 → 按实际分数着色
       - 无数据 → 标记为"未学习"（灰色）

    返回格式适配 D3.js 力导向图：
    - nodes: 知识点节点（含掌握程度、标签、颜色状态）
    - links: 知识点关联边
    - statistics: 统计摘要
    """
    if memory is None:
        raise HTTPException(status_code=500, detail="Memory 未初始化")

    # 1. 从知识库获取全部课程知识点（图谱的"全集"）
    all_curriculum_topics = {}  # {subject: [topic_name, ...]}
    if knowledge_base is not None:
        for subject in knowledge_base.list_subjects():
            all_curriculum_topics[subject] = knowledge_base.list_topics(subject)
    else:
        # 知识库未初始化时使用预置数据兜底
        from backend.rag import COURSE_DATA
        all_curriculum_topics = {
            subj: list(topics.keys()) for subj, topics in COURSE_DATA.items()
        }

    # 2. 从学生记忆获取实际掌握数据
    profile = memory.get_student_profile(student_id)
    student_topics = profile.get("all_topics", {})  # {subject: {topic: {score, attempts, ...}}}

    # 3. 合并：课程知识点为底，学生数据叠加
    nodes = []
    links = []
    subject_order = {}  # {subject: [node_id, ...]}  用于生成边

    for subject, topic_names in all_curriculum_topics.items():
        subject_order[subject] = []
        for topic_name in topic_names:
            node_id = f"{subject}_{topic_name}"
            subject_order[subject].append(node_id)

            # 查找学生在该知识点的实际数据
            topic_data = student_topics.get(subject, {}).get(topic_name)
            if topic_data is not None:
                # 有学习记录：使用真实掌握度
                score = topic_data.get("score", 0.5)
                attempts = topic_data.get("attempts", 0)
                status = "mastered" if score >= 0.8 else ("weak" if score < 0.4 else "learning")
            else:
                # 无学习记录：标记为"未学习"
                score = 0.0
                attempts = 0
                status = "unstudied"

            nodes.append({
                "id": node_id,
                "label": topic_name,
                "subject": subject,
                "mastery": round(score, 2),
                "attempts": attempts,
                "mastered": status == "mastered",
                "weak": status == "weak",
                "learning": status == "learning",
                "unstudied": status == "unstudied",
                "size": 6 + score * 8 if status != "unstudied" else 5,
            })

    # 4. 构建边（同一学科内相邻知识点相连，模拟知识依赖关系）
    for subject, node_ids in subject_order.items():
        for i in range(len(node_ids) - 1):
            links.append({
                "source": node_ids[i],
                "target": node_ids[i + 1],
                "weight": 0.5,
            })

    # 5. 统计（只统计有学习记录的知识点）
    studied_nodes = [n for n in nodes if not n.get("unstudied")]
    studied_scores = [n["mastery"] for n in studied_nodes]
    stats = {
        "total_nodes": len(nodes),
        "studied_nodes": len(studied_nodes),
        "unstudied_nodes": len(nodes) - len(studied_nodes),
        "avg_mastery": round(sum(studied_scores) / len(studied_scores), 2) if studied_scores else 0,
        "mastered": len([n for n in studied_nodes if n["mastered"]]),
        "needs_work": len([n for n in studied_nodes if n["weak"]]),
        "subjects": list(all_curriculum_topics.keys()),
    }

    return {
        "student_id": student_id,
        "nodes": nodes,
        "links": links,
        "statistics": stats,
    }


# ------------------------------------------------------------------
#  知识库检索接口
# ------------------------------------------------------------------


@router.get("/knowledge/search")
async def knowledge_search(
    query: str,
    subject: str = "python",
    k: int = 5,
):
    """
    从知识库检索学习材料。
    """
    if knowledge_base is None:
        raise HTTPException(status_code=500, detail="Knowledge Base 未初始化")

    results = knowledge_base.hybrid_search(query, subject, k)

    return {
        "query": query,
        "subject": subject,
        "results": results,
        "count": len(results),
    }


@router.get("/knowledge/topics")
async def list_topics(subject: str = "python"):
    """
    列出指定科目的所有知识点主题。
    """
    if knowledge_base is None:
        raise HTTPException(status_code=500, detail="Knowledge Base 未初始化")

    topics = knowledge_base.list_topics(subject)
    subjects = knowledge_base.list_subjects()

    return {
        "subject": subject,
        "topics": topics,
        "available_subjects": subjects,
    }


# ------------------------------------------------------------------
#  会话管理接口
# ------------------------------------------------------------------


@router.delete("/session/{session_id}")
async def clear_session(session_id: str):
    """
    清除指定会话的短期记忆。
    """
    if memory is None:
        raise HTTPException(status_code=500, detail="Memory 未初始化")

    memory.cleanup_session(session_id)

    return {"success": True, "session_id": session_id}


@router.get("/session/{session_id}/history")
async def get_session_history(session_id: str, last_n: int = 20):
    """
    获取会话对话历史。
    """
    if memory is None:
        raise HTTPException(status_code=500, detail="Memory 未初始化")

    history = memory.short_term.get_history(session_id, last_n)

    return {
        "session_id": session_id,
        "history": history,
        "count": len(history),
    }


# ------------------------------------------------------------------
#  MCP 工具接口
# ------------------------------------------------------------------


@router.get("/mcp/tools")
async def list_mcp_tools():
    """
    列出所有已加载的 MCP 工具。

    返回工具名称和描述，供前端或调试使用。
    """
    if not mcp_tools:
        return {"tools": [], "count": 0, "message": "MCP 工具未加载"}

    tools_info = []
    for tool in mcp_tools:
        name = getattr(tool, "name", str(tool))
        desc = getattr(tool, "description", "") or ""
        tools_info.append({"name": name, "description": desc})

    return {"tools": tools_info, "count": len(tools_info)}


@router.post("/mcp/tools/{tool_name}")
async def call_mcp_tool_endpoint(tool_name: str, params: Dict[str, Any] = {}):
    """
    手动调用指定 MCP 工具（调试用）。

    Args:
        tool_name: 工具名称。
        params: 传递给工具的参数。
    """
    if not mcp_tools:
        raise HTTPException(status_code=500, detail="MCP 工具未加载")

    result = await _call_mcp_tool_async(tool_name, **params)
    if result is None:
        raise HTTPException(status_code=404, detail=f"工具 '{tool_name}' 未找到")

    return {"tool_name": tool_name, "result": result}


# ------------------------------------------------------------------
#  图片上传接口
# ------------------------------------------------------------------


def _is_valid_image_signature(content: bytes) -> bool:
    """基于魔数校验真实图片类型（不依赖扩展名 / content_type）。"""
    if len(content) < 12:
        return False
    if content[:8] == b"\x89PNG\r\n\x1a\n":
        return True
    if content[:3] == b"\xff\xd8\xff":
        return True
    if content[:6] in (b"GIF87a", b"GIF89a"):
        return True
    if content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return True
    if content[:2] == b"BM":
        return True
    return False


def _verify_image(content: bytes) -> None:
    """解码校验图片合法性；环境具备 Pillow 时用其做强校验，否则退化到魔数校验。"""
    import io
    try:
        from PIL import Image
        Image.open(io.BytesIO(content)).verify()
    except ImportError:
        if not _is_valid_image_signature(content):
            raise ValueError("不是合法的图片文件")
    except Exception as e:
        raise ValueError(f"图片解码失败: {e}")


def _enforce_upload_quota(upload_dir: Path, max_files: int = 300) -> None:
    """控制 uploads 目录规模：超出上限时删除最旧的文件。"""
    try:
        files = [f for f in upload_dir.iterdir() if f.is_file()]
        if len(files) <= max_files:
            return
        files.sort(key=lambda f: f.stat().st_mtime)  # 最旧在前
        for old in files[: len(files) - max_files]:
            try:
                old.unlink()
            except OSError:
                pass
    except OSError:
        pass


@router.post("/upload-image")
async def upload_image(file: UploadFile = File(...), student_id: str = Form("unknown")):
    """
    上传图片（作业截图、题目照片等），做安全校验后保存到 uploads 目录。

    安全措施：
    - 大小上限（5MB）；
    - 魔数 + 解码校验，确认真实图片（不只看扩展名 / content_type）；
    - student_id 仅保留安全字符，防路径穿越；
    - 唯一文件名，并定期清理旧文件。
    """
    MAX_UPLOAD_BYTES = 5 * 1024 * 1024

    # 1. 读取内容并校验大小
    content = await file.read()
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="文件为空")
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"文件过大（{len(content) // 1024}KB），上限 {MAX_UPLOAD_BYTES // 1024}KB",
        )

    # 2. 解码 / 魔数校验，确认真实图片
    try:
        _verify_image(content)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # 3. 仅保留安全字符，防路径穿越
    safe_id = (
        "".join(c for c in (student_id or "unknown") if c.isalnum() or c in "-_")[:32]
        or "unknown"
    )

    # 4. 唯一文件名（保留扩展名）
    ext = Path(file.filename).suffix if file.filename else ".png"
    if ext.lower() not in (".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"):
        ext = ".png"
    unique_name = f"{safe_id}_{uuid.uuid4().hex[:12]}{ext}"

    upload_path = Path(UPLOAD_DIR)
    upload_path.mkdir(parents=True, exist_ok=True)
    file_path = upload_path / unique_name
    with open(file_path, "wb") as f:
        f.write(content)

    # 5. 清理旧文件，控制目录规模
    _enforce_upload_quota(upload_path, max_files=300)

    # 构建访问 URL
    file_url = f"/uploads/{unique_name}"

    # 调用视觉模型分析图片内容
    analyzed_content = None
    content_error = None
    try:
        vision_llm = QwenVisionLLM()
        # 视觉模型为同步网络调用，放到线程池避免阻塞事件循环
        analyzed_content = await asyncio.to_thread(vision_llm.analyze_image, str(file_path))
        print(f"   🖼️ 图片分析完成: {unique_name} ({len(analyzed_content)} 字符)")
    except Exception as e:
        content_error = str(e)
        print(f"   ⚠️ 图片分析失败 ({unique_name}): {e}")

    return {
        "success": True,
        "file_name": file.filename,
        "saved_name": unique_name,
        "url": file_url,
        "size": len(content),
        "content_type": file.content_type,
        "analyzed_content": analyzed_content,
        "content_error": content_error,
    }