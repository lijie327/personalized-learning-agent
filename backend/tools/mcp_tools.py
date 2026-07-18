"""
MCP工具统一管理模块
使用MultiServerMCPClient加载所有MCP Server，在应用启动时统一初始化。
"""
import asyncio
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional

from langchain_mcp_adapters.client import MultiServerMCPClient

# 项目根目录（backend/tools/mcp_tools.py → backend → 项目根）
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# ---- 连接健壮性参数（针对 Windows ProactorEventLoop 下 stdio 子进程握手竞态）----
# 现象：Win 开发机偶发 `McpError: Connection closed`（子进程握手阶段中途退出），非确定性；
#       Docker/Linux 稳定。通过「单 server 重试 + 退避」+「server 间错开启动」双重手段提升
#       Windows 本地加载成功率，对已在 Docker 下稳定的部署无任何负面影响。
MCP_CONNECT_MAX_RETRIES = 3   # 单个 server 连接失败后的最大重试次数
MCP_CONNECT_BACKOFF = 0.4     # 重试之间的退避间隔（秒）
MCP_SPAWN_STAGGER = 0.6       # 相邻 server 之间的错开启动间隔（秒），降低 spawn 竞争


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

    async def _safe_close(self, client) -> None:
        """尽力关闭单个 server 的 client，屏蔽 API 差异（close / cleanup / 无该方法）。"""
        try:
            if hasattr(client, "close"):
                await client.close()
            elif hasattr(client, "cleanup"):
                await client.cleanup()
        except Exception:
            pass

    async def _connect_single_server(
        self, server_name: str, config: Dict[str, Any]
    ) -> tuple[List, MultiServerMCPClient]:
        """
        连接单个 MCP Server，带重试与退避。

        针对 Windows ProactorEventLoop 下 stdio 子进程握手竞态
        （`McpError: Connection closed`，子进程中途退出、非确定性），通过重试显著提升
        加载成功率。成功时返回 (tools, client)，且 **保留 client 不关闭**，因为工具实例
        绑定在该 client 的 stdio 会话上；失败时尝试关闭可能遗留的半死子进程后重试。
        """
        last_err: Optional[Exception] = None
        for attempt in range(1, MCP_CONNECT_MAX_RETRIES + 1):
            client = MultiServerMCPClient({server_name: config})
            try:
                tools = await client.get_tools()
            except Exception as e:
                last_err = e
                # 失败时清理可能遗留的半死子进程，避免泄漏
                await self._safe_close(client)
                if attempt < MCP_CONNECT_MAX_RETRIES:
                    print(
                        f"   ↻ {server_name} 第 {attempt}/{MCP_CONNECT_MAX_RETRIES} 次失败，"
                        f"{MCP_CONNECT_BACKOFF}s 后重试 — {e}"
                    )
                    await asyncio.sleep(MCP_CONNECT_BACKOFF)
                continue

            # 拿到空工具列表也视为异常，重试
            if not tools:
                last_err = RuntimeError(f"{server_name} 返回了空工具列表")
                await self._safe_close(client)
                if attempt < MCP_CONNECT_MAX_RETRIES:
                    print(
                        f"   ↻ {server_name} 第 {attempt}/{MCP_CONNECT_MAX_RETRIES} 次返回空，"
                        f"{MCP_CONNECT_BACKOFF}s 后重试"
                    )
                    await asyncio.sleep(MCP_CONNECT_BACKOFF)
                continue

            # 成功：保留 client，工具才能继续工作
            return tools, client

        raise RuntimeError(
            f"{server_name} 连接失败（已重试 {MCP_CONNECT_MAX_RETRIES} 次）: {last_err}"
        )

    async def load_tools(self) -> List:
        """
        加载所有MCP工具（单 server 重试 + server 间错开启动）。

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
        is_first = True

        for server_name, config in self._server_configs.items():
            # 错开启动：避免 3 个子进程在相邻时刻集中 spawn，降低 Windows 握手竞态概率
            if not is_first:
                await asyncio.sleep(MCP_SPAWN_STAGGER)
            is_first = False

            try:
                print(f"   ⏳ 连接 {server_name}...")
                server_tools, single_client = await self._connect_single_server(
                    server_name, config
                )
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
