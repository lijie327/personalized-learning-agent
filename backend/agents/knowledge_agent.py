"""
知识问答 Agent 模块
基于 RAG 检索教材和课件，提供带来源引用的知识点解答。
"""

from typing import Any, Callable, Dict, List, Optional

from backend.agents.base_tutor import BaseTutor
from backend.rag import EducationKnowledgeBase


# 模块级共享知识库实例（由 main.py 的 lifespan 初始化）
_shared_kb: Optional[EducationKnowledgeBase] = None


def set_shared_knowledge_base(kb: EducationKnowledgeBase):
    """设置共享知识库实例（由 main.py 在启动时调用）。"""
    global _shared_kb
    _shared_kb = kb


def knowledge_search(query: str, subject: str = "python", k: int = 3) -> Dict[str, Any]:
    """
    知识检索工具：从教材和课件中检索相关知识点。

    使用 RAG 向量检索 + 混合排序，返回匹配的课程内容片段。
    复用全局共享的 EducationKnowledgeBase 实例，避免重复初始化。

    Args:
        query: 检索查询（学生的问题或关键词）。
        subject: 科目名称，如 'python' / 'data_structures'。
        k: 返回结果数量。

    Returns:
        {
            "results": List[dict],    # 检索结果列表
            "has_results": bool,       # 是否有检索结果
            "sources": List[str],      # 来源引用列表
            "query": str,              # 原始查询
        }
    """
    global _shared_kb
    if _shared_kb is None:
        _shared_kb = EducationKnowledgeBase()

    # 先用混合检索（向量 + 关键词）
    results = _shared_kb.hybrid_search(query=query, subject=subject, k=k)

    # 如果混合检索无结果，退回到向量检索
    if not results:
        results = _shared_kb.search(query=query, subject=subject, k=k)

    # 提取来源引用
    sources = []
    for r in results:
        topic = r.get("topic", "未知主题")
        chunk_idx = r.get("chunk_index", 0)
        score = r.get("score", 0)
        source_str = f"《{subject}》- {topic} - 第{chunk_idx + 1}段（匹配度 {score:.0%}）"
        sources.append(source_str)

    return {
        "results": results,
        "has_results": len(results) > 0,
        "sources": sources,
        "query": query,
    }


