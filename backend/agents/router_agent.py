"""
路由 Agent 模块
负责分析学生问题，将其分类并路由到最合适的教学 Agent。
"""

import json
from typing import Dict, List, Optional

from backend.llm import QwenLLM
from backend.models import AgentType


class RouterAgent:
    """
    路由 Agent：分析学生问题并决定交给哪个专业 Agent 处理。

    综合考虑：
    - 问题本身的学科领域
    - 学生的薄弱知识点
    - 当前会话上下文
    """

    # 学科 → Agent 类型映射
    SUBJECT_AGENT_MAP: Dict[str, AgentType] = {
        "python": AgentType.PROGRAMMING,
        "programming": AgentType.PROGRAMMING,
        "java": AgentType.PROGRAMMING,
        "c++": AgentType.PROGRAMMING,
        "c": AgentType.PROGRAMMING,
        "javascript": AgentType.PROGRAMMING,
        "数学": AgentType.MATH,
        "math": AgentType.MATH,
        "物理": AgentType.MATH,
        "线性代数": AgentType.MATH,
        "概率论": AgentType.MATH,
        "微积分": AgentType.MATH,
        "data_structures": AgentType.KNOWLEDGE,
        "操作系统": AgentType.KNOWLEDGE,
        "计算机网络": AgentType.KNOWLEDGE,
        "database": AgentType.KNOWLEDGE,
    }

    def __init__(self):
        self.llm = QwenLLM(temperature=0.3)  # 路由需要更确定性的输出

    # ------------------------------------------------------------------
    #  核心分类方法
    # ------------------------------------------------------------------

    def classify(
        self,
        question: str,
        student_profile: Optional[Dict] = None,
        chat_history: Optional[List[Dict]] = None,
    ) -> Dict:
        """
        分析学生问题，返回分类结果。

        Args:
            question: 学生提出的问题文本。
            student_profile: 学生画像（可选），含 weak_points 等信息。
            chat_history: 最近的对话历史，用于理解模糊的跟进问题。

        Returns:
            {
                "subject": str,             # 识别的学科
                "agent_type": AgentType,    # 路由到的 Agent 类型
                "confidence": float,        # 置信度 0-1
                "suggested_tools": List[str], # 建议使用的工具
                "reasoning": str,           # 路由推理说明
            }
        """
        profile_context = self._build_profile_context(student_profile)
        history_context = self._build_history_context(chat_history)

        system_prompt = """你是一个教育系统的智能路由分类器。
你的任务是分析学生的问题，判断它属于哪个学科领域，应该交给哪种类型的辅导Agent处理。

可用的Agent类型：
- math: 数学、物理、逻辑推理类问题
- programming: 编程、代码调试、算法实现类问题
- knowledge: 课本知识、概念理解、理论问答类问题
- assessor: 学习评估、知识点检测、薄弱环节分析类请求

请严格按JSON格式返回，不要添加任何额外文字。"""

        prompt = f"""请分析以下学生问题并分类：

学生问题：「{question}」
{profile_context}{history_context}

请严格按以下 JSON 格式返回：
{{
    "subject": "识别出的学科（如 python / 数学 / data_structures）",
    "agent_type": "math / programming / knowledge / assessor",
    "confidence": 0.95,
    "suggested_tools": ["工具名1", "工具名2"],
    "reasoning": "简要说明为什么选择该Agent"
}}

请直接返回 JSON，不要添加 markdown 代码块标记。"""

        try:
            response = self.llm.invoke(prompt, system_prompt=system_prompt)
            result = self._parse_response(response)

            # 确保 agent_type 是有效的枚举值
            try:
                result["agent_type"] = AgentType(result["agent_type"])
            except (ValueError, KeyError):
                result["agent_type"] = AgentType.KNOWLEDGE

            return result

        except (json.JSONDecodeError, RuntimeError):
            # LLM 调用失败时使用规则兜底
            return self._rule_based_classify(question, student_profile)

    async def aclassify(
        self,
        question: str,
        student_profile: Optional[Dict] = None,
        chat_history: Optional[List[Dict]] = None,
    ) -> Dict:
        """
        异步版本的 classify：使用异步 LLM 调用，避免阻塞事件循环。
        逻辑与 classify 完全一致，仅 LLM 调用改为 await。
        """
        profile_context = self._build_profile_context(student_profile)
        history_context = self._build_history_context(chat_history)

        system_prompt = """你是一个教育系统的智能路由分类器。
你的任务是分析学生的问题，判断它属于哪个学科领域，应该交给哪种类型的辅导Agent处理。

可用的Agent类型：
- math: 数学、物理、逻辑推理类问题
- programming: 编程、代码调试、算法实现类问题
- knowledge: 课本知识、概念理解、理论问答类问题
- assessor: 学习评估、知识点检测、薄弱环节分析类请求

请严格按JSON格式返回，不要添加任何额外文字。"""

        prompt = f"""请分析以下学生问题并分类：

学生问题：「{question}」
{profile_context}{history_context}

请严格按以下 JSON 格式返回：
{{
    "subject": "识别出的学科（如 python / 数学 / data_structures）",
    "agent_type": "math / programming / knowledge / assessor",
    "confidence": 0.95,
    "suggested_tools": ["工具名1", "工具名2"],
    "reasoning": "简要说明为什么选择该Agent"
}}

请直接返回 JSON，不要添加 markdown 代码块标记。"""

        try:
            response = await self.llm.ainvoke(prompt, system_prompt=system_prompt)
            result = self._parse_response(response)

            # 确保 agent_type 是有效的枚举值
            try:
                result["agent_type"] = AgentType(result["agent_type"])
            except (ValueError, KeyError):
                result["agent_type"] = AgentType.KNOWLEDGE

            return result

        except (json.JSONDecodeError, RuntimeError):
            # LLM 调用失败时使用规则兜底
            return self._rule_based_classify(question, student_profile)

    # ------------------------------------------------------------------
    #  辅助方法
    # ------------------------------------------------------------------

    def _build_profile_context(self, profile: Optional[Dict]) -> str:
        """根据学生画像构造上下文描述。"""
        if not profile:
            return ""

        weak_points = profile.get("weak_points", [])
        if not weak_points:
            return ""

        weak_str = "、".join(weak_points[:5])
        return f"""
该学生的薄弱知识点：{weak_str}
请优先将相关问题的路由考虑到学生需要加强的方向。"""

    @staticmethod
    def _build_history_context(chat_history: Optional[List[Dict]]) -> str:
        """根据最近的对话历史构造上下文，帮助理解跟进问题。"""
        if not chat_history:
            return ""

        # 只取最近 3 轮（6 条消息）来推断当前话题
        recent = chat_history[-6:]
        lines = []
        for msg in recent:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            # 截断长消息
            short = content[:100] + "..." if len(content) > 100 else content
            lines.append(f"[{role}]: {short}")

        if not lines:
            return ""

        return f"""
最近的对话历史（用于理解当前问题的上下文）：
{chr(10).join(lines)}"""

    def _parse_response(self, response: str) -> Dict:
        """解析 LLM 返回的 JSON 结果。"""
        cleaned = response.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            cleaned = "\n".join(lines)

        result = json.loads(cleaned)

        # 确保必要字段存在
        result.setdefault("subject", "general")
        result.setdefault("agent_type", "knowledge")
        result.setdefault("confidence", 0.5)
        result.setdefault("suggested_tools", [])
        result.setdefault("reasoning", "")

        # 根据 agent_type 推荐工具
        if not result["suggested_tools"]:
            result["suggested_tools"] = self._suggest_tools(result["agent_type"])

        return result

    def _suggest_tools(self, agent_type: str) -> List[str]:
        """根据 Agent 类型推荐工具。"""
        tool_map = {
            "programming": ["execute_python", "check_syntax", "generate_exercise"],
            "math": ["generate_exercise", "evaluate_answer"],
            "knowledge": ["knowledge_search"],
            "assessor": ["generate_exercise", "evaluate_answer"],
        }
        return tool_map.get(agent_type, [])

    def _rule_based_classify(
        self,
        question: str,
        student_profile: Optional[Dict] = None,
    ) -> Dict:
        """
        基于关键词规则的兜底分类。
        当 LLM 调用失败时使用。
        """
        q = question.lower()

        # 编程关键词
        code_keywords = [
            "代码", "编程", "函数", "变量", "循环", "bug", "报错",
            "python", "java", "def ", "class ", "import", "print(",
            "调试", "debug", "算法", "递归", "链表", "树",
        ]
        if any(kw in q for kw in code_keywords):
            return {
                "subject": "python" if "python" in q else "programming",
                "agent_type": AgentType.PROGRAMMING,
                "confidence": 0.7,
                "suggested_tools": ["execute_python", "check_syntax"],
                "reasoning": "检测到编程相关关键词（规则兜底）",
            }

        # 数学关键词
        math_keywords = [
            "方程", "求解", "证明", "微积分", "矩阵", "概率",
            "导数", "积分", "极限", "公式", "计算",
        ]
        if any(kw in q for kw in math_keywords):
            return {
                "subject": "math",
                "agent_type": AgentType.MATH,
                "confidence": 0.7,
                "suggested_tools": ["generate_exercise", "evaluate_answer"],
                "reasoning": "检测到数学相关关键词（规则兜底）",
            }

        # 评估请求关键词
        if any(kw in q for kw in ["评估", "测试", "测评", "检查我的水平", "薄弱点", "分析"]):
            return {
                "subject": "assessment",
                "agent_type": AgentType.ASSESSOR,
                "confidence": 0.7,
                "suggested_tools": ["generate_exercise", "evaluate_answer"],
                "reasoning": "检测到评估相关关键词（规则兜底）",
            }

        # 考虑学生薄弱点
        if student_profile:
            weak_points = student_profile.get("weak_points", [])
            for wp in weak_points:
                if wp.lower() in q:
                    subject = self._weak_point_to_subject(wp)
                    agent_type = self.SUBJECT_AGENT_MAP.get(subject, AgentType.KNOWLEDGE)
                    return {
                        "subject": subject,
                        "agent_type": agent_type,
                        "confidence": 0.6,
                        "suggested_tools": self._suggest_tools(agent_type.value),
                        "reasoning": f"匹配到学生薄弱点 '{wp}'（规则兜底）",
                    }

        # 默认路由到知识 Agent
        return {
            "subject": "general",
            "agent_type": AgentType.KNOWLEDGE,
            "confidence": 0.4,
            "suggested_tools": ["knowledge_search"],
            "reasoning": "无法明确分类，默认使用知识 Agent（规则兜底）",
        }

    @staticmethod
    def _weak_point_to_subject(weak_point: str) -> str:
        """将薄弱知识点映射到科目。"""
        wp = weak_point.lower()
        if any(kw in wp for kw in ["变量", "函数", "类", "循环", "python"]):
            return "python"
        if any(kw in wp for kw in ["数组", "链表", "栈", "队列", "树"]):
            return "data_structures"
        if any(kw in wp for kw in ["方程", "积分", "矩阵"]):
            return "math"
        return "general"
