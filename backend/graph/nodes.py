"""
LangGraph 节点：记忆落库与练习推荐。

这些节点在 specialist 子图产出最终回复之后执行，
把对话写入记忆、并基于薄弱点生成推荐练习题。
"""

from langchain_core.messages import AIMessage

from backend.graph.tools import _GLOBALS


def _extract_response(state: dict) -> str:
    """从 messages 中取出最后一条 AI 消息作为最终回复。"""
    for msg in reversed(state.get("messages", []) or []):
        if isinstance(msg, AIMessage):
            content = msg.content
            return content if isinstance(content, str) else str(content)
    return ""


def update_memory_node(state: dict) -> dict:
    """
    将本轮问答写入短期记忆。

    薄弱点不被此处污染——仅由真实测评（/exercise/evaluate）更新。
    """
    memory = _GLOBALS.get("memory")
    session_id = state.get("session_id", "")
    question = state.get("question", "")
    response = _extract_response(state)
    agent_type = state.get("classification", {}).get("agent_type", "knowledge")

    if memory and response:
        memory.add_session_message(
            session_id,
            {"role": "user", "content": question, "timestamp": _now()},
        )
        memory.add_session_message(
            session_id,
            {
                "role": "assistant",
                "content": response,
                "agent": agent_type,
                "timestamp": _now(),
            },
        )

    return {"response": response}


def generate_exercises_node(state: dict) -> dict:
    """基于学生第一个薄弱点生成 1 道推荐练习题。"""
    weak_points = state.get("weak_points", []) or []
    if not weak_points:
        return {"exercises": []}

    weak_topic = weak_points[0]
    try:
        from backend.tools import generate_exercise

        result = generate_exercise(
            topic=weak_topic,
            difficulty="medium",
            subject="python",
            count=1,
        )
        exercises = result.get("exercises", [])
    except Exception:
        exercises = []

    return {"exercises": exercises}


def _now() -> str:
    from datetime import datetime

    return datetime.now().isoformat()