class KnowledgeAgent(BaseTutor):
    """
    知识问答 Agent。

    继承 BaseTutor，基于 RAG 检索教材/课件中的知识点：
    - 工具: knowledge_search（RAG 检索）
    - 教材知识点解答，附带来源引用
    - 苏格拉底式引导结合教材内容
    """

    def __init__(
        self,
        name: str = "KnowledgeBot",
        tools: Optional[List[Callable]] = None,
        mcp_tools: Optional[List] = None,
        system_prompt: Optional[str] = None,
        memory: Optional[Any] = None,
        knowledge_base: Optional[EducationKnowledgeBase] = None,
    ):
        default_tools = [knowledge_search]
        super().__init__(
            name=name,
            subject="通用知识",
            tools=tools or default_tools,
            mcp_tools=mcp_tools or [],
            system_prompt=system_prompt or self._knowledge_system_prompt(),
            memory=memory,
        )
        # 复用共享知识库实例（避免重复初始化 ChromaDB 和重复入库）
        if knowledge_base is not None:
            self.kb = knowledge_base
        elif _shared_kb is not None:
            self.kb = _shared_kb
        else:
            self.kb = EducationKnowledgeBase()

    # ------------------------------------------------------------------
    #  系统提示词
    # ------------------------------------------------------------------

    @staticmethod
    def _knowledge_system_prompt() -> str:
        return """你是一位知识渊博的通识教师，名叫 KnowledgeBot。
你擅长从教材和课件中找到准确的知识点来解答学生的问题。

你的教学风格：
1. 回答问题时要引用教材中的具体内容，标注来源
2. 如果检索到的内容不完整，用自己的知识补充解释
3. 用清晰的结构组织答案：先核心概念，再详细解释，最后举例
4. 如果检索不到相关内容，坦诚告诉学生，并尝试用自己的知识回答
5. 鼓励学生举一反三，在最后提出一个相关的思考问题"""

    # ------------------------------------------------------------------
    #  RAG 增强的教学方法
    # ------------------------------------------------------------------

    def answer_with_sources(
        self,
        question: str,
        subject: str = "python",
    ) -> Dict[str, Any]:
        """
        基于 RAG 检索的知识点解答，附带来源引用。

        Args:
            question: 学生的问题。
            subject: 科目名称。

        Returns:
            {
                "answer": str,          # 解答内容
                "sources": List[str],   # 来源引用
                "has_sources": bool,    # 是否有教材来源
                "answer_type": str,     # "rag" 或 "direct"（无检索结果时）
            }
        """
        # 第一步：检索教材
        search_result = knowledge_search(query=question, subject=subject, k=3)

        # 第二步：根据检索结果生成解答
        if search_result["has_results"]:
            return self._generate_rag_answer(question, search_result, subject)
        else:
            return self._generate_direct_answer(question, subject)

    def _generate_rag_answer(
        self,
        question: str,
        search_result: Dict[str, Any],
        subject: str,
    ) -> Dict[str, Any]:
        """
        基于检索到的教材内容生成解答。

        将检索到的教材片段作为上下文，让 LLM 生成结构化的解答。
        """
        # 构建教材上下文
        context_parts = []
        for i, r in enumerate(search_result["results"], 1):
            topic = r.get("topic", "")
            content = r.get("content", "")
            context_parts.append(f"【来源{i}：{subject} - {topic}】\n{content}")

        context_text = "\n\n---\n\n".join(context_parts)
        sources = search_result["sources"]

        prompt = f"""学生问了以下问题：
「{question}」

以下是从教材中检索到的相关内容：

{context_text}

请基于上述教材内容，为学生解答问题：
1. 先用 1-2 句话概括核心答案
2. 再详细解释，配合具体例子
3. 在相关的地方标注来源，如 [来源1]
4. 最后提出一个相关的思考问题

请直接输出解答内容："""

        answer = self.execute(
            messages=[
                {"role": "system", "content": self._system_prompt},
                {"role": "user", "content": prompt},
            ]
        )

        return {
            "answer": answer,
            "sources": sources,
            "has_sources": True,
            "answer_type": "rag",
        }

    def _generate_direct_answer(
        self,
        question: str,
        subject: str,
    ) -> Dict[str, Any]:
        """
        教材中未检索到相关内容时，用自己的知识解答。

        明确告知学生此答案未来自教材，而是教师自己的理解。
        """
        prompt = f"""学生问了以下问题：
「{question}」

注意：在教材中没有检索到直接相关的内容。

请根据你的知识为学生解答：
1. 先说明"这部分内容教材中没有详细展开，我来帮你梳理一下"
2. 清晰地讲解核心概念
3. 配合具体的例子帮助理解
4. 最后提出一个相关的思考问题

请直接输出解答内容："""

        answer = self.execute(
            messages=[
                {"role": "system", "content": self._system_prompt},
                {"role": "user", "content": prompt},
            ]
        )

        return {
            "answer": answer,
            "sources": [],
            "has_sources": False,
            "answer_type": "direct",
        }

    # ------------------------------------------------------------------
    #  苏格拉底式引导（知识版）
    # ------------------------------------------------------------------

    def socratic_guide(self, question: str, context: Optional[str] = None) -> str:
        """
        知识问答的苏格拉底式引导。

        引导学生回顾教材中的相关内容，而非直接给出答案。
        """
        context_text = f"\n\n之前的对话背景：\n{context}" if context else ""

        prompt = f"""学生在知识学习中问了以下问题：
「{question}」{context_text}

请用苏格拉底式教学法回应：
1. 引导学生回忆教材中的相关内容（"你还记得课本里是怎么说的吗？"）
2. 用反问帮助学生联系已学知识
3. 如果学生完全没有头绪，给出一个具体的回忆线索
4. 保持友善和鼓励的语气

请直接输出引导回复："""

        return self.execute(
            messages=[
                {"role": "system", "content": self._system_prompt},
                {"role": "user", "content": prompt},
            ]
        )

    # ------------------------------------------------------------------
    #  获取学习材料
    # ------------------------------------------------------------------

    def get_materials(self, subject: str, topic: str) -> List[Dict[str, Any]]:
        """
        获取指定主题的完整学习材料。

        Args:
            subject: 科目名称。
            topic: 主题名称。

        Returns:
            该主题所有分块的学习材料列表。
        """
        return self.kb.get_learning_materials(subject=subject, topic=topic)

    def list_subjects(self) -> List[str]:
        """列出所有可用科目。"""
        return self.kb.list_subjects()

    def list_topics(self, subject: str) -> List[str]:
        """列出指定科目的所有主题。"""
        return self.kb.list_topics(subject)

    # ------------------------------------------------------------------
    #  综合处理方法
    # ------------------------------------------------------------------

    def handle_question(
        self,
        question: str,
        subject: str = "python",
        use_socratic: bool = False,
        include_sources: bool = True,
    ) -> Dict[str, Any]:
        """
        处理学生的知识问题。

        Args:
            question: 学生的问题。
            subject: 科目名称。
            use_socratic: 是否先用苏格拉底式引导。
            include_sources: 是否附带来源引用。

        Returns:
            {
                "reply": str,
                "sources": List[str],
                "mode": str,
            }
        """
        response: Dict[str, Any] = {"reply": "", "sources": [], "mode": ""}

        if include_sources:
            result = self.answer_with_sources(question, subject)
            response["reply"] = result["answer"]
            response["sources"] = result["sources"]
            response["mode"] = result["answer_type"]
        else:
            if use_socratic:
                response["reply"] = self.socratic_guide(question)
                response["mode"] = "socratic"
            else:
                response["reply"] = self.direct_teach(question)
                response["mode"] = "direct"

        return response

    def __repr__(self) -> str:
        return f"<KnowledgeAgent name={self.name!r} subject={self.subject!r} tools={self.get_tool_names()}>"
