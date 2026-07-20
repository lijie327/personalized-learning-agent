"""从学生画像构建注入 LLM prompt 的上下文文本。"""

from typing import Any, Dict


def build_student_context(profile: Dict[str, Any]) -> str:
    """
    从学生画像构建上下文文本，注入到 LLM prompt 中。

    包含薄弱点、已掌握知识点和知识图谱统计，
    帮助 LLM 了解学生状况并个性化教学。
    """
    parts = []

    weak_detail = profile.get("weak_points_detail", [])
    if weak_detail:
        lines = ["\n## 该学生的学习薄弱点（需要重点帮助）"]
        for wp in weak_detail[:5]:
            lines.append(
                f"- {wp['topic']}（{wp.get('subject', '')}），"
                f"掌握程度 {wp['score']:.0%}，已尝试 {wp.get('attempts', 0)} 次"
            )
        parts.append("\n".join(lines))

    strong_detail = profile.get("strengths_detail", [])
    if strong_detail:
        lines = ["\n## 该学生已掌握的知识点（可跳过基础讲解）"]
        for s in strong_detail[:5]:
            lines.append(
                f"- {s['topic']}（{s.get('subject', '')}），"
                f"掌握程度 {s['score']:.0%}"
            )
        parts.append("\n".join(lines))

    kg = profile.get("knowledge_graph", {})
    stats = kg.get("statistics", {})
    if stats and stats.get("total_nodes", 0) > 0:
        lines = ["\n## 知识图谱统计"]
        lines.append(f"- 总知识点数: {stats.get('total_nodes', 0)}")
        lines.append(f"- 平均掌握度: {stats.get('avg_mastery', 0):.0%}")
        lines.append(f"- 已掌握（≥80%）: {stats.get('mastered', 0)} 个")
        lines.append(f"- 需加强（<60%）: {stats.get('needs_work', 0)} 个")
        parts.append("\n".join(lines))

    return "\n".join(parts) + "\n" if parts else ""
