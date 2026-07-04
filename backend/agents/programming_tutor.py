"""
编程辅导 Agent 模块
专注于 Python 编程教学，提供苏格拉底式引导、代码执行验证和错误解释。
确保生成的代码完整、可运行，经过语法验证。
"""

from typing import Any, Callable, Dict, List, Optional

from backend.agents.base_tutor import BaseTutor
from backend.tools import execute_python, check_syntax, generate_exercise
from backend.tools.code_validator import (
    validate_and_enhance_code,
    check_code_completeness,
    auto_fix_code,
    generate_code_quality_prompt,
)


class ProgrammingTutor(BaseTutor):
    """
    编程辅导 Agent。

    继承 BaseTutor，专注编程教学：
    - 苏格拉底式引导：先问"你觉得哪里卡住了"，再给提示
    - 代码实时验证：在沙箱中执行学生代码
    - 错误解释：分析运行时错误，给出易懂的解释
    - 练习题生成：根据薄弱点生成编程练习
    """

    def __init__(
        self,
        name: str = "CodeTutor",
        tools: Optional[List[Callable]] = None,
        mcp_tools: Optional[List] = None,
        system_prompt: Optional[str] = None,
        memory: Optional[Any] = None,
    ):
        default_tools = [execute_python, check_syntax, generate_exercise]
        super().__init__(
            name=name,
            subject="Python编程",
            tools=tools or default_tools,
            mcp_tools=mcp_tools or [],
            system_prompt=system_prompt or self._programming_system_prompt(),
            memory=memory,
        )

    # ------------------------------------------------------------------
    #  系统提示词
    # ------------------------------------------------------------------

    @staticmethod
    def _programming_system_prompt() -> str:
        return f"""你是一位经验丰富的编程辅导教师，名叫 CodeTutor。
你专注于 Python 编程教学，教学风格：
1. 先让学生自己思考问题卡在哪里，而不是直接指出错误
2. 善于用生活中的类比解释编程概念（如把变量比作储物柜）
3. 鼓励学生动手写代码，通过运行结果来验证理解
4. 错误解释要通俗易懂，不要只说"语法错误"，要解释为什么错了
5. 代码风格要符合 PEP 8 规范，养成良好的编程习惯
6. 对于常见错误（缩进、拼写、类型转换等），给出记忆口诀帮助记住

{generate_code_quality_prompt()}"""

    # ------------------------------------------------------------------
    #  苏格拉底式编程引导
    # ------------------------------------------------------------------

    def socratic_guide(self, question: str, context: Optional[str] = None) -> str:
        """
        编程特有的苏格拉底式引导。

        先用反问引导学生定位问题（"你觉得哪里卡住了？"），
        再根据回答给出分步提示，而非直接修复代码。
        """
        context_text = f"\n\n之前的对话背景：\n{context}" if context else ""

        prompt = f"""学生在编程学习中问了以下问题：
「{question}」{context_text}

请用编程教学中的苏格拉底式方法回应：
1. 先问学生"你觉得代码卡在哪里？"或"你期望的输出是什么？"
2. 引导学生逐行阅读自己的代码（橡皮鸭调试法）
3. 如果是错误相关，引导学生先阅读错误信息
4. 用一个小提示引导学生自己发现bug
5. 如果学生提供了代码，不要直接修改，指出方向让学生自己改

请直接输出引导回复："""

        return self.execute(
            messages=[
                {"role": "system", "content": self._system_prompt},
                {"role": "user", "content": prompt},
            ]
        )

    def direct_teach(self, question: str, context: Optional[str] = None) -> str:
        """
        编程特有的直接教学模式。

        覆盖父类方法，强调生成完整可运行的代码示例。
        """
        context_text = f"\n\n之前的对话背景：\n{context}" if context else ""

        prompt = f"""学生需要理解以下编程内容：
「{question}」{context_text}

请进行直接教学：
1. 用清晰的结构讲解核心概念
2. 配合生活化的类比帮助学生建立直观理解
3. **给出完整可运行的代码示例（⚠️ 关键要求）**：
   - 所有代码（import + 定义 + 示例调用 + 预期输出注释）必须放在**唯一一个** ```python ... ``` 代码块中
   - 禁止拆分成多个代码块（比如一个放函数定义、另一个放调用代码）
   - 函数/类的定义必须完整
   - 必须在同一个代码块内包含 if __name__ == "__main__": 入口和 print 输出
   - 预期输出用注释写在代码块内（如 # 输出：xxx）
   - 代码必须可以直接复制粘贴后运行
4. 在最后设置一个检查理解的小问题
5. 语言简洁明了，适合学生水平

请直接输出教学内容："""

        return self.execute(
            messages=[
                {"role": "system", "content": self._system_prompt},
                {"role": "user", "content": prompt},
            ]
        )

    # ------------------------------------------------------------------
    #  代码验证方法
    # ------------------------------------------------------------------

    def run_code(self, code: str) -> Dict[str, Any]:
        """
        在沙箱中执行学生代码，返回结果。

        Args:
            code: 学生编写的 Python 代码。

        Returns:
            {
                "success": bool,
                "output": str,
                "error": str | None,
                "explanation": str,
            }
        """
        result = execute_python(code)

        if not result["success"]:
            result["explanation"] = self._explain_error(result)

        return result

    def check_student_code(self, code: str) -> Dict[str, Any]:
        """
        检查学生代码的语法。

        Args:
            code: 学生编写的 Python 代码。

        Returns:
            语法检查结果。
        """
        result = check_syntax(code)

        if not result["valid"]:
            result["explanation"] = self._explain_syntax_error(result)

        return result

    # ------------------------------------------------------------------
    #  错误解释
    # ------------------------------------------------------------------

    def _explain_error(self, exec_result: Dict[str, Any]) -> str:
        """
        对运行时错误进行教学性解释。

        Args:
            exec_result: execute_python 返回的结果。

        Returns:
            易懂的错误解释。
        """
        error = exec_result.get("error", "未知错误")

        error_explanations = {
            "SyntaxError": "语法错误 —— 就像写句子少了句号，Python 读不懂你的代码。",
            "NameError": "名字错误 —— Python 说'我不认识这个名字'，可能拼错了或者还没定义。",
            "TypeError": "类型错误 —— 就像用苹果+数字一样，不同类型不能直接运算。",
            "IndentationError": "缩进错误 —— Python 用空格来区分代码块，缩进不对就不知道哪些代码是一组的。",
            "IndexError": "索引越界 —— 就像伸手去拿第6个苹果但只有5个。",
            "KeyError": "键不存在 —— 像在字典里查一个不存在的单词。",
            "ValueError": "值错误 —— 类型对了，但值不在允许范围内。",
            "AttributeError": "属性错误 —— 这个对象没有你调用的那个方法或属性。",
            "ZeroDivisionError": "除零错误 —— 数学上不能除以0，程序也是。",
            "TimeoutExpired": "超时 —— 程序运行太久了，可能陷入了死循环。",
        }

        for error_type, explanation in error_explanations.items():
            if error_type in error:
                return f"【{explanation}】\n\n错误详情：{error}"

        return self._llm_explain_error(error)

    def _explain_syntax_error(self, syntax_result: Dict[str, Any]) -> str:
        """
        对语法错误进行教学性解释。

        Args:
            syntax_result: check_syntax 返回的结果。

        Returns:
            易懂的语法错误解释。
        """
        error = syntax_result.get("error", "未知语法错误")
        line = syntax_result.get("line")

        if line:
            return f"第 {line} 行有语法问题：{error}\n\n提示：检查括号是否匹配、冒号是否遗漏、缩进是否正确。"
        return f"语法问题：{error}\n\n提示：检查拼写、括号配对和缩进。"

    def _llm_explain_error(self, error: str) -> str:
        """调用 LLM 生成个性化的错误解释。"""
        prompt = f"""学生代码运行时出现了以下错误：

{error}

请用通俗易懂的语言解释：
1. 这个错误是什么意思（用生活类比）
2. 可能的原因是什么
3. 应该怎么排查和修复

请直接输出解释，语气友善："""

        return self.execute(
            messages=[
                {"role": "system", "content": self._system_prompt},
                {"role": "user", "content": prompt},
            ]
        )

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
        生成编程练习题。

        Args:
            topic: 知识点名称（如 "递归"、"列表推导式"）。
            difficulty: 难度等级 easy/medium/hard。
            count: 题目数量。

        Returns:
            练习题结果。
        """
        return generate_exercise(
            topic=topic,
            difficulty=difficulty,
            subject="python",
            count=count,
        )

    # ------------------------------------------------------------------
    #  综合处理方法
    # ------------------------------------------------------------------

    def handle_question(
        self,
        question: str,
        code: Optional[str] = None,
        use_socratic: bool = False,
    ) -> Dict[str, Any]:
        """
        处理学生的编程问题。

        如果学生附带了代码，先检查语法和执行结果，
        再根据情况给出苏格拉底引导或直接教学。

        Args:
            question: 学生的问题。
            code: 学生编写的代码（可选）。
            use_socratic: 是否使用苏格拉底式引导。

        Returns:
            {
                "reply": str,
                "code_result": dict | None,
                "mode": str,
                "code_validation": dict | None,
            }
        """
        response: Dict[str, Any] = {
            "reply": "",
            "code_result": None,
            "mode": "",
            "code_validation": None,
        }

        if code:
            syntax = self.check_student_code(code)
            if not syntax["valid"]:
                response["code_result"] = syntax
                response["reply"] = f"代码有语法问题：{syntax.get('explanation', syntax.get('error', ''))}\n\n请检查后重新提交。"
                response["mode"] = "syntax_check"
                return response

            exec_result = self.run_code(code)
            response["code_result"] = exec_result

            if not exec_result["success"]:
                response["reply"] = f"代码运行出了点问题：\n{exec_result.get('explanation', exec_result.get('error', ''))}\n\n想想看，是哪里出了问题？"
                response["mode"] = "error_guide"
                return response

        if use_socratic:
            response["reply"] = self.socratic_guide(question)
            response["mode"] = "socratic"
        else:
            response["reply"] = self.direct_teach(question)
            response["mode"] = "direct"

        # 代码验证：检查生成的回复中是否包含代码，验证其完整性
        if response["reply"]:
            validation = validate_and_enhance_code(response["reply"], auto_fix=True)
            if validation["has_code"]:
                code_issues = []
                for cb in validation["code_blocks"]:
                    if not cb.get("complete", True):
                        code_issues.append({
                            "language": cb.get("language", "python"),
                            "issues": cb.get("issues", []),
                            "suggestions": cb.get("suggestions", []),
                            "fixes_applied": cb.get("fixes_applied", []),
                        })
                response["code_validation"] = {
                    "has_issues": len(code_issues) > 0,
                    "issues": code_issues,
                    "all_valid": validation["all_valid"],
                }

        return response

    def __repr__(self) -> str:
        return f"<ProgrammingTutor name={self.name!r} tools={self.get_tool_names()}>"