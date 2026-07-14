"""
代码执行工具
提供安全的 Python 代码沙箱执行和语法检查功能。
"""

import ast
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
#  沙箱守卫：在用户代码前注入，限制危险模块与内建函数
#  阻断 os / subprocess / socket 等任意执行与网络外联，消除 RCE 风险。
# ---------------------------------------------------------------------------

# 禁止导入的危险模块（首段包名）
_SANDBOX_BLOCKED_MODULES = {
    "os", "subprocess", "socket", "shutil", "ctypes", "ctypes.util",
    "multiprocessing", "pty", "pickle", "marshal", "shelve",
    "requests", "urllib", "http", "ftplib", "smtplib", "telnetlib",
    "imaplib", "poplib", "nntplib", "asyncio", "importlib", "code",
    "resource", "signal", "builtins", "sys", "pathlib",
}

# 从内建命名空间中移除的危险内建函数
# 注意：__import__ 不能移除——它会被替换为 _sb_safe_import（见 build_sandbox_guard），
# 移除后所有 import 语句都会报 "__import__ not found"。这里只移除真正的动态执行入口。
_SANDBOX_REMOVED_BUILTINS = ("eval", "exec", "compile")


def build_sandbox_guard() -> str:
    """
    生成沙箱守卫代码（作为用户代码的前缀注入子进程）。

    作用：
    1. 替换 __import__，拦截 os/subprocess/socket 等危险模块导入（合法模块不受影响）。
    2. 删除 eval / exec / compile 内建，防止动态执行。
    注意：__import__ 不会被删除，而是被替换为安全版本；学生代码中的合法
    import（math、random、re 等）仍可正常工作。
    """
    blocked = ", ".join(repr(m) for m in sorted(_SANDBOX_BLOCKED_MODULES))
    removed = ", ".join(repr(b) for b in _SANDBOX_REMOVED_BUILTINS)
    return f'''
import builtins as _sb_builtins
_SB_BLOCKED = {{{blocked}}}
_SB_REMOVED = [{removed}]
_SB_ORIG_IMPORT = _sb_builtins.__import__
def _sb_safe_import(name, *args, _blocked=_SB_BLOCKED, _orig=_SB_ORIG_IMPORT, **kwargs):
    _top = name.split(".")[0]
    if _top in _blocked:
        raise ImportError("模块 '{{}}' 在沙箱中不可用".format(_top))
    return _orig(name, *args, **kwargs)
_sb_builtins.__import__ = _sb_safe_import
for _n in _SB_REMOVED:
    if hasattr(_sb_builtins, _n):
        delattr(_sb_builtins, _n)
del _sb_builtins, _SB_BLOCKED, _SB_REMOVED, _SB_ORIG_IMPORT, _sb_safe_import, _n
'''


