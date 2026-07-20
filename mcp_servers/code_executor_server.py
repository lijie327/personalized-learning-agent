"""
代码执行 MCP Server
复用 backend.tools.code_executor 的安全沙箱（沙箱守卫拦截 os/subprocess/socket 等
危险模块与 eval/exec 内建），避免与本地实现分裂为两套逻辑，也补齐 MCP 版此前缺失的
危险模块拦截（安全边界一致）。
"""
import importlib.util
import sys
from pathlib import Path

# Windows: 强制 UTF-8 输出
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# 直接按文件路径加载 backend.tools.code_executor（仅依赖标准库），
# 避免触发 backend.tools 包的其它重型依赖导入，保持 MCP 子进程轻量。
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_ce_path = _PROJECT_ROOT / "backend" / "tools" / "code_executor.py"
_spec = importlib.util.spec_from_file_location("_mcp_code_executor", str(_ce_path))
_ce = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_ce)

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("CodeExecutor")


@mcp.tool()
def execute_python(code: str, timeout: int = 5) -> dict:
    """
    安全执行 Python 代码并返回结果（复用 backend 沙箱守卫）。

    Args:
        code: 要执行的 Python 代码
        timeout: 执行超时时间(秒)

    Returns:
        {"success": bool, "output": str, "error": str, "return_code": int}
    """
    return _ce.execute_python(code, timeout=timeout)


@mcp.tool()
def check_syntax(code: str) -> dict:
    """
    检查 Python 代码语法。

    Returns:
        {"valid": bool, "error": str, "line": int | None}
    """
    return _ce.check_syntax(code)


if __name__ == "__main__":
    mcp.run()
