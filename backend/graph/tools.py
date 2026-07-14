"""
LangGraph 工具定义。

将项目已有的能力（RAG 检索、代码沙箱、练习题生成、答案评估）包装为
LangChain @tool，供各 specialist 子图通过真实的 tool calling 调用。
这同时修复了此前"MCP 工具只以文本注入、从不被 LLM 真正调用"的问题。
"""

import json
from typing import Dict, List

from langchain_core.tools import tool

# 由 main.py 在启动时通过 init_graph_globals 注入
_GLOBALS: Dict[str, object] = {
    "knowledge_base": None,
    "memory": None,
}


def init_graph_globals(knowledge_base=None, memory=None) -> None:
    """注入知识库与记忆实例（在 lifespan 中调用）。"""
    _GLOBALS["knowledge_base"] = knowledge_base
    _GLOBALS["memory"] = memory


# RAG 实际存在的科目集合（与 COURSE_DATA 对应）
_RAG_SUBJECTS = ("python", "data_structures")


@tool
def rag_search(query: str) -> str:
    """检索课程知识库，返回与问题相关的 Python / 数据结构课程内容片段。

    当学生问题涉及课本概念、语法、算法或定义时应当调用本工具，
    以保证回答基于权威课程资料而非凭空生成。
    """
    kb = _GLOBALS.get("knowledge_base")
    if kb is None:
        return json.dumps([], ensure_ascii=False)

    sources: List[Dict[str, str]] = []
    for subj in _RAG_SUBJECTS:
        if subj not in kb.list_subjects():
            continue
        try:
            hits = kb.hybrid_search(query, subj, 3)
        except Exception:
            hits = []
        for h in hits:
            sources.append({
                "topic": h.get("topic", ""),
                "content": (h.get("content", "") or "")[:600],
            })

    return json.dumps(sources, ensure_ascii=False)


@tool
def run_python_code(code: str) -> str:
    """在隔离沙箱中执行 Python 代码并返回标准输出或错误信息。

    用于验证学生提交的代码、运行示例代码，或演示算法运行结果。
    """
    from backend.tools import execute_python

    result = execute_python(code)
    if result.get("success"):
        out = result.get("output", "")
        return f"执行成功，输出：\n{out}" if out else "执行成功（无输出）。"
    return f"执行失败：\n{result.get('error', '未知错误')}"


@tool
def generate_practice(topic: str, difficulty: str = "medium", subject: str = "python", count: int = 1) -> str:
    """根据知识点生成练习题，返回题面与参考答案的 JSON 字符串。

    当需要根据学生薄弱点出题、或学生要求练习时使用。
    """
    from backend.tools import generate_exercise

    res = generate_exercise(topic=topic, difficulty=difficulty, subject=subject, count=count)
    return json.dumps(res, ensure_ascii=False)


@tool
def evaluate_practice(question: str, student_answer: str, correct_answer: str) -> str:
    """评估学生答案，返回包含得分与反馈的 JSON 字符串。

    当学生提交了某道题的解答、需要批改或诊断时使用。
    """
    from backend.tools import evaluate_answer

    res = evaluate_answer(
        question=question,
        student_answer=student_answer,
        correct_answer=correct_answer,
    )
    return json.dumps(res, ensure_ascii=False)
