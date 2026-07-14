"""
Tutor Agent 的 LangGraph 状态定义。

TutorState 在 MessagesState 基础上扩展业务字段：学生画像、路由结果、
RAG 来源、薄弱点、练习题等。消息通过 add_messages 规约自动合并，
保证 specialist 子图与 supervisor 之间共享同一份对话历史。
"""

from typing import Annotated, Any, Dict, List, Optional

from langgraph.graph import MessagesState
from langchain_core.messages import BaseMessage


class TutorState(MessagesState):
    """
    LangGraph 在节点间传递的状态对象。

    字段说明：
    - messages: 对话消息（由 MessagesState 提供，add_messages 规约）
    - question / student_id / session_id / mode / code: 请求参数
    - intent: 意图类型
    - profile: 学生画像（薄弱点、知识图谱等）
    - chat_history: 短期记忆中的历史消息
    - classification: Router 分类结果（subject / agent_type / confidence）
    - rag_sources: RAG 检索到的来源片段（供前端展示）
    - rag_context: 已拼接的参考资料文本
    - response: 最终辅导回复（由 update_memory 节点回填）
    - weak_points: 当前薄弱点列表
    - exercises: 推荐练习题列表
    """

    question: str
    student_id: str
    session_id: str
    mode: str
    code: Optional[str]
    intent: str
    profile: Dict[str, Any]
    chat_history: List[Dict[str, Any]]
    classification: Dict[str, Any]
    rag_sources: List[Dict[str, Any]]
    rag_context: str
    response: str
    weak_points: List[str]
    exercises: List[Dict[str, Any]]
