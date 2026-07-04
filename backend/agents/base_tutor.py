"""
基础辅导 Agent 模块
所有教学 Agent 的父类，提供苏格拉底式引导和直接教学两种模式。
"""

from typing import Any, Callable, Dict, List, Optional

from backend.llm import QwenLLM


class BaseTutor:
    """
    基础教学 Agent 抽象类。

    所有具体教学 Agent（编程、数学、知识问答等）均继承此类，
    复用 LLM 调用、苏格拉底引导、直接教学等核心能力。
    """

    def __init__(
        self,
        name: str,
        subject: str,
        tools: Optional[List[Callable]] = None,
        mcp_tools: Optional[List] = None,
        system_prompt: Optional[str] = None,
        memory: Optional[Any] = None,
    ):
        """
        Args:
            name: Agent 名称标识。
            subject: 学科领域。
            tools: 本地可调用的工具函数列表。
            mcp_tools: MCP 工具列表（LangChain BaseTool 实例）。
            system_prompt: 自定义系统提示词（为 None 时使用默认）。
            memory: LearningMemory 实例，用于查询和更新学生数据。
        """
        self.name = name
        self.subject = subject
        self.tools = tools or []
        self.mcp_tools = mcp_tools or []
        self.llm = QwenLLM()
        self.memory = memory
        self._system_prompt = system_prompt or self._default_system_prompt()
        # 对话历史，用于上下文感知
        self._conversation_history: List[Dict[str, str]] = []

    # ------------------------------------------------------------------
    #  系统提示词
    # ------------------------------------------------------------------

    def _default_system_prompt(self) -> str:
        """默认系统提示词，子类可覆写。"""
        return f"""你是一位专业的{self.subject}辅导教师，名叫{self.name}。
你的教学理念：
1. 以学生为中心，关注学生的理解过程
2. 善用苏格拉底式提问，引导学生自主思考
3. 根据学生的回答调整教学策略
4. 给予鼓励性反馈，建立学习信心
5. 解释要清晰、循序渐进，使用类比和生活实例"""

    # ------------------------------------------------------------------
    #  核心教学方法
    # ------------------------------------------------------------------

    def socratic_guide(self, question: str, context: Optional[str] = None) -> str:
        """
        苏格拉底式引导：通过反问引导学生思考，而非直接给出答案。

        Args:
            question: 学生提出的问题。
            context: 可选的对话上下文。

        Returns:
            引导性反问或提示文本。
        """
        context_text = f"\n\n之前的对话背景：\n{context}" if context else ""

        prompt = f"""学生问了以下问题：
「{question}」{context_text}

请用苏格拉底式教学法回应：
1. 不要直接给出答案
2. 先肯定学生的思考（如果有的话）
3. 用 1-2 个引导性反问，帮助学生自己发现答案
4. 如果学生明显卡住了，给出一个小提示（但仍以问题形式呈现）
5. 保持友善和鼓励的语气

请直接输出引导回复："""

        return self.execute(
            messages=[
                {"role": "system", "content": self._system_prompt},
                {"role": "user", "content": prompt},
            ]
        )

    def direct_teach(self, question: str, context: Optional[str] = None) -> str:
        """
        直接教学模式：清晰、结构化地讲解知识点。

        适用于学生已经经过引导但仍不理解，或明确要求直接讲解时。

        Args:
            question: 学生提出的问题。
            context: 可选的对话上下文。

        Returns:
            教学讲解文本。
        """
        context_text = f"\n\n之前的对话背景：\n{context}" if context else ""

        prompt = f"""学生需要理解以下内容：
「{question}」{context_text}

请进行直接教学：
1. 用清晰的结构讲解核心概念
2. 配合具体的例子帮助理解
3. 在最后设置一个检查理解的小问题
4. 语言简洁明了，适合学生水平

请直接输出教学内容："""

        return self.execute(
            messages=[
                {"role": "system", "content": self._system_prompt},
                {"role": "user", "content": prompt},
            ]
        )

    # ------------------------------------------------------------------
    #  LLM 调用
    # ------------------------------------------------------------------

    def execute(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """
        调用 LLM 执行推理。

        Args:
            messages: 消息列表，格式为 [{"role": "...", "content": "..."}]。
            **kwargs: 传递给 LLM 的额外参数。

        Returns:
            模型回复文本。
        """
        # 拼接 system prompt（如果 messages 中没有 system 角色）
        has_system = any(m.get("role") == "system" for m in messages)

        if has_system:
            # 提取 system 和 user messages
            system_content = ""
            user_content = ""
            for m in messages:
                if m["role"] == "system":
                    system_content = m["content"]
                elif m["role"] == "user":
                    user_content = m["content"]
            return self.llm.invoke(user_content, system_prompt=system_content)
        else:
            # 仅使用最后一条 user message
            last_user = messages[-1]["content"] if messages else ""
            return self.llm.invoke(last_user, system_prompt=self._system_prompt)

    # ------------------------------------------------------------------
    #  工具调用辅助
    # ------------------------------------------------------------------

    def get_all_tools(self) -> List:
        """获取所有可用工具（本地 + MCP）的合并列表。"""
        return self.tools + self.mcp_tools

    def get_tool_names(self) -> List[str]:
        """获取所有可用工具的名称列表（含本地工具和 MCP 工具）。"""
        local_names = []
        for t in self.tools:
            name = getattr(t, "__name__", None) or getattr(t, "name", str(t))
            local_names.append(name)
        mcp_names = [getattr(t, "name", str(t)) for t in self.mcp_tools]
        return local_names + mcp_names

    def call_tool(self, tool_name: str, **kwargs) -> Any:
        """
        按名称调用工具（先查本地工具，再查 MCP 工具）。

        Args:
            tool_name: 工具函数名。
            **kwargs: 传递给工具的参数。

        Returns:
            工具返回结果。

        Raises:
            ValueError: 找不到指定工具。
        """
        # 先在本地工具中查找
        for tool in self.tools:
            t_name = getattr(tool, "__name__", None) or getattr(tool, "name", "")
            if t_name == tool_name:
                return tool(**kwargs)

        # 再在 MCP 工具中查找
        for tool in self.mcp_tools:
            t_name = getattr(tool, "name", "")
            if t_name == tool_name:
                # MCP 工具（LangChain BaseTool）使用 .invoke() 方法
                # 支持单参数调用和关键字参数调用
                if hasattr(tool, "ainvoke"):
                    # 异步调用需要事件循环支持，这里使用同步方式
                    import asyncio
                    try:
                        loop = asyncio.get_event_loop()
                        if loop.is_running():
                            # 当前有事件循环运行中，使用 run_in_executor
                            import concurrent.futures
                            with concurrent.futures.ThreadPoolExecutor() as executor:
                                future = executor.submit(
                                    asyncio.run, tool.ainvoke(kwargs)
                                )
                                return future.result()
                        else:
                            return loop.run_until_complete(tool.ainvoke(kwargs))
                    except RuntimeError:
                        return asyncio.run(tool.ainvoke(kwargs))
                elif hasattr(tool, "invoke"):
                    return tool.invoke(kwargs)
                else:
                    # 直接调用
                    return tool(**kwargs)

        raise ValueError(
            f"工具 '{tool_name}' 不存在。可用工具：{self.get_tool_names()}"
        )

    def get_mcp_tool_by_name(self, name: str):
        """根据名称获取 MCP 工具。"""
        for tool in self.mcp_tools:
            if getattr(tool, "name", "") == name:
                return tool
        return None

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.name!r} subject={self.subject!r} tools={self.get_tool_names()}>"
