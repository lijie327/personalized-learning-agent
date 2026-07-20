"""MCP 工具接口（调试用）。"""

from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from backend.services.mcp_bridge import call_mcp_tool_async

import backend.runtime as runtime

router = APIRouter(tags=["mcp"])


@router.get("/mcp/tools")
async def list_mcp_tools():
    """
    列出所有已加载的 MCP 工具。

    返回工具名称和描述，供前端或调试使用。
    """
    if not runtime.mcp_tools:
        return {"tools": [], "count": 0, "message": "MCP 工具未加载"}

    tools_info = []
    for tool in runtime.mcp_tools:
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
    if not runtime.mcp_tools:
        raise HTTPException(status_code=500, detail="MCP 工具未加载")

    result = await call_mcp_tool_async(tool_name, **params)
    if result is None:
        raise HTTPException(status_code=404, detail=f"工具 '{tool_name}' 未找到")

    return {"tool_name": tool_name, "result": result}
