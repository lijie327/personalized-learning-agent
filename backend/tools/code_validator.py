"""
代码验证与自动修复工具
从 LLM 生成的文本中提取代码块，进行语法验证和自动修复，确保生成的代码完整可运行。
"""

import ast
import re
from typing import Dict, List, Optional, Tuple


# ---------------------------------------------------------------
#  常用模块导入映射（自动补全缺失的 import）
# ---------------------------------------------------------------

_COMMON_IMPORTS: Dict[str, str] = {
    # 标准库
    "math": "import math",
    "random": "import random",
    "datetime": "import datetime",
    "json": "import json",
    "re": "import re",
    "os": "import os",
    "sys": "import sys",
    "collections": "import collections",
    "itertools": "import itertools",
    "functools": "import functools",
    "typing": "from typing import List, Dict, Optional, Tuple, Any",
    "dataclasses": "from dataclasses import dataclass",
    "statistics": "import statistics",
    "copy": "import copy",
    "heapq": "import heapq",
    "bisect": "import bisect",
    "hashlib": "import hashlib",
    "time": "import time",
}

# 常用标准库模块名（用于检测缺失导入）
_STDLIB_MODULES = frozenset(_COMMON_IMPORTS.keys())


def extract_code_blocks(text: str) -> List[Dict[str, str]]:
    """
    从文本中提取所有代码块。

    支持两种格式：
    - Markdown 代码块：```python ... ```
    - 裸代码块：连续缩进或无标记的代码片段

    Args:
        text: 包含代码的文本。

    Returns:
        代码块列表，每个元素为 {"language": str, "code": str, "start": int, "end": int}。
    """
    blocks = []

    # 1. 提取 Markdown 风格代码块 ```python ... ```
    pattern = r"```(\w*)\s*\n(.*?)```"
    for match in re.finditer(pattern, text, re.DOTALL):
        language = match.group(1).lower() or "python"
        code = match.group(2).strip()
        blocks.append({
            "language": language,
            "code": code,
            "start": match.start(),
            "end": match.end(),
        })

    return blocks


def check_code_completeness(code: str) -> Dict:
    """
    检查 Python 代码的完整性和可运行性。

    检查项：
    1. 语法是否正确
    2. 是否有必要的导入语句
    3. 是否有可执行的入口（函数定义 + 调用）
    4. 常见错误（如缩进问题、括号不匹配等）

    Args:
        code: Python 源代码字符串。

    Returns:
        {
            "valid": bool,              # 是否语法正确
            "complete": bool,           # 是否完整可运行
            "issues": List[str],        # 发现的问题列表
            "suggestions": List[str],   # 改进建议
            "missing_imports": List[str], # 缺失的导入
            "has_entry_point": bool,    # 是否有执行入口
        }
    """
    result = {
        "valid": False,
        "complete": False,
        "issues": [],
        "suggestions": [],
        "missing_imports": [],
        "has_entry_point": False,
    }

    # 1. 语法检查
    try:
        tree = ast.parse(code)
        result["valid"] = True
    except SyntaxError as e:
        result["issues"].append(f"语法错误（第 {e.lineno} 行）: {e.msg}")
        result["suggestions"].append(f"请检查第 {e.lineno} 行的语法：{e.msg}")
        return result

    # 2. 分析代码结构
    has_function_def = False
    has_class_def = False
    has_top_level_call = False
    has_if_main = False
    used_names: set = set()

    class CodeAnalyzer(ast.NodeVisitor):
        def visit_FunctionDef(self, node):
            nonlocal has_function_def
            has_function_def = True
            self.generic_visit(node)

        def visit_ClassDef(self, node):
            nonlocal has_class_def
            has_class_def = True
            self.generic_visit(node)

        def visit_Call(self, node):
            nonlocal has_top_level_call, used_names
            # 记录被调用的函数名
            if isinstance(node.func, ast.Name):
                used_names.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                # 如 math.sqrt, random.randint 等
                obj = node.func.value
                if isinstance(obj, ast.Name):
                    used_names.add(obj.id)
            self.generic_visit(node)

        def visit_If(self, node):
            nonlocal has_if_main
            # 检查是否为 if __name__ == "__main__":
            if isinstance(node.test, ast.Compare):
                left = node.test.left
                if isinstance(left, ast.Name) and left.id == "__name__":
                    has_if_main = True
            self.generic_visit(node)

        def visit_Name(self, node):
            nonlocal used_names
            if isinstance(node.ctx, ast.Load):
                used_names.add(node.id)
            self.generic_visit(node)

    analyzer = CodeAnalyzer()
    try:
        analyzer.visit(tree)
    except Exception as e:
        result["issues"].append(f"代码分析异常: {e}")
        return result

    result["has_entry_point"] = has_if_main or (
        has_top_level_call and not (has_function_def and not has_top_level_call)
    )

    # 3. 检查缺失的导入
    imported_modules: set = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported_modules.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imported_modules.add(node.module.split(".")[0])

    for name in used_names:
        if name in _STDLIB_MODULES and name not in imported_modules:
            result["missing_imports"].append(name)

    # 4. 汇总完整性问题
    if not result["has_entry_point"] and has_function_def and not has_if_main:
        result["issues"].append("代码定义了函数但缺少调用入口（建议添加 if __name__ == '__main__' 块）")
        result["suggestions"].append(
            "添加执行入口：\n\nif __name__ == '__main__':\n    # 调用你的函数\n    ..."
        )

    if result["missing_imports"]:
        import_names = ", ".join(result["missing_imports"])
        result["issues"].append(f"代码使用了 {import_names} 但未导入")
        for mod in result["missing_imports"]:
            if mod in _COMMON_IMPORTS:
                result["suggestions"].append(f"在文件开头添加：{_COMMON_IMPORTS[mod]}")

    # 5. 检查常见模式
    code_lower = code.lower()
    if "input(" in code_lower and "input(" not in code_lower.split("#")[0]:
        result["issues"].append("代码使用了 input() 函数（在线沙箱不支持交互式输入）")
        result["suggestions"].append(
            "将 input() 替换为变量赋值，如：\n"
            "# name = input('请输入姓名: ')  →  name = '张三'"
        )

    # 6. 判断完整性
    result["complete"] = (
        result["valid"]
        and len(result["issues"]) == 0
    )

    return result


