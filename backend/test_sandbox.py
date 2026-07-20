"""
代码沙箱安全离线测试（无需 API Key / 网络）。

验证 execute_python 的沙箱守卫：
- 合法计算代码可正常执行；
- 危险模块（os / socket / urllib 等）导入被拦截；
- 动态执行内建（eval / exec / compile）被移除。

运行：
    cd <项目根目录>
    python backend/test_sandbox.py
"""

import sys
from pathlib import Path

# Windows: 强制 UTF-8 输出，避免 GBK 控制台打印 emoji 报 UnicodeEncodeError
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# 确保项目根目录在 Python 路径中
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.tools.code_executor import execute_python


def _run(name: str, code: str, expect_success: bool) -> bool:
    """执行一段代码并断言其成功/失败状态符合预期。"""
    result = execute_python(code, timeout=5)
    ok = result["success"] is expect_success
    status = "PASS" if ok else "FAIL"
    snippet = (result.get("error") or result.get("output") or "")[:80].replace("\n", " ")
    print(f"[{status}] {name}: success={result['success']} | {snippet}")
    return ok


def main() -> int:
    all_ok = True

    # 1. 合法代码应成功执行
    all_ok &= _run("安全代码（求和）", "print(sum(range(10)))", True)
    all_ok &= _run("安全代码（数学）", "import math\nprint(math.sqrt(16))", True)

    # 2. 命令执行类危险模块必须被拦截
    all_ok &= _run(
        "阻断 os.system",
        "import os\nos.system('echo PWNED')",
        False,
    )
    all_ok &= _run(
        "阻断 subprocess",
        "import subprocess\nsubprocess.run(['echo', 'PWNED'])",
        False,
    )

    # 3. 网络外联必须被拦截
    all_ok &= _run(
        "阻断 socket",
        "import socket\ns = socket.socket()\ns.connect(('1.2.3.4', 80))",
        False,
    )
    all_ok &= _run(
        "阻断 urllib 外联",
        "import urllib.request\nurllib.request.urlopen('http://example.com')",
        False,
    )

    # 4. 动态执行内建必须被移除
    all_ok &= _run("阻断 eval", "print(eval('1+1'))", False)
    all_ok &= _run("阻断 exec", "exec('import os')", False)

    print("\n" + ("✅ 全部沙箱安全用例通过" if all_ok else "❌ 存在未通过的用例"))
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
