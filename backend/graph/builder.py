"""
Tutor Agent 的 LangGraph 编译入口。

图结构（supervisor 多 Agent）：
    START --(按 classification.agent_type 路由)--> math / programming / knowledge / assessor
    每个 specialist 子图（create_react_agent，自带 tool-calling）
        --> update_memory --> generate_exercises --> END

supervisor 即"按 Router 分类结果做条件路由"的节点，
4 个 specialist 各自是带真实工具的 ReAct 子图。
"""

from langgraph.graph import END, START, StateGraph

from backend.graph.agents import build_agents
from backend.graph.nodes import generate_exercises_node, update_memory_node
from backend.graph.state import TutorState

AGENT_NODES = ["math", "programming", "knowledge", "assessor"]

# 进程内缓存编译结果，避免每次请求重建 ChatOpenAI / 子图
_COMPILED = None


def _route_by_classification(state: dict) -> str:
    """根据 Router 分类结果选择 specialist 子图。"""
    agent_type = state.get("classification", {}).get("agent_type", "knowledge")
    agent_type = agent_type.value if hasattr(agent_type, "value") else agent_type
    return agent_type if agent_type in AGENT_NODES else "knowledge"


def build_tutor_graph():
    """构建并编译 Tutor Agent 的 StateGraph。"""
    agents = build_agents()
    builder = StateGraph(TutorState)

    for name in AGENT_NODES:
        builder.add_node(name, agents[name])
    builder.add_node("update_memory", update_memory_node)
    builder.add_node("generate_exercises", generate_exercises_node)

    builder.add_conditional_edges(
        START, _route_by_classification, {name: name for name in AGENT_NODES}
    )
    for name in AGENT_NODES:
        builder.add_edge(name, "update_memory")
    builder.add_edge("update_memory", "generate_exercises")
    builder.add_edge("generate_exercises", END)

    return builder.compile()


def get_compiled_graph():
    """返回缓存的已编译图（首次调用时构建）。"""
    global _COMPILED
    if _COMPILED is None:
        _COMPILED = build_tutor_graph()
    return _COMPILED
