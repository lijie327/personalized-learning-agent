"""
MCP工具统一管理模块
使用MultiServerMCPClient加载所有MCP Server，在应用启动时统一初始化。
"""
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional

from langchain_mcp_adapters.client import MultiServerMCPClient

# 项目根目录（backend/tools/mcp_tools.py → backend → 项目根）
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def _mcp_server_path(relative_path: str) -> str:
    """将相对路径转为基于项目根目录的绝对路径。"""
    return str(_PROJECT_ROOT / relative_path)


class MCPToolManager:
    """MCP工具管理器，统一加载和管理所有教学工具。"""

    def __init__(self):
        self.client: Optional[MultiServerMCPClient] = None
        self.tools: List = []
        self._is_loaded: bool = False
        self._server_configs = self._build_server_configs()
        # 记录每个 server 的 client 引用，用于清理
        self._server_clients: Dict[str, MultiServerMCPClient] = {}

    def _build_server_configs(self) -> Dict[str, Dict[str, Any]]:
        """构建所有MCP Server配置（使用绝对路径）。"""
        return {
            "code_executor": {
                "command": sys.executable,
                "args": [_mcp_server_path("mcp_servers/code_executor_server.py")],
                "transport": "stdio",
            },
            "exercise_generator": {
                "command": sys.executable,
                "args": [_mcp_server_path("mcp_servers/exercise_generator_server.py")],
                "transport": "stdio",
            },
            "assessment": {
                "command": sys.executable,
                "args": [_mcp_server_path("mcp_servers/assessment_server.py")],
                "transport": "stdio",
            },
        }

    @property
    def is_loaded(self) -> bool:
        """是否已成功加载 MCP 工具。"""
        return self._is_loaded

    async def load_tools(self) -> List:
        """
        加载所有MCP工具。

        Returns:
            所有MCP Server提供的工具列表（LangChain BaseTool 实例）。

        Raises:
            RuntimeError: 所有 MCP Server 加载均失败时抛出。
        """
        if self._is_loaded:
            print("⚠️  MCP工具已加载，跳过重复加载。")
            return self.tools

        print("🔌 正在连接 MCP Servers...")
        errors = []

        for server_name, config in self._server_configs.items():
            try:
                print(f"   ⏳ 连接 {server_name}...")
                single_client = MultiServerMCPClient({server_name: config})
                server_tools = await single_client.get_tools()
                self.tools.extend(server_tools)
                # 保存 client 引用，便于后续清理
                self._server_clients[server_name] = single_client
                print(f"   ✅ {server_name}: 加载了 {len(server_tools)} 个工具")
            except Exception as e:
                errors.append(f"{server_name}: {e}")
                print(f"   ⚠️ {server_name}: 连接失败 — {e}")

        if not self.tools:
            raise RuntimeError(
                f"所有 MCP Server 加载均失败:\n" + "\n".join(errors)
            )

        self._is_loaded = True
        print(f"✅ MCP工具加载完成，共 {len(self.tools)} 个工具")
        for tool in self.tools:
            desc = (tool.description or "无描述")[:60]
            print(f"   🔧 {tool.name}: {desc}")
        return self.tools

    async def close(self):
        """关闭所有 MCP Server 连接（清理 stdio 子进程）。"""
        import asyncio
        for name, client in self._server_clients.items():
            try:
                if hasattr(client, 'close'):
                    await client.close()
                elif hasattr(client, 'cleanup'):
                    await client.cleanup()
            except Exception:
                pass
        self._server_clients.clear()

    def get_tool_by_name(self, name: str):
        """根据名称获取指定工具。"""
        for tool in self.tools:
            if tool.name == name:
                return tool
        return None

    def list_tools(self) -> List[Dict[str, str]]:
        """列出所有可用工具。"""
        return [
            {"name": tool.name, "description": tool.description or ""}
            for tool in self.tools
        ]


# 全局单例
mcp_manager = MCPToolManager()