def execute_python(
    code: str,
    timeout: int = 5,
    max_output_length: int = 5000,
) -> dict:
    """
    在子进程沙箱中安全执行 Python 代码。

    使用 subprocess 隔离执行环境，设置超时防止死循环；
    注入沙箱守卫代码，阻断 os/subprocess/socket 等危险模块与
    eval/exec 等动态执行内建，消除任意代码执行（RCE）风险。

    Args:
        code: 待执行的 Python 源代码字符串。
        timeout: 最大执行时间（秒），默认 5 秒。
        max_output_length: 最大输出长度，超出部分截断。

    Returns:
        字典格式结果：
        {
            "success": bool,       # 是否执行成功
            "output": str,         # 标准输出内容
            "error": str | None,   # 错误信息（如有）
            "return_code": int,    # 进程返回码
        }
    """
    # 先做语法检查，语法错误直接返回，不启动子进程
    syntax_result = check_syntax(code)
    if not syntax_result["valid"]:
        return {
            "success": False,
            "output": "",
            "error": syntax_result["error"],
            "return_code": -1,
        }

    # 检测代码中是否包含 input() 调用（沙箱不支持交互式输入）
    if _uses_interactive_input(code):
        return {
            "success": False,
            "output": "",
            "error": (
                "代码中使用了 input() 等交互式输入函数，在线沙箱不支持。\n"
                "请将代码改为非交互式：用变量赋值替代 input() 调用。\n"
                "例如：name = '张三'  # 替代 name = input('请输入姓名: ')"
            ),
            "return_code": -1,
        }

    # 注入沙箱守卫，限制危险模块与内建
    guarded_code = build_sandbox_guard() + "\n" + code

    # 在临时目录中执行，避免污染主文件系统
    with tempfile.TemporaryDirectory() as tmpdir:
        script_path = Path(tmpdir) / "solution.py"
        script_path.write_text(guarded_code, encoding="utf-8")

        try:
            # 继承当前进程环境变量，只覆盖需要隔离的部分
            # 不能清空 PATH，否则子进程无法找到 Python 运行所需的系统库
            safe_env = os.environ.copy()
            safe_env["HOME"] = tmpdir
            # 清空 PYTHONPATH，防止子进程导入项目中的模块
            safe_env.pop("PYTHONPATH", None)

            result = subprocess.run(
                [sys.executable, str(script_path)],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=tmpdir,  # 隔离工作目录
                env=safe_env,
                stdin=subprocess.DEVNULL,  # 禁止交互式输入，input() 会立即报 EOFError
            )

            stdout = result.stdout
            stderr = result.stderr

            # 截断过长的输出
            if len(stdout) > max_output_length:
                stdout = stdout[:max_output_length] + "\n... [输出已截断]"
            if len(stderr) > max_output_length:
                stderr = stderr[:max_output_length] + "\n... [错误已截断]"

            return {
                "success": result.returncode == 0,
                "output": stdout.strip(),
                "error": stderr.strip() if result.returncode != 0 else None,
                "return_code": result.returncode,
            }

        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "output": "",
                "error": f"执行超时（超过 {timeout} 秒），请检查是否存在死循环。",
                "return_code": -1,
            }
        except Exception as e:
            return {
                "success": False,
                "output": "",
                "error": f"执行异常：{str(e)}",
                "return_code": -1,
            }


def check_syntax(code: str) -> dict:
    """
    检查 Python 代码的语法是否正确。

    使用 ast.parse 进行静态语法分析，不实际执行代码。

    Args:
        code: 待检查的 Python 源代码字符串。

    Returns:
        字典格式结果：
        {
            "valid": bool,        # 语法是否正确
            "error": str | None,  # 错误描述（如有）
            "line": int | None,   # 出错行号（如有）
        }
    """
    try:
        ast.parse(code)
        return {
            "valid": True,
            "error": None,
            "line": None,
        }
    except SyntaxError as e:
        return {
            "valid": False,
            "error": f"语法错误（第 {e.lineno} 行）：{e.msg}",
            "line": e.lineno,
        }


def _uses_interactive_input(code: str) -> bool:
    """
    检测代码中是否使用了交互式输入函数（input 等）。

    在线沙箱不支持交互式 stdin，使用这些函数的代码会直接返回错误提示，
    而不是等超时或抛出难以理解的 EOFError。

    Args:
        code: Python 源代码字符串。

    Returns:
        是否包含交互式输入调用。
    """
    try:
        tree = ast.parse(code)

        class InputVisitor(ast.NodeVisitor):
            def __init__(self):
                self.found = False

            def visit_Call(self, node):
                # 检查函数名是否为 input
                if isinstance(node.func, ast.Name) and node.func.id == "input":
                    self.found = True
                # 也检查 sys.stdin.readline 等
                elif isinstance(node.func, ast.Attribute):
                    attr_chain = []
                    obj = node.func
                    while isinstance(obj, ast.Attribute):
                        attr_chain.append(obj.attr)
                        obj = obj.value
                    if isinstance(obj, ast.Name):
                        attr_chain.append(obj.id)
                        full_name = ".".join(reversed(attr_chain))
                        if full_name in ("sys.stdin.read", "sys.stdin.readline", "sys.stdin.readlines"):
                            self.found = True
                self.generic_visit(node)

        visitor = InputVisitor()
        visitor.visit(tree)
        return visitor.found
    except SyntaxError:
        # 语法错误由 check_syntax 在前面已经处理，这里不应发生
        return False
