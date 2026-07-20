"""全局运行时状态。

由 main.py 的 lifespan 在启动时通过 init_agents() 注入实际实例；
各子路由在请求处理时通过 ``runtime.memory`` 等属性访问最新值，
避免在导入期就把全局变量绑定为 ``None`` 的经典陷阱，也避免子路由之间出现循环依赖。
"""

from typing import List, Optional

from backend.agents.router_agent import RouterAgent
from backend.memory import LearningMemory
from backend.rag import EducationKnowledgeBase


router_agent: Optional[RouterAgent] = None
memory: Optional[LearningMemory] = None
knowledge_base: Optional[EducationKnowledgeBase] = None
mcp_tools: List = []


def init_agents(
    router: RouterAgent,
    mem: LearningMemory,
    kb: EducationKnowledgeBase,
    mcp_tool_list: Optional[List] = None,
) -> None:
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
