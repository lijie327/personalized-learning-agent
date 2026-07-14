"""
Tutor Agent 的 LangGraph 多 Agent 编排包。

对外暴露：
- get_compiled_graph(): 获取编译好的 supervisor 多 Agent 图
- init_graph_globals(knowledge_base, memory): 注入工具所需的全局实例
"""

from backend.graph.builder import get_compiled_graph
from backend.graph.tools import init_graph_globals

__all__ = ["get_compiled_graph", "init_graph_globals"]