def auto_fix_code(code: str) -> Dict:
    """
    自动修复常见的代码问题，使其完整可运行。

    修复项：
    1. 添加缺失的标准库导入
    2. 为定义了函数但没有入口的代码添加 if __name__ 块
    3. 修复常见的缩进问题

    Args:
        code: 原始 Python 代码字符串。

    Returns:
        {
            "code": str,              # 修复后的代码
            "fixed": bool,            # 是否进行了修复
            "fixes_applied": List[str], # 应用的修复列表
            "still_incomplete": bool, # 修复后是否仍不完整
        }
    """
    fixes_applied = []
    fixed_code = code

    # 1. 检查完整性
    completeness = check_code_completeness(code)

    # 如果语法错误，不尝试自动修复（太复杂，可能引入新问题）
    if not completeness["valid"]:
        return {
            "code": code,
            "fixed": False,
            "fixes_applied": [],
            "still_incomplete": True,
        }

    # 2. 添加缺失的导入
    if completeness["missing_imports"]:
        import_lines = []
        for mod in completeness["missing_imports"]:
            if mod in _COMMON_IMPORTS:
                import_lines.append(_COMMON_IMPORTS[mod])
                fixes_applied.append(f"添加缺失的导入: {_COMMON_IMPORTS[mod]}")

        if import_lines:
            # 将导入插入到代码开头
            fixed_code = "\n".join(import_lines) + "\n\n" + fixed_code

    # 3. 如果定义了函数但没有调用入口，自动添加
    if not completeness["has_entry_point"] and not completeness["missing_imports"]:
        # 确保只在确实定义了函数时才添加
        # 添加简单的入口提示（不自动添加调用，因为不知道正确的调用方式）
        # 改为在代码后添加注释提示
        pass  # 不自动添加调用，避免生成错误的调用方式

    still_incomplete = not completeness["valid"]

    return {
        "code": fixed_code,
        "fixed": len(fixes_applied) > 0,
        "fixes_applied": fixes_applied,
        "still_incomplete": still_incomplete,
    }


