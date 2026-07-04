"""
练习题生成工具
基于 QwenLLM 根据知识点和难度生成练习题、提示和答案评估。
采用苏格拉底式引导，启发学生思考而非直接给出答案。
确保生成的代码完整可运行。
"""

import json
from typing import List, Optional

from backend.llm import QwenLLM
from backend.tools.code_validator import (
    check_code_completeness,
    auto_fix_code,
    generate_code_quality_prompt,
)

# 创建全局 LLM 实例
_llm = QwenLLM(temperature=0.8)


def generate_exercise(
    topic: str,
    difficulty: str = "medium",
    subject: str = "python",
    count: int = 1,
) -> dict:
    """
    根据知识点和难度生成练习题。

    Args:
        topic: 知识点名称（如 "递归"、"链表反转"、"二叉树遍历"）。
        difficulty: 难度等级，可选 "easy" / "medium" / "hard"。
        subject: 科目名称，用于调整题目风格。
        count: 生成题目数量，默认 1。

    Returns:
        字典格式结果：
        {
            "topic": str,
            "difficulty": str,
            "exercises": List[dict],  # 每个元素含 question / hint / answer
        }
    """
    difficulty_desc = {
        "easy": "简单（适合初学者，考察基础概念）",
        "medium": "中等（需要一定思考，综合多个知识点）",
        "hard": "困难（需要深入理解，可能涉及算法设计）",
    }

    diff_text = difficulty_desc.get(difficulty, difficulty_desc["medium"])

    system_prompt = f"""你是一位经验丰富的编程教师，擅长设计循序渐进的练习题。
{generate_code_quality_prompt()}
请严格按照要求的 JSON 格式返回结果，不要添加任何多余的文字说明。"""

    prompt = f"""请为「{subject}」科目的「{topic}」知识点出 {count} 道{diff_text}的练习题。

要求：
1. 题目要贴近实际应用场景
2. 每道题包含清晰的题目描述
3. hint（提示）要用苏格拉底式引导，给出思考方向但不直接透露答案
4. answer 给出参考答案和简要解析
5. **如果是编程题，answer 中的代码必须完整可运行**：
   - 包含所有必要的 import 语句
   - 函数/类定义完整，不可以使用 `...` 或 `pass` 占位
   - 必须包含示例调用（如 if __name__ == '__main__':）
   - 代码格式使用 ```python ... ``` 标记
   - 避免使用 input() 函数

请严格按以下 JSON 格式返回：
{{
    "exercises": [
        {{
            "question": "题目描述",
            "hint": "苏格拉底式提示（引导思考方向）",
            "answer": "参考答案与解析（含完整可运行代码）"
        }}
    ]
}}

请直接返回 JSON，不要添加 markdown 代码块标记或其他说明文字。"""

    try:
        response = _llm.invoke(prompt, system_prompt=system_prompt)

        # 尝试解析 JSON（兼容模型可能加了 markdown 标记的情况）
        cleaned = response.strip()
        if cleaned.startswith("```"):
            # 去掉 ```json ... ``` 包裹
            lines = cleaned.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            cleaned = "\n".join(lines)

        result = json.loads(cleaned)

        # 对每道练习题的答案进行代码验证和自动修复
        exercises = result.get("exercises", [])
        for ex in exercises:
            answer = ex.get("answer", "")
            if answer and ("```" in answer or "def " in answer or "import " in answer):
                # 提取并验证代码块
                import re
                code_blocks = re.findall(r"```(?:python)?\s*\n(.*?)```", answer, re.DOTALL)
                for code in code_blocks:
                    completeness = check_code_completeness(code.strip())
                    if not completeness["complete"]:
                        # 尝试自动修复
                        fix_result = auto_fix_code(code.strip())
                        if fix_result["fixed"]:
                            # 替换原代码块为修复后的版本
                            old_block = f"```python\n{code.strip()}\n```"
                            if old_block not in answer:
                                # 尝试匹配不带语言标记的代码块
                                old_block = f"```\n{code.strip()}\n```"
                            new_block = f"```python\n{fix_result['code']}\n```"
                            answer = answer.replace(old_block, new_block, 1)
                            ex["answer"] = answer

        return {
            "topic": topic,
            "difficulty": difficulty,
            "exercises": exercises,
        }

    except (json.JSONDecodeError, KeyError) as e:
        # JSON 解析失败时，返回原始文本作为单道题
        return {
            "topic": topic,
            "difficulty": difficulty,
            "exercises": [
                {
                    "question": response.strip(),
                    "hint": "请仔细阅读题目要求，从基础概念出发思考。",
                    "answer": "（答案生成异常，请重新生成）",
                }
            ],
        }
    except RuntimeError as e:
        return {
            "topic": topic,
            "difficulty": difficulty,
            "exercises": [],
            "error": f"LLM 调用失败：{str(e)}",
        }


