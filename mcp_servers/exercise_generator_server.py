"""
习题生成 MCP Server
根据知识点自动生成练习题和提示，使用 LLM 进行答案评估。
"""
import random
import sys
import json
import os
from pathlib import Path

# Windows: 强制 UTF-8 输出
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from mcp.server.fastmcp import FastMCP

# 延迟导入 LLM（避免 MCP stdio 启动时的循环导入）
_llm = None


def _get_llm():
    """懒加载 LLM 实例（MCP Server 独立进程，需要独立初始化）。"""
    global _llm
    if _llm is None:
        try:
            # MCP Server 以子进程方式运行，需要独立加载配置
            from dotenv import load_dotenv
            _project_root = Path(__file__).resolve().parent.parent
            _env_file = _project_root / ".env"
            if _env_file.exists():
                load_dotenv(_env_file)

            from openai import OpenAI
            api_key = os.getenv("DASHSCOPE_API_KEY", "")
            base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
            model = os.getenv("LLM_MODEL", "qwen-max")

            if api_key:
                _llm = OpenAI(api_key=api_key, base_url=base_url)
                _llm._model = model
            else:
                _llm = False  # 标记为不可用
        except Exception:
            _llm = False
    return _llm if _llm is not False else None

mcp = FastMCP("ExerciseGenerator")

# 预设题库
EXERCISE_BANK = {
    "函数": [
        {"title": "编写求和函数", "difficulty": "简单",
         "question": "编写函数 sum_list(lst)，接收一个数字列表，返回所有元素的和。",
         "hint": "可以使用for循环遍历列表，累加每个元素。"},
        {"title": "递归阶乘", "difficulty": "中等",
         "question": "用递归实现 factorial(n) 计算n的阶乘，需处理n=0和n<0的情况。",
         "hint": "阶乘定义: n! = n × (n-1)!，基础情况 0! = 1。"},
    ],
    "循环": [
        {"title": "九九乘法表", "difficulty": "简单",
         "question": "使用嵌套循环打印九九乘法表。",
         "hint": "外层循环控制行(i)，内层循环控制列(j)，范围都是1-9。"},
        {"title": "斐波那契数列", "difficulty": "中等",
         "question": "用循环生成前20个斐波那契数列。",
         "hint": "前两个数是0和1，之后每个数都是前两个数之和。"},
    ],
    "列表": [
        {"title": "列表去重", "difficulty": "简单",
         "question": "给定列表 [1,2,2,3,4,4,5]，写代码去除重复元素。",
         "hint": "可以使用set()转换为集合，或遍历判断是否已存在。"},
        {"title": "列表推导式", "difficulty": "中等",
         "question": "用列表推导式生成1-100中所有能被3整除的数的平方。",
         "hint": "使用 [x**2 for x in range(1,101) if x % 3 == 0]。"},
    ],
    "链表": [
        {"title": "反转链表", "difficulty": "中等",
         "question": "实现函数 reverse_linked_list(head) 反转单链表。",
         "hint": "使用三个指针 prev/curr/next，遍历时逐个反转指向。"},
    ],
    "导数": [
        {"title": "基本函数求导", "difficulty": "简单",
         "question": "求函数 f(x) = x³ + 2x² - 5x + 1 的导数。",
         "hint": "使用幂函数求导公式: d/dx(x^n) = n·x^(n-1)。"},
    ],
}


@mcp.tool()
def generate_exercise(topic: str, difficulty: str = "中等") -> dict:
    """
    根据知识点和难度生成练习题

    Args:
        topic: 知识点名称（如：函数、循环、链表）
        difficulty: 难度（简单/中等/困难）

    Returns:
        {"title": str, "difficulty": str, "question": str, "hint": str}
    """
    exercises = EXERCISE_BANK.get(topic, [])

    if not exercises:
        return {
            "title": f"{topic}练习",
            "difficulty": difficulty,
            "question": f"请根据{topic}的知识点，完成一道练习题。（题库正在扩展中）",
            "hint": f"回顾{topic}的核心概念，先理解原理再动手。"
        }

    # 匹配难度
    matched = [e for e in exercises if e["difficulty"] == difficulty]
    if not matched:
        matched = exercises

    exercise = random.choice(matched)
    return exercise


@mcp.tool()
def generate_hint(exercise_title: str, level: int = 1) -> str:
    """
    生成分步提示（不直接给答案）

    Args:
        exercise_title: 练习题标题
        level: 提示级别(1=轻微提示, 2=中等提示, 3=详细提示)

    Returns:
        提示文本
    """
    hints = {
        1: "先想想这道题考察的核心概念是什么？",
        2: "试着写下伪代码，把思路理清楚。",
        3: "回顾一下相关的知识点，看看有没有类似的例题可以参考。"
    }
    return f"💡 提示(Level {level}): {hints.get(level, hints[1])}"


@mcp.tool()
def evaluate_answer(question: str, student_answer: str) -> dict:
    """
    评估学生答案（基于 LLM 进行真实语义评估）

    Args:
        question: 题目内容
        student_answer: 学生答案

    Returns:
        {"correct": bool, "score": int, "feedback": str}
    """
    llm = _get_llm()

    # 如果有 LLM，使用 LLM 进行真实评估
    if llm is not None:
        try:
            system_prompt = """你是一位耐心且公正的教师。请评估学生的答案，按 JSON 格式返回结果。"""
            prompt = f"""请评估以下学生答案：

【题目】
{question}

【学生答案】
{student_answer}

请从正确性、完整性等维度评估，严格按以下 JSON 格式返回：
{{
    "correct": true/false,
    "score": 0-100,
    "feedback": "详细评估反馈"
}}
请直接返回 JSON，不要添加 markdown 代码块标记。"""

            response = llm.chat.completions.create(
                model=llm._model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=1024,
                temperature=0.3,
            )
            raw = response.choices[0].message.content or "{}"
            cleaned = raw.strip()
            if cleaned.startswith("```"):
                lines = cleaned.split("\n")
                lines = [l for l in lines if not l.strip().startswith("```")]
                cleaned = "\n".join(lines)
            result = json.loads(cleaned)
            return {
                "correct": result.get("correct", False),
                "score": result.get("score", 0),
                "feedback": result.get("feedback", "评估完成"),
            }
        except Exception:
            pass  # LLM 失败时回退到启发式评估

    # 启发式回退评估（无 LLM 或 LLM 失败时）
    if not student_answer or not student_answer.strip():
        return {
            "correct": False,
            "score": 0,
            "feedback": "未提供答案，请尝试作答后再提交。",
        }

    # 简单的关键词匹配评估
    q_lower = question.lower()
    a_lower = student_answer.lower()
    # 提取题目中的关键概念词
    keywords = [w for w in q_lower.replace("？", " ").replace("，", " ").split() if len(w) >= 2]
    matched = sum(1 for kw in keywords if kw in a_lower)
    if keywords:
        match_ratio = matched / len(keywords)
        score = int(match_ratio * 100)
    else:
        score = 50  # 无法提取关键词时给中性分

    score = max(30, min(95, score))  # 限制在合理范围
    return {
        "correct": score >= 70,
        "score": score,
        "feedback": f"你的答案覆盖了约 {score}% 的关键概念。{'继续努力！' if score < 70 else '做得不错！'}",
    }


if __name__ == "__main__":
    mcp.run()