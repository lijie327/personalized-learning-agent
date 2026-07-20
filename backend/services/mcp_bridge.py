"""MCP 工具桥接：在 API 端点与 MCP 子进程工具之间建立调用通道。"""

from typing import Any, Dict, Optional

import backend.runtime as runtime


async def call_mcp_tool_async(tool_name: str, **kwargs) -> Optional[Dict[str, Any]]:
    """
    异步调用指定 MCP 工具并返回结果。

    Args:
        tool_name: MCP 工具名称。
        **kwargs: 传递给工具的参数。

    Returns:
        工具返回结果字典，工具不存在或调用失败返回 None。
    """
    for tool in runtime.mcp_tools:
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
