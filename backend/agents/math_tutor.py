"""
数学辅导 Agent 模块
专注于数学教学，提供苏格拉底式引导、分步提示和练习题生成。
"""

from typing import Any, Callable, Dict, List, Optional

from backend.agents.base_tutor import BaseTutor
from backend.tools import generate_exercise, evaluate_answer


class MathTutor(BaseTutor):
    """
    数学辅导 Agent。

    继承 BaseTutor，专注数学教学：
    - 苏格拉底式引导：反问解题思路，逐步引导
    - 分步提示：hint level 1-3，逐步揭示思路
    - 练习题生成：根据知识点和难度生成数学练习
    - 答案评估：多维度评估学生解题过程
    """

    def __init__(
        self,
        name: str = "MathTutor",
        tools: Optional[List[Callable]] = None,
        mcp_tools: Optional[List] = None,
        system_prompt: Optional[str] = None,
        memory: Optional[Any] = None,
    ):
        default_tools = [generate_exercise, evaluate_answer]
        super().__init__(
            name=name,
            subject="数学",
            tools=tools or default_tools,
            mcp_tools=mcp_tools or [],
            system_prompt=system_prompt or self._math_system_prompt(),
            memory=memory,
        )

    # ------------------------------------------------------------------
    #  系统提示词
    # ------------------------------------------------------------------

    @staticmethod
    def _math_system_prompt() -> str:
        return """你是一位经验丰富的数学辅导教师，名叫 MathTutor。
你的教学风格：
1. 善于反问学生的解题思路，而不是直接给出解题步骤
2. 引导学生理解数学概念的本质，而非死记硬背公式
3. 用具体的数值例子帮助理解抽象概念
4. 分步骤讲解，每步都确认学生是否理解
5. 鼓励学生用不同方法求解同一道题
6. 善用几何直觉和图形思维解释代数问题
7. 指出常见的计算错误和概念误区"""

    # ------------------------------------------------------------------
    #  苏格拉底式数学引导
    # ------------------------------------------------------------------

    def socratic_guide(self, question: str, context: Optional[str] = None) -> str:
        """
        数学特有的苏格拉底式引导。

        反问学生的解题思路（"你打算从哪里开始？"、"这道题和之前做过的哪道题类似？"），
        引导学生自己找到解题方向。
        """
        context_text = f"\n\n之前的对话背景：\n{context}" if context else ""

        prompt = f"""学生在数学学习中问了以下问题：
「{question}」{context_text}

请用数学教学中的苏格拉底式方法回应：
1. 问学生"你打算从哪里开始思考？"或"这道题给了你什么信息？"
2. 引导学生识别题目中的已知条件和未知量
3. 问"这道题和你之前做过的哪道题类似？有什么相同和不同？"
4. 如果学生毫无头绪，给一个非常小的切入点（如"先试试把已知条件列出来"）
5. 绝对不要直接给出完整的解题步骤
6. 用鼓励的语气，数学很难，但慢慢想就能想通

请直接输出引导回复："""

        return self.execute(
            messages=[
                {"role": "system", "content": self._system_prompt},
                {"role": "user", "content": prompt},
            ]
        )

    # ------------------------------------------------------------------
    #  分步提示系统（Hint Level 1-3）
    # ------------------------------------------------------------------

    def generate_hints(
        self,
        question: str,
        correct_answer: Optional[str] = None,
        student_attempt: Optional[str] = None,
    ) -> Dict[str, str]:
        """
        生成 3 个级别的分步提示。

        Hint Level 1: 最轻的引导（指出思路方向，不透露解法）
        Hint Level 2: 中等提示（给出关键公式或定理名称）
        Hint Level 3: 较强的提示（给出第一步具体操作，但不完整解题）

        Args:
            question: 数学题目。
            correct_answer: 标准答案（可选）。
            student_attempt: 学生的尝试（可选）。

        Returns:
            {
                "hint_1": str,  # 轻度引导
                "hint_2": str,  # 中等提示
                "hint_3": str,  # 较强提示
            }
        """
        attempt_context = ""
        if student_attempt:
            attempt_context = f"\n\n学生目前的尝试：\n{student_attempt}"

        answer_context = ""
        if correct_answer:
            answer_context = f"\n\n正确答案是：{correct_answer}（仅供你参考，不要直接透露给学生）"

        prompt = f"""请为以下数学题目生成 3 个级别的分步提示：

题目：{question}{answer_context}{attempt_context}

要求：
- hint_1（轻度引导）：只指出思考方向，如"想想这个公式和什么类似"。
  不要给出具体的公式或数字，帮助学生自己找到方向。

- hint_2（中等提示）：给出关键信息，如具体的定理名称或公式方向，
  但不展示完整的代入过程。

- hint_3（较强提示）：给出第一步的具体操作和计算，
  但不要完成全部解题过程，留给学生继续完成。

请严格按以下 JSON 格式返回：
{
    "hint_1": "轻度引导",
    "hint_2": "中等提示",
    "hint_3": "较强提示"
}

请直接返回 JSON，不要添加 markdown 代码块标记。"""

        try:
            import json

            response = self.execute(
                messages=[
                    {"role": "system", "content": self._system_prompt},
                    {"role": "user", "content": prompt},
                ]
            )

            cleaned = response.strip()
            if cleaned.startswith("```"):
                lines = cleaned.split("\n")
                lines = [l for l in lines if not l.strip().startswith("```")]
                cleaned = "\n".join(lines)

            result = json.loads(cleaned)
            return {
                "hint_1": result.get("hint_1", "请仔细阅读题目，想想已知条件能告诉你什么。"),
                "hint_2": result.get("hint_2", "回顾一下相关的公式或定理。"),
                "hint_3": result.get("hint_3", "试着先把已知条件列出来。"),
            }

        except (json.JSONDecodeError, RuntimeError):
            return {
                "hint_1": "请仔细阅读题目，想想已知条件能告诉你什么。",
                "hint_2": "回顾一下学过的相关公式或定理，哪个可以用在这道题上？",
                "hint_3": "试着先把已知条件都列出来，然后想想第一步可以做什么。",
            }

    def get_hint(
        self,
        question: str,
        level: int = 1,
        student_attempt: Optional[str] = None,
    ) -> str:
        """
        获取指定级别的提示。

        Args:
            question: 数学题目。
            level: 提示级别，1（轻度）/ 2（中等）/ 3（较强）。
            student_attempt: 学生的尝试（可选）。

        Returns:
            对应级别的提示文本。
        """
        level = max(1, min(3, level))  # 限制在 1-3
        hints = self.generate_hints(question, student_attempt=student_attempt)
        return hints[f"hint_{level}"]

    # ------------------------------------------------------------------
    #  解题思路分析
    # ------------------------------------------------------------------

    def analyze_approach(self, question: str, student_approach: str) -> Dict[str, Any]:
        """
        分析学生的解题思路是否正确。

        Args:
            question: 数学题目。
            student_approach: 学生的解题思路描述。

        Returns:
            {
                "is_valid": bool,
                "feedback": str,
                "next_step": str,
                "score": int,  # 0-100
            }
        """
        prompt = f"""请分析以下学生的数学解题思路：

【题目】
{question}

【学生的思路】
{student_approach}

请从以下维度分析：
1. 思路方向是否正确（是否选对了方法）
2. 关键步骤是否合理
3. 有没有明显的逻辑漏洞
4. 下一步应该做什么

请严格按以下 JSON 格式返回：
{
    "is_valid": true,
    "feedback": "具体的评价",
    "next_step": "建议的下一步操作",
    "score": 75
}

请直接返回 JSON，不要添加 markdown 代码块标记。"""

        try:
            import json

            response = self.execute(
                messages=[
                    {"role": "system", "content": self._system_prompt},
                    {"role": "user", "content": prompt},
                ]
            )

            cleaned = response.strip()
            if cleaned.startswith("```"):
                lines = cleaned.split("\n")
                lines = [l for l in lines if not l.strip().startswith("```")]
                cleaned = "\n".join(lines)

            result = json.loads(cleaned)
            return {
                "is_valid": result.get("is_valid", False),
                "feedback": result.get("feedback", ""),
                "next_step": result.get("next_step", "再想想看"),
                "score": result.get("score", 0),
            }

        except (json.JSONDecodeError, RuntimeError):
            return {
                "is_valid": False,
                "feedback": response.strip(),
                "next_step": "继续尝试，你可以的！",
                "score": 0,
            }

    # ------------------------------------------------------------------
    #  练习题生成
    # ------------------------------------------------------------------

    def generate_practice(
        self,
        topic: str,
        difficulty: str = "medium",
        count: int = 1,
    ) -> Dict[str, Any]:
        """
        生成数学练习题。

        Args:
            topic: 知识点名称（如 "一元二次方程"、"三角函数"）。
            difficulty: 难度等级 easy/medium/hard。
            count: 题目数量。

        Returns:
            练习题结果。
        """
        return generate_exercise(
            topic=topic,
            difficulty=difficulty,
            subject="math",
            count=count,
        )

    # ------------------------------------------------------------------
    #  答案评估
    # ------------------------------------------------------------------

    def evaluate_solution(
        self,
        question: str,
        student_answer: str,
        correct_answer: str,
    ) -> Dict[str, Any]:
        """
        评估学生的数学答案。

        Args:
            question: 题目。
            student_answer: 学生的答案（包含解题过程）。
            correct_answer: 标准答案。

        Returns:
            评估结果。
        """
        return evaluate_answer(
            question=question,
            student_answer=student_answer,
            correct_answer=correct_answer,
        )

    # ------------------------------------------------------------------
    #  综合处理方法
    # ------------------------------------------------------------------

    def handle_question(
        self,
        question: str,
        student_answer: Optional[str] = None,
        correct_answer: Optional[str] = None,
        hint_level: Optional[int] = None,
        use_socratic: bool = False,
    ) -> Dict[str, Any]:
        """
        处理学生的数学问题。

        Args:
            question: 学生的问题或题目。
            student_answer: 学生的答案（可选）。
            correct_answer: 标准答案（可选）。
            hint_level: 请求提示的级别（可选，1-3）。
            use_socratic: 是否使用苏格拉底式引导。

        Returns:
            {
                "reply": str,
                "mode": str,
                "evaluation": dict | None,
            }
        """
        response: Dict[str, Any] = {"reply": "", "mode": "", "evaluation": None}

        # 学生请求提示
        if hint_level is not None:
            response["reply"] = self.get_hint(question, level=hint_level)
            response["mode"] = f"hint_{hint_level}"
            return response

        # 学生提交答案
        if student_answer and correct_answer:
            evaluation = self.evaluate_solution(question, student_answer, correct_answer)
            response["evaluation"] = evaluation

            if evaluation.get("is_correct"):
                response["reply"] = (
                    f"🎉 太棒了！你的答案是对的！\n\n"
                    f"得分：{evaluation.get('score', 0)}/100\n\n"
                    f"{evaluation.get('feedback', '')}\n\n"
                    f"{evaluation.get('encouragement', '继续保持！')}"
                )
                response["mode"] = "answer_correct"
            else:
                response["reply"] = (
                    f"答案还不够准确，但思路可能没错！\n\n"
                    f"得分：{evaluation.get('score', 0)}/100\n\n"
                    f"{evaluation.get('feedback', '')}\n\n"
                    f"改进建议：{', '.join(evaluation.get('improvements', []))}\n\n"
                    f"{evaluation.get('encouragement', '再试一次吧！')}"
                )
                response["mode"] = "answer_incorrect"
            return response

        # 一般性提问
        if use_socratic:
            response["reply"] = self.socratic_guide(question)
            response["mode"] = "socratic"
        else:
            response["reply"] = self.direct_teach(question)
            response["mode"] = "direct"

        return response

    def __repr__(self) -> str:
        return f"<MathTutor name={self.name!r} tools={self.get_tool_names()}>"
