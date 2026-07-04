"""
工具模块 —— 导出所有可用工具函数。
"""

from backend.tools.code_executor import execute_python, check_syntax
from backend.tools.exercise_generator import (
    generate_exercise,
    generate_hint,
    evaluate_answer,
)
from backend.tools.code_validator import (
    extract_code_blocks,
    check_code_completeness,
    auto_fix_code,
    validate_and_enhance_code,
    generate_code_quality_prompt,
)

__all__ = [
    # 代码执行工具
    "execute_python",
    "check_syntax",
    # 练习题生成工具
    "generate_exercise",
    "generate_hint",
    "evaluate_answer",
    # 代码验证与增强工具
    "extract_code_blocks",
    "check_code_completeness",
    "auto_fix_code",
    "validate_and_enhance_code",
    "generate_code_quality_prompt",
]
