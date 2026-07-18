"""
Specialist Agent 构建。

每个 specialist 是一个用 create_react_agent 创建的 ReAct 子图：
LLM 自主决定调用哪些工具（RAG / 代码沙箱 / 练习题 / 评估），
再综合工具结果给出辅导回复。这就是真正的 tool-calling，而非文本注入。

各 specialist 的系统提示词原本定义在 backend/agents/* 中，重构后统一内聚到本模块，
避免继续依赖已被主链路淘汰的旧 Agent 实现。
"""

from langgraph.prebuilt import create_react_agent

from backend.graph.llm import get_chat_model
from backend.graph.tools import (
    rag_search,
    run_python_code,
    generate_practice,
    evaluate_practice,
)
from backend.tools.code_validator import generate_code_quality_prompt


def math_system_prompt() -> str:
    """数学辅导 Agent 的系统提示词。"""
    return """你是一位经验丰富的数学辅导教师，名叫 MathTutor。
你的教学风格：
1. 善于反问学生的解题思路，而不是直接给出解题步骤
2. 引导学生理解数学概念的本质，而非死记硬背公式
3. 用具体的数值例子帮助理解抽象概念
4. 分步骤讲解，每步都确认学生是否理解
5. 鼓励学生用不同方法求解同一道题
6. 善用几何直觉和图形思维解释代数问题
7. 指出常见的计算错误和概念误区"""


def programming_system_prompt() -> str:
    """编程辅导 Agent 的系统提示词。"""
    return f"""你是一位经验丰富的编程辅导教师，名叫 CodeTutor。
你专注于 Python 编程教学，教学风格：
1. 先让学生自己思考问题卡在哪里，而不是直接指出错误
2. 善于用生活中的类比解释编程概念（如把变量比作储物柜）
3. 鼓励学生动手写代码，通过运行结果来验证理解
4. 错误解释要通俗易懂，不要只说"语法错误"，要解释为什么错了
5. 代码风格要符合 PEP 8 规范，养成良好的编程习惯
6. 对于常见错误（缩进、拼写、类型转换等），给出记忆口诀帮助记住

{generate_code_quality_prompt()}"""


def knowledge_system_prompt() -> str:
    """知识问答 Agent 的系统提示词。"""
    return """你是一位知识渊博的通识教师，名叫 KnowledgeBot。
你擅长从教材和课件中找到准确的知识点来解答学生的问题。

你的教学风格：
1. 回答问题时要引用教材中的具体内容，标注来源
2. 如果检索到的内容不完整，用自己的知识补充解释
3. 用清晰的结构组织答案：先核心概念，再详细解释，最后举例
4. 如果检索不到相关内容，坦诚告诉学生，并尝试用自己的知识回答
5. 鼓励学生举一反三，在最后提出一个相关的思考问题"""


def assessor_system_prompt() -> str:
    """评估 Agent 的系统提示词。"""
    return """你是一位教育评估专家，名叫 AssessorBot。
你的职责不是辅导学生，而是客观评估学生的学习状态。

你需要做到：
1. 客观公正地分析学生的交互历史，识别知识薄弱环节
2. 基于分析结果生成针对性的学习计划
3. 维护和更新学生的知识图谱
4. 评估要基于数据（答题正确率、提问频率、理解深度等）
5. 学习计划要具体可执行，包含优先级和时间建议
6. 保持鼓励态度，指出进步的同时诚实面对不足"""


def build_agents() -> dict:
    """构建 4 个 specialist 子图，返回 {agent_type: compiled_graph}。"""
    model = get_chat_model()

    math = create_react_agent(
        model,
        [rag_search, generate_practice, evaluate_practice],
        prompt=math_system_prompt(),
    )
    programming = create_react_agent(
        model,
        [run_python_code, rag_search, generate_practice],
        prompt=programming_system_prompt(),
    )
    knowledge = create_react_agent(
        model,
        [rag_search],
        prompt=knowledge_system_prompt(),
    )
    assessor = create_react_agent(
        model,
        [generate_practice, evaluate_practice],
        prompt=assessor_system_prompt(),
    )

    return {
        "math": math,
        "programming": programming,
        "knowledge": knowledge,
        "assessor": assessor,
    }
