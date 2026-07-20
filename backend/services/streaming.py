"""SSE 流式辅导主流程：意图分流 + Router 路由 + LangGraph 多 Agent 图驱动。"""

import asyncio
import json
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, List, Optional

from backend.llm import QwenLLM
from backend.models import AgentType
from backend.services import context, intent, sse

import backend.runtime as runtime


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
    memory = runtime.memory
    router_agent = runtime.router_agent

    # 1. 获取学生画像
    profile = memory.get_student_profile(student_id, session_id)
    weak_points = profile.get("weak_points", [])
    student_context = context.build_student_context(profile)

    # 1.5 构建对话历史（供意图处理和 Router/LLM 使用）
    raw_history = memory.short_term.get_history(session_id, last_n=10)
    chat_history = [{"role": m["role"], "content": m["content"]} for m in raw_history]

    # 2. 意图识别：根据学生意图选择最合适的处理方式
    intent_type = intent.detect_intent(question)
    session_context = memory.short_term.get_context(session_id, last_n=10)
    print(f"\n[Intent] question='{question}' | intent={intent_type.value} | weak_points={weak_points}")

    # --- 处理名字询问 ---
    if intent_type == intent.IntentType.NAME_QUERY:
        stored_name = profile.get("name", "")
        name_response = intent.build_name_query_response(stored_name)
        yield sse.sse_format({
            "type": "route", "agent": "memory", "subject": "name_query",
            "confidence": 1.0, "reasoning": "学生询问自己的名字，从记忆数据查找",
            "weak_points": weak_points,
        })
        for char in name_response:
            yield sse.sse_format({"type": "token", "token": char, "agent": "memory", "mode": "direct"})
            await asyncio.sleep(0.005)
        memory.add_session_message(session_id, {"role": "user", "content": question, "timestamp": datetime.now().isoformat()})
        memory.add_session_message(session_id, {"role": "assistant", "content": name_response, "agent": "memory", "timestamp": datetime.now().isoformat()})
        yield sse.sse_format({
            "type": "done", "done": True, "exercises": [],
            "weak_points": weak_points, "agent": "memory",
            "suggested_topics": [],
        })
        return

    # --- 处理自我介绍 ---
    if intent_type == intent.IntentType.SELF_INTRO:
        student_name = intent.extract_name_from_intro(question)
        if student_name:
            # 更新学生的名字到中期记忆中
            memory.set_metadata(student_id, "name", student_name)
            intro_response = intent.build_self_intro_response(student_name)
        else:
            intro_response = "你好！请问你的名字是什么？"
        yield sse.sse_format({
            "type": "route", "agent": "memory", "subject": "self_intro",
            "confidence": 1.0, "reasoning": "学生自我介绍，更新档案",
            "weak_points": weak_points,
        })
        for char in intro_response:
            yield sse.sse_format({"type": "token", "token": char, "agent": "memory", "mode": "direct"})
            await asyncio.sleep(0.005)
        memory.add_session_message(session_id, {"role": "user", "content": question, "timestamp": datetime.now().isoformat()})
        memory.add_session_message(session_id, {"role": "assistant", "content": intro_response, "agent": "memory", "timestamp": datetime.now().isoformat()})
        yield sse.sse_format({
            "type": "done", "done": True, "exercises": [],
            "weak_points": weak_points, "agent": "memory",
            "suggested_topics": [wp["topic"] for wp in profile.get("weak_points_detail", [])[:3]],
        })
        return

    # --- 处理问候 ---
    if intent_type == intent.IntentType.GREETING:
        greeting_response = intent.build_greeting_response()
        yield sse.sse_format({
            "type": "route", "agent": "memory", "subject": "greeting",
            "confidence": 1.0, "reasoning": "学生打招呼，友好回应",
            "weak_points": weak_points,
        })
        for char in greeting_response:
            yield sse.sse_format({"type": "token", "token": char, "agent": "memory", "mode": "direct"})
            await asyncio.sleep(0.005)
        memory.add_session_message(session_id, {"role": "user", "content": question, "timestamp": datetime.now().isoformat()})
        memory.add_session_message(session_id, {"role": "assistant", "content": greeting_response, "agent": "memory", "timestamp": datetime.now().isoformat()})
        yield sse.sse_format({
            "type": "done", "done": True, "exercises": [],
            "weak_points": weak_points, "agent": "memory",
            "suggested_topics": [],
        })
        return

    # --- 处理对话历史引用 ---
    if intent_type == intent.IntentType.HISTORY_REF:
        history_response = intent.build_history_ref_response(session_context)
        yield sse.sse_format({
            "type": "route", "agent": "memory", "subject": "history_ref",
            "confidence": 1.0, "reasoning": "学生询问之前讨论过的内容，直接展示会话历史",
            "weak_points": weak_points,
        })
        for char in history_response:
            yield sse.sse_format({"type": "token", "token": char, "agent": "memory", "mode": "direct"})
            await asyncio.sleep(0.005)
        memory.add_session_message(session_id, {"role": "user", "content": question, "timestamp": datetime.now().isoformat()})
        memory.add_session_message(session_id, {"role": "assistant", "content": history_response, "agent": "memory", "timestamp": datetime.now().isoformat()})
        yield sse.sse_format({
            "type": "done", "done": True, "exercises": [],
            "weak_points": weak_points, "agent": "memory",
            "suggested_topics": [],
        })
        return

    # --- 处理自我查询（薄弱点等） ---
    if intent_type == intent.IntentType.SELF_QUERY:
        self_response = intent.build_self_query_response(profile)
        yield sse.sse_format({
            "type": "route",
            "agent": "memory",
            "subject": "self_query",
            "confidence": 1.0,
            "reasoning": "学生询问自身学习状况，直接使用记忆数据",
            "weak_points": weak_points,
        })
        # 流式输出记忆数据（按段落拆分模拟 token 流）
        for char in self_response:
            yield sse.sse_format({
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
        yield sse.sse_format({
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
    yield sse.sse_format({
        "type": "route",
        "agent": routed_agent_type.value,
        "subject": subject,
        "confidence": confidence,
        "reasoning": reasoning,
        "weak_points": weak_points,
    })

    # 2.5 判断是否与教学内容相关：subject 不匹配已知科目时，直接调用 LLM 自由回答
    is_known_subject = intent.is_known_subject(subject)
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
        off_topic_prompt = f"{question}\n{student_context}"
        system_prompt = "你是一个智能助手。请直接、自然地回答用户的问题。用中文回答。"
        full_response = ""
        try:
            async for token in llm.astream_with_history(off_topic_prompt, system_prompt=system_prompt, history=chat_history):
                full_response += token
                yield sse.sse_format({
                    "type": "token", "token": token,
                    "agent": "general", "mode": "chat",
                })
        except Exception as e:
            yield sse.sse_format({"type": "error", "error": str(e)})
            return

        memory.add_session_message(session_id, {"role": "user", "content": question, "timestamp": datetime.now().isoformat()})
        memory.add_session_message(session_id, {"role": "assistant", "content": full_response, "agent": "general", "timestamp": datetime.now().isoformat()})
        yield sse.sse_format({
            "type": "done", "done": True, "exercises": [],
            "weak_points": weak_points, "agent": "general",
            "suggested_topics": [],
        })
        return

    # 3. 路由到 LangGraph supervisor 多 Agent 图，由其调度 specialist 子图并流式返回
    async for sse_msg in stream_via_graph(
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
        yield sse_msg
    return


# ---------------------------------------------------------------------------
#  LangGraph 流式封装：把编译图的事件映射为 SSE
# ---------------------------------------------------------------------------


async def stream_via_graph(
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

    student_context = context.build_student_context(profile)
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
                    yield sse.sse_format({
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
                yield sse.sse_format({
                    "type": "sources",
                    "sources": sources,
                    "agent": agent_type,
                })
            elif ev == "on_chain_end" and event.get("name") == "generate_exercises":
                exercises = event["data"]["output"].get("exercises", [])
    except Exception as e:
        yield sse.sse_format({"type": "error", "error": str(e)})
        return

    yield sse.sse_format({
        "type": "done",
        "done": True,
        "exercises": exercises,
        "weak_points": weak_points,
        "agent": agent_type,
        "suggested_topics": classification.get("suggested_tools", []),
    })