def generate_hint(
    exercise: str,
    context: Optional[str] = None,
) -> str:
    """
    为一道练习题生成苏格拉底式提示（不直接给答案）。

    Args:
        exercise: 题目内容。
        context: 可选的上下文信息（如学生之前的尝试）。

    Returns:
        引导性提示文本。
    """
    system_prompt = """你是一位善于启发式教学的导师。
你的任务是通过提问和引导帮助学生自己找到答案，而不是直接告诉他们答案。
请使用苏格拉底式提问法：先指出问题的关键，然后用引导性问题帮助学生思考。"""

    context_text = f"\n\n学生之前的尝试或背景：\n{context}" if context else ""

    prompt = f"""请为以下题目生成一个苏格拉底式的提示，帮助学生思考解题方向，但不要直接给出答案。

题目：
{exercise}{context_text}

要求：
1. 用 2-3 句话引导思考
2. 至少包含一个引导性问题
3. 不要直接透露答案或关键代码
4. 语气友善、鼓励

请直接返回提示内容："""

    try:
        return _llm.invoke(prompt, system_prompt=system_prompt).strip()
    except RuntimeError as e:
        return f"提示生成失败：{str(e)}。建议：先回顾相关基础概念，再尝试分解问题。"


def evaluate_answer(
    question: str,
    student_answer: str,
    correct_answer: str,
) -> dict:
    """
    评估学生的答案。

    从正确性、完整性、代码质量等维度进行评估，
    给出改进建议和鼓励性反馈。

    Args:
        question: 原始题目。
        student_answer: 学生提交的答案。
        correct_answer: 标准答案。

    Returns:
        字典格式评估结果：
        {
            "score": int,            # 得分 0-100
            "is_correct": bool,      # 是否正确
            "feedback": str,         # 详细反馈
            "improvements": List[str], # 改进建议列表
            "encouragement": str,    # 鼓励性评语
        }
    """
    system_prompt = """你是一位耐心且公正的编程教师。
评估学生答案时，请做到：
1. 公正客观地评分
2. 指出具体的优点和不足
3. 给出可操作的改进建议
4. 始终给予鼓励，保持学生学习的积极性
请严格按 JSON 格式返回。"""

    prompt = f"""请评估以下学生答案：

【题目】
{question}

【标准答案】
{correct_answer}

【学生答案】
{student_answer}

请从以下维度评估：
- 正确性：答案是否正确或基本正确
- 完整性：是否完整解决了问题
- 代码质量（如适用）：代码是否清晰、高效、有良好注释

请严格按以下 JSON 格式返回：
{{
    "score": 85,
    "is_correct": true,
    "feedback": "详细的评估反馈...",
    "improvements": ["建议1", "建议2"],
    "encouragement": "鼓励性评语"
}}

请直接返回 JSON，不要添加 markdown 代码块标记或其他说明文字。"""

    try:
        response = _llm.invoke(prompt, system_prompt=system_prompt)

        # 清理可能的 markdown 包裹
        cleaned = response.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            cleaned = "\n".join(lines)

        result = json.loads(cleaned)

        return {
            "score": result.get("score", 0),
            "is_correct": result.get("is_correct", False),
            "feedback": result.get("feedback", ""),
            "improvements": result.get("improvements", []),
            "encouragement": result.get("encouragement", "继续努力，你一定可以的！"),
        }

    except (json.JSONDecodeError, KeyError):
        # JSON 解析失败时，返回基本评估
        return {
            "score": 0,
            "is_correct": False,
            "feedback": response.strip(),
            "improvements": ["请重新审视你的答案，对照标准答案检查。"],
            "encouragement": "不要气馁，再试一次！",
        }
    except RuntimeError as e:
        return {
            "score": 0,
            "is_correct": False,
            "feedback": f"评估失败：{str(e)}",
            "improvements": [],
            "encouragement": "请稍后重试。",
        }
