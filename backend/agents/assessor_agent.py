"""
评估 Agent 模块
分析学生交互历史，识别薄弱知识点，生成学习计划和知识图谱。
"""

import json
from typing import Any, Callable, Dict, List, Optional
from datetime import datetime

from backend.agents.base_tutor import BaseTutor
from backend.tools import generate_exercise, evaluate_answer


class AssessorAgent(BaseTutor):
    """
    评估 Agent。

    独立于辅导 Agent，专注学习评估：
    - analyze_student(interaction_history): 分析薄弱点
    - generate_study_plan(weak_points): 生成学习计划
    - update_knowledge_graph(student_id): 更新知识图谱
    - 生成诊断测试题评估学生当前水平
    """

    def __init__(
        self,
        name: str = "AssessorBot",
        tools: Optional[List[Callable]] = None,
        mcp_tools: Optional[List] = None,
        system_prompt: Optional[str] = None,
        memory: Optional[Any] = None,
    ):
        default_tools = [generate_exercise, evaluate_answer]
        super().__init__(
            name=name,
            subject="学习评估",
            tools=tools or default_tools,
            mcp_tools=mcp_tools or [],
            system_prompt=system_prompt or self._assessor_system_prompt(),
            memory=memory,
        )

    # ------------------------------------------------------------------
    #  系统提示词
    # ------------------------------------------------------------------

    @staticmethod
    def _assessor_system_prompt() -> str:
        return """你是一位教育评估专家，名叫 AssessorBot。
你的职责不是辅导学生，而是客观评估学生的学习状态。

你需要做到：
1. 客观公正地分析学生的交互历史，识别知识薄弱环节
2. 基于分析结果生成针对性的学习计划
3. 维护和更新学生的知识图谱
4. 评估要基于数据（答题正确率、提问频率、理解深度等）
5. 学习计划要具体可执行，包含优先级和时间建议
6. 保持鼓励态度，指出进步的同时诚实面对不足"""

    # ------------------------------------------------------------------
    #  学生分析
    # ------------------------------------------------------------------

    def analyze_student(
        self,
        interaction_history: List[Dict[str, Any]],
        student_profile: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        分析学生的交互历史，识别薄弱知识点。

        Args:
            interaction_history: 交互历史列表，每项包含：
                - question: 学生的问题
                - reply: 系统回复
                - topic: 相关知识点
                - is_correct: 回答是否正确（如有）
                - hint_used: 是否使用了提示
                - timestamp: 时间戳
            student_profile: 学生画像（可选），含已有薄弱点信息。

        Returns:
            {
                "weak_points": List[str],      # 薄弱知识点列表
                "strengths": List[str],        # 已掌握的强项
                "progress": str,               # 进步情况描述
                "confidence_level": float,     # 整体信心指数 0-1
                "error_patterns": List[str],   # 常见错误模式
                "recommendations": List[str],  # 学习建议
            }
        """
        # 构建交互摘要
        summary = self._build_interaction_summary(interaction_history)
        profile_context = ""
        if student_profile:
            existing_weak = student_profile.get("weak_points", [])
            existing_strong = student_profile.get("strengths", [])
            if existing_weak:
                profile_context += f"\n已识别的薄弱点：{', '.join(existing_weak)}"
            if existing_strong:
                profile_context += f"\n已掌握的强项：{', '.join(existing_strong)}"

        prompt = f"""请分析以下学生的学习交互记录：

【交互摘要】
{summary}
{profile_context}

请从以下维度进行分析：
1. 薄弱知识点（反复出错或需要多次提示的主题）
2. 已掌握的强项（回答正确且无需提示的主题）
3. 进步情况（相比之前是否有改善）
4. 整体信心指数（0-1，基于回答正确率和独立性）
5. 常见错误模式（如"概念混淆"、"粗心计算错误"等）
6. 针对性学习建议

请严格按以下 JSON 格式返回：
{{
    "weak_points": ["薄弱点1", "薄弱点2"],
    "strengths": ["强项1", "强项2"],
    "progress": "进步描述",
    "confidence_level": 0.65,
    "error_patterns": ["错误模式1", "错误模式2"],
    "recommendations": ["建议1", "建议2"]
}}

请直接返回 JSON，不要添加 markdown 代码块标记。"""

        try:
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
                "weak_points": result.get("weak_points", []),
                "strengths": result.get("strengths", []),
                "progress": result.get("progress", "暂无明显变化"),
                "confidence_level": result.get("confidence_level", 0.5),
                "error_patterns": result.get("error_patterns", []),
                "recommendations": result.get("recommendations", []),
            }

        except (json.JSONDecodeError, RuntimeError):
            # 兜底分析
            return self._fallback_analysis(interaction_history)

    def _build_interaction_summary(self, history: List[Dict[str, Any]]) -> str:
        """将交互历史构建为结构化的摘要文本。"""
        if not history:
            return "暂无交互记录。"

        total = len(history)
        correct_count = sum(1 for h in history if h.get("is_correct"))
        hint_count = sum(1 for h in history if h.get("hint_used"))

        # 按主题统计
        topic_stats: Dict[str, Dict[str, int]] = {}
        for h in history:
            topic = h.get("topic", "未分类")
            if topic not in topic_stats:
                topic_stats[topic] = {"total": 0, "correct": 0, "hints": 0}
            topic_stats[topic]["total"] += 1
            if h.get("is_correct"):
                topic_stats[topic]["correct"] += 1
            if h.get("hint_used"):
                topic_stats[topic]["hints"] += 1

        lines = [
            f"总交互次数：{total} 次",
            f"回答正确：{correct_count} 次（{correct_count / total:.0%}）",
            f"使用过提示：{hint_count} 次",
            "",
            "按主题统计：",
        ]

        for topic, stats in topic_stats.items():
            accuracy = stats["correct"] / stats["total"] if stats["total"] > 0 else 0
            lines.append(
                f"  - {topic}: {stats['total']} 次，"
                f"正确率 {accuracy:.0%}，"
                f"提示 {stats['hints']} 次"
            )

        # 最近的交互
        if len(history) >= 3:
            lines.append("")
            lines.append("最近 3 次交互：")
            for h in history[-3:]:
                lines.append(f"  Q: {h.get('question', '无')}")
                lines.append(f"  知识点: {h.get('topic', '未分类')} | 正确: {h.get('is_correct', '未知')}")

        return "\n".join(lines)

    def _fallback_analysis(self, history: List[Dict[str, Any]]) -> Dict[str, Any]:
        """LLM 分析失败时的兜底分析。"""
        weak_points = []
        strengths = []

        for h in history:
            topic = h.get("topic", "")
            if not topic:
                continue
            if not h.get("is_correct") or h.get("hint_used"):
                if topic not in weak_points:
                    weak_points.append(topic)
            elif h.get("is_correct") and not h.get("hint_used"):
                if topic not in strengths:
                    strengths.append(topic)

        correct_count = sum(1 for h in history if h.get("is_correct"))
        total = len(history)
        confidence = correct_count / total if total > 0 else 0.5

        return {
            "weak_points": weak_points,
            "strengths": strengths,
            "progress": "基于交互数据的简单分析",
            "confidence_level": round(confidence, 2),
            "error_patterns": ["数据不足以识别具体错误模式"],
            "recommendations": [f"重点练习以下薄弱点：{', '.join(weak_points)}"],
        }

    # ------------------------------------------------------------------
    #  学习计划生成
    # ------------------------------------------------------------------

    def generate_study_plan(
        self,
        weak_points: List[str],
        strengths: Optional[List[str]] = None,
        available_hours: int = 2,
        time_horizon: str = "week",  # "day" / "week" / "month"
    ) -> Dict[str, Any]:
        """
        根据薄弱知识点生成个性化的学习计划。

        Args:
            weak_points: 薄弱知识点列表。
            strengths: 已掌握的强项（可选），用于安排复习间隔。
            available_hours: 每天可用学习时间（小时）。
            time_horizon: 计划时间跨度。

        Returns:
            {
                "plan": List[dict],         # 学习计划项
                "schedule": str,            # 日程安排描述
                "priorities": Dict[str, int], # 知识点优先级
                "estimated_completion": str, # 预计完成时间
            }
        """
        horizons = {
            "day": "一天内的学习计划",
            "week": "一周的学习计划",
            "month": "一个月的学习计划",
        }
        horizon_text = horizons.get(time_horizon, horizons["week"])

        strengths_text = ""
        if strengths:
            strengths_text = f"\n已掌握的强项：{', '.join(strengths)}（安排定期复习即可）"

        prompt = f"""请为学生制定一个个性化的{horizon_text}。

【薄弱知识点】（需要重点攻克）
{', '.join(weak_points)}
{strengths_text}

【每天可用学习时间】
{available_hours} 小时

请按以下结构制定学习计划：
1. 为每个薄弱点分配优先级（1=最高，数字越大优先级越低）
2. 安排具体的学习内容和练习
3. 包含新知识点学习和已掌握知识点的复习间隔
4. 每步标注预计耗时
5. 最后标注预计完成时间

请严格按以下 JSON 格式返回：
{{
    "plan": [
        {{
            "step": 1,
            "topic": "知识点名称",
            "action": "学习/练习/复习",
            "description": "具体的学习内容描述",
            "estimated_minutes": 30,
            "exercises": ["练习题1", "练习题2"]
        }}
    ],
    "schedule": "日程安排的总体描述",
    "priorities": {{"知识点1": 1, "知识点2": 2}},
    "estimated_completion": "预计 X 天后完成"
}}

请直接返回 JSON，不要添加 markdown 代码块标记。"""

        try:
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
                "plan": result.get("plan", []),
                "schedule": result.get("schedule", ""),
                "priorities": result.get("priorities", {}),
                "estimated_completion": result.get("estimated_completion", ""),
                "generated_at": datetime.now().isoformat(),
            }

        except (json.JSONDecodeError, RuntimeError):
            return self._fallback_study_plan(weak_points, available_hours)

    def _fallback_study_plan(
        self,
        weak_points: List[str],
        available_hours: int,
    ) -> Dict[str, Any]:
        """兜底学习计划生成。"""
        total_minutes = available_hours * 60
        minutes_per_topic = total_minutes // max(len(weak_points), 1)

        plan = []
        for i, wp in enumerate(weak_points, 1):
            plan.append({
                "step": i,
                "topic": wp,
                "action": "学习",
                "description": f"学习 {wp} 的核心概念，完成基础练习",
                "estimated_minutes": minutes_per_topic,
                "exercises": [f"关于 {wp} 的基础练习题"],
            })
            plan.append({
                "step": i * 2,
                "topic": wp,
                "action": "练习",
                "description": f"针对 {wp} 进行强化练习",
                "estimated_minutes": minutes_per_topic // 2,
                "exercises": [f"关于 {wp} 的进阶练习题"],
            })

        return {
            "plan": plan,
            "schedule": f"依次学习 {len(weak_points)} 个薄弱点，每个分配约 {minutes_per_topic} 分钟",
            "priorities": {wp: i + 1 for i, wp in enumerate(weak_points)},
            "estimated_completion": f"{len(weak_points)} 个知识点",
            "generated_at": datetime.now().isoformat(),
        }

    # ------------------------------------------------------------------
    #  知识图谱更新
    # ------------------------------------------------------------------

    def update_knowledge_graph(
        self,
        student_id: str,
        interaction_history: Optional[List[Dict[str, Any]]] = None,
        current_profile: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        根据最新的交互数据更新学生的知识图谱。

        知识图谱结构：
        {
            student_id: str,
            nodes: {                        # 知识点节点
                "知识点名": {
                    "mastery": float,        # 掌握程度 0-1
                    "last_tested": str,      # 最后测试时间
                    "tests_count": int,      # 测试次数
                    "correct_count": int,    # 正确次数
                    "difficulty": float,     # 感知难度 0-1
                }
            },
            edges: [                        # 知识点关联
                {"from": "A", "to": "B", "weight": float}
            ],
            updated_at: str,
        }

        Args:
            student_id: 学生 ID。
            interaction_history: 最新交互历史。
            current_profile: 当前知识图谱（可选）。

        Returns:
            更新后的知识图谱。
        """
        graph = {
            "student_id": student_id,
            "nodes": {},
            "edges": [],
            "updated_at": datetime.now().isoformat(),
        }

        # 加载已有图谱
        if current_profile and "knowledge_graph" in current_profile:
            graph = current_profile["knowledge_graph"]
            graph["updated_at"] = datetime.now().isoformat()

        if not interaction_history:
            return graph

        # 根据交互更新知识点节点
        topic_stats: Dict[str, Dict[str, Any]] = {}
        for h in interaction_history:
            topic = h.get("topic")
            if not topic:
                continue
            if topic not in topic_stats:
                topic_stats[topic] = {
                    "tests_count": 0,
                    "correct_count": 0,
                    "hints_used": 0,
                }
            topic_stats[topic]["tests_count"] += 1
            if h.get("is_correct"):
                topic_stats[topic]["correct_count"] += 1
            if h.get("hint_used"):
                topic_stats[topic]["hints_used"] += 1

        # 更新或创建节点
        for topic, stats in topic_stats.items():
            if topic in graph["nodes"]:
                # 更新已有节点
                node = graph["nodes"][topic]
                old_correct = node.get("correct_count", 0)
                old_total = node.get("tests_count", 0)

                node["tests_count"] = old_total + stats["tests_count"]
                node["correct_count"] = old_correct + stats["correct_count"]
                node["mastery"] = node["correct_count"] / node["tests_count"]
                node["last_tested"] = datetime.now().isoformat()
                # 感知难度：使用提示频率来估计
                total_hints = node.get("hints_used", 0) + stats["hints_used"]
                node["difficulty"] = total_hints / max(node["tests_count"], 1)
            else:
                # 创建新节点
                mastery = stats["correct_count"] / stats["tests_count"] if stats["tests_count"] > 0 else 0
                graph["nodes"][topic] = {
                    "mastery": round(mastery, 2),
                    "last_tested": datetime.now().isoformat(),
                    "tests_count": stats["tests_count"],
                    "correct_count": stats["correct_count"],
                    "hints_used": stats["hints_used"],
                    "difficulty": round(stats["hints_used"] / max(stats["tests_count"], 1), 2),
                }

        return graph

    # ------------------------------------------------------------------
    #  诊断测试
    # ------------------------------------------------------------------

    def generate_diagnostic_test(
        self,
        topics: List[str],
        num_questions: int = 5,
    ) -> Dict[str, Any]:
        """
        生成诊断测试题，用于评估学生对特定知识点的掌握程度。

        Args:
            topics: 要测试的知识点列表。
            num_questions: 题目数量。

        Returns:
            {
                "test_id": str,
                "questions": List[dict],
                "topics": List[str],
                "total_questions": int,
            }
        """
        topics_str = ", ".join(topics)
        questions_per_topic = max(1, num_questions // len(topics))

        prompt = f"""请生成一套诊断测试，评估学生对以下知识点的掌握程度：
{topics_str}

共生成 {num_questions} 道题，每个知识点约 {questions_per_topic} 题。

要求：
1. 题目难度逐步递增
2. 每题包含题目、选项（如果是选择题）、标准答案和解析
3. 题目要能区分"真正理解"和"表面记忆"

请严格按以下 JSON 格式返回：
{{
    "questions": [
        {{
            "id": 1,
            "topic": "知识点",
            "difficulty": "easy/medium/hard",
            "type": "choice/fill/essay",
            "question": "题目描述",
            "options": ["A", "B", "C", "D"],
            "answer": "标准答案",
            "explanation": "解析"
        }}
    ]
}}

请直接返回 JSON，不要添加 markdown 代码块标记。"""

        try:
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

            import uuid
            return {
                "test_id": str(uuid.uuid4())[:8],
                "questions": result.get("questions", []),
                "topics": topics,
                "total_questions": num_questions,
            }

        except (json.JSONDecodeError, RuntimeError):
            return {
                "test_id": "fallback",
                "questions": [],
                "topics": topics,
                "total_questions": num_questions,
                "error": "诊断测试生成失败，请稍后重试。",
            }

    # ------------------------------------------------------------------
    #  综合处理方法
    # ------------------------------------------------------------------

    def handle_assessment(
        self,
        interaction_history: List[Dict[str, Any]],
        student_profile: Optional[Dict[str, Any]] = None,
        generate_plan: bool = True,
        update_graph: bool = True,
    ) -> Dict[str, Any]:
        """
        综合评估处理入口。

        Args:
            interaction_history: 交互历史。
            student_profile: 学生画像。
            generate_plan: 是否生成学习计划。
            update_graph: 是否更新知识图谱。

        Returns:
            完整的评估报告。
        """
        result: Dict[str, Any] = {"timestamp": datetime.now().isoformat()}

        # 分析学生
        analysis = self.analyze_student(interaction_history, student_profile)
        result["analysis"] = analysis

        # 生成学习计划
        if generate_plan and analysis["weak_points"]:
            plan = self.generate_study_plan(
                weak_points=analysis["weak_points"],
                strengths=analysis.get("strengths"),
            )
            result["study_plan"] = plan

        # 更新知识图谱
        if update_graph and student_profile:
            graph = self.update_knowledge_graph(
                student_id=student_profile.get("student_id", "unknown"),
                interaction_history=interaction_history,
                current_profile=student_profile,
            )
            result["knowledge_graph"] = graph

        return result

    def __repr__(self) -> str:
        return f"<AssessorAgent name={self.name!r} tools={self.get_tool_names()}>"