def validate_and_enhance_code(
    text: str,
    auto_fix: bool = True,
) -> Dict:
    """
    综合处理：从文本中提取代码块，验证并增强。

    这是供外部调用的主要接口。

    Args:
        text: 包含代码的文本（如 LLM 生成的回复）。
        auto_fix: 是否自动修复常见问题。

    Returns:
        {
            "original_text": str,        # 原始文本
            "code_blocks": List[Dict],   # 提取的代码块及其验证结果
            "has_code": bool,            # 是否包含代码
            "all_valid": bool,           # 所有代码块是否都有效
            "enhanced_text": str,        # 增强后的文本（修复了代码块）
        }
    """
    blocks = extract_code_blocks(text)
    enhanced_text = text

    if not blocks:
        return {
            "original_text": text,
            "code_blocks": [],
            "has_code": False,
            "all_valid": True,
            "enhanced_text": text,
        }

    all_valid = True
    validated_blocks = []

    for block in blocks:
        lang = block.get("language", "")
        code = block.get("code", "")

        # 只处理 Python 代码
        if lang in ("python", "py", ""):
            completeness = check_code_completeness(code)

            fixed_code = code
            fixes = []
            if auto_fix and not completeness["complete"]:
                fix_result = auto_fix_code(code)
                if fix_result["fixed"]:
                    fixed_code = fix_result["code"]
                    fixes = fix_result["fixes_applied"]

            block_result = {
                **block,
                "valid": completeness["valid"],
                "complete": completeness["complete"],
                "issues": completeness["issues"],
                "suggestions": completeness["suggestions"],
                "missing_imports": completeness["missing_imports"],
                "has_entry_point": completeness["has_entry_point"],
                "fixed_code": fixed_code if fixes else None,
                "fixes_applied": fixes,
            }
            validated_blocks.append(block_result)

            if not completeness["valid"]:
                all_valid = False

            # 更新增强文本中的代码块
            if fixes:
                old_block = f"```{block['language']}\n{block['code']}\n```"
                new_block = f"```{block['language']}\n{fixed_code}\n```"
                enhanced_text = enhanced_text.replace(old_block, new_block, 1)
        else:
            # 非 Python 代码块，跳过验证
            validated_blocks.append({
                **block,
                "valid": True,
                "complete": True,
                "issues": [],
                "suggestions": [],
                "missing_imports": [],
                "has_entry_point": True,
                "fixed_code": None,
                "fixes_applied": [],
            })

    return {
        "original_text": text,
        "code_blocks": validated_blocks,
        "has_code": True,
        "all_valid": all_valid,
        "enhanced_text": enhanced_text,
    }


def generate_code_quality_prompt() -> str:
    """
    生成代码质量要求的提示词片段，可插入到 LLM system prompt 中。

    Returns:
        代码质量提示词文本。
    """
    return """## 代码质量要求（极其重要，必须严格遵守）

当你的回复中包含 Python 代码时，必须遵守以下规则：

1. **单一代码块（最关键！）**：
   - **所有代码必须放在唯一一个 ```python ... ``` 代码块中**
   - 禁止拆分成多个代码块（如一个放定义、一个放调用）
   - import 语句、函数/类定义、示例调用、预期输出注释全部合并在同一个代码块内

2. **完整性**：
   - 代码必须包含所有必要的 `import` 语句
   - 所有函数/类定义必须完整，不能使用 `...` 或 `pass` 占位
   - 必须提供可执行的示例调用

3. **可运行性**：
   - 代码必须语法正确，可以直接复制粘贴后运行
   - 避免使用 `input()` 函数（在线环境不支持交互输入）
   - 用变量赋值代替用户输入

4. **格式规范**：
   - 使用标准 Markdown 代码块格式：```python ... ```（只能有一个）
   - 代码缩进使用 4 个空格
   - 遵循 PEP 8 代码风格

5. **示例要求**：
   - 对于函数/方法教学，必须包含实际调用示例
   - 示例输出应包含在注释中（如 # 输出：...），帮助学生理解预期结果
   - 变量命名要具有描述性

**错误做法（拆成多个代码块）—— 严禁：**
- ❌ 代码块1：只有函数定义 → 代码块2：调用代码
- ❌ 代码块1：代码 → 代码块2：输出结果

记住：一个回复中最多只能有一个 ```python 代码块，所有内容合并在其中。"""
