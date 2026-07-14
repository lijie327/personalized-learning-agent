"""
Specialist Agent 构建。

每个 specialist 是一个用 create_react_agent 创建的 ReAct 子图：
LLM 自主决定调用哪些工具（RAG / 代码沙箱 / 练习题 / 评估），
再综合工具结果给出辅导回复。这就是真正的 tool-calling，而非文本注入。
"""

from langgraph.prebuilt import create_react_agent

from backend.graph.llm import get_chat_model
from backend.graph.tools import (
    rag_search,
    run_python_code,
    generate_practice,
    evaluate_practice,
)
from backend.agents.math_tutor import MathTutor
from backend.agents.programming_tutor import ProgrammingTutor
from backend.agents.knowledge_agent import KnowledgeAgent
from backend.agents.assessor_agent import AssessorAgent


def build_agents() -> dict:
    """构建 4 个 specialist 子图，返回 {agent_type: compiled_graph}。"""
    model = get_chat_model()

    math = create_react_agent(
        model,
        [rag_search, generate_practice, evaluate_practice],
        prompt=MathTutor._math_system_prompt(),
    )
    programming = create_react_agent(
        model,
        [run_python_code, rag_search, generate_practice],
        prompt=ProgrammingTutor._programming_system_prompt(),
    )
    knowledge = create_react_agent(
        model,
        [rag_search],
        prompt=KnowledgeAgent._knowledge_system_prompt(),
    )
    assessor = create_react_agent(
        model,
        [generate_practice, evaluate_practice],
        prompt=AssessorAgent._assessor_system_prompt(),
    )

    return {
        "math": math,
        "programming": programming,
        "knowledge": knowledge,
        "assessor": assessor,
    }
