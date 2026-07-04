"""
代码执行 MCP Server
提供安全的Python代码在线执行能力
"""
import subprocess
import sys
import tempfile
import os

# Windows: 强制 UTF-8 输出
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("CodeExecutor")


@mcp.tool()
def execute_python(code: str, timeout: int = 5) -> dict:
    """
    安全执行Python代码并返回结果

    Args:
        code: 要执行的Python代码
        timeout: 执行超时时间(秒)

    Returns:
        {"success": bool, "output": str, "error": str, "execution_time": float}
    """
    # 先做语法检查
    syntax = check_syntax(code)
    if not syntax["valid"]:
        return {
            "success": False,
            "output": "",
            "error": syntax["error"],
            "returncode": -1,
        }

    # 检测交互式输入
    if _uses_interactive_input(code):
        return {
            "success": False,
            "output": "",
            "error": (
                "代码中使用了 input() 等交互式输入函数，在线沙箱不支持。"
                "请将代码改为非交互式：用变量赋值替代 input() 调用。"
            ),
            "returncode": -1,
        }

    # 清理 PYTHONPATH 防止导入项目模块
    safe_env = os.environ.copy()
    safe_env.pop("PYTHONPATH", None)

    try:
        # 写入临时文件
        with tempfile.NamedTemporaryFile(
                mode='w', suffix='.py', delete=False, encoding='utf-8'
        ) as f:
            f.write(code)
            temp_path = f.name

        # 沙箱执行
        result = subprocess.run(
            [sys.executable, temp_path],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=os.path.dirname(temp_path),
            env=safe_env,
            stdin=subprocess.DEVNULL,
        )

        # 清理临时文件
        os.unlink(temp_path)

        stdout = result.stdout
        stderr = result.stderr
        max_len = 5000
        if len(stdout) > max_len:
            stdout = stdout[:max_len] + "\n... [输出已截断]"
        if len(stderr) > max_len:
            stderr = stderr[:max_len] + "\n... [错误已截断]"

        return {
            "success": result.returncode == 0,
            "output": stdout.strip() or "(无输出)",
            "error": stderr.strip() if result.returncode != 0 else None,
            "returncode": result.returncode
        }

    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "output": "",
            "error": f"代码执行超时（>{timeout}秒）",
            "returncode": -1,
        }
    except Exception as e:
        return {
            "success": False,
            "output": "",
            "error": str(e),
            "returncode": -1,
        }


def _uses_interactive_input(code: str) -> bool:
    """检测代码中是否使用了交互式输入函数（input 等）。"""
    import ast as ast_module
    try:
        tree = ast_module.parse(code)

        class InputVisitor(ast_module.NodeVisitor):
            def __init__(self):
                self.found = False

            def visit_Call(self, node):
                if isinstance(node.func, ast_module.Name) and node.func.id == "input":
                    self.found = True
                elif isinstance(node.func, ast_module.Attribute):
                    attr_chain = []
                    obj = node.func
                    while isinstance(obj, ast_module.Attribute):
                        attr_chain.append(obj.attr)
                        obj = obj.value
                    if isinstance(obj, ast_module.Name):
                        attr_chain.append(obj.id)
                        full_name = ".".join(reversed(attr_chain))
                        if full_name in ("sys.stdin.read", "sys.stdin.readline", "sys.stdin.readlines"):
                            self.found = True
                self.generic_visit(node)

        visitor = InputVisitor()
        visitor.visit(tree)
        return visitor.found
    except SyntaxError:
        return False


@mcp.tool()
def check_syntax(code: str) -> dict:
    """
    检查Python代码语法

    Args:
        code: 要检查的Python代码

    Returns:
        {"valid": bool, "error": str}
    """
    try:
        compile(code, '<check>', 'exec')
        return {"valid": True, "error": None}
    except SyntaxError as e:
        return {
            "valid": False,
            "error": f"第{e.lineno}行: {e.msg}"
        }


if __name__ == "__main__":
    mcp.run()