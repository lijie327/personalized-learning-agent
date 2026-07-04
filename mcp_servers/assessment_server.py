"""
学情评估 MCP Server
提供学生学习情况分析能力
"""
import sys

# Windows: 强制 UTF-8 输出
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Assessment")


@mcp.tool()
def analyze_weak_points(topics: list[dict]) -> dict:
    """
    分析学生薄弱点

    Args:
        topics: [{"name": "函数", "score": 0.35, "attempts": 3}, ...]

    Returns:
        {"weak_points": list, "suggestions": list}
    """
    weak_points = []
    suggestions = []

    for topic in topics:
        score = topic.get("score", 0.5)
        name = topic.get("name", "")
        attempts = topic.get("attempts", 0)

        if score < 0.4:
            weak_points.append({
                "name": name,
                "level": "严重薄弱",
                "score": score
            })
            suggestions.append(f"⚠️ {name}需要重点补习，建议从基础概念重新学习")
        elif score < 0.6:
            weak_points.append({
                "name": name,
                "level": "一般薄弱",
                "score": score
            })
            suggestions.append(f"📝 {name}还需加强练习，建议做3-5道针对性习题")
        elif attempts >= 3:
            suggestions.append(f"💪 {name}进步明显，继续保持！")

    return {
        "weak_points": weak_points,
        "suggestions": suggestions,
        "total_weak": len(weak_points)
    }


@mcp.tool()
def generate_study_plan(weak_points: list[str], available_time: int = 60) -> dict:
    """
    根据薄弱点生成学习计划

    Args:
        weak_points: 薄弱知识点列表
        available_time: 可用学习时间(分钟)

    Returns:
        {"daily_plan": list, "total_days": int}
    """
    if not weak_points:
        return {
            "daily_plan": ["🎉 当前没有明显薄弱点，保持复习即可！"],
            "total_days": 1
        }

    daily_plan = []
    time_per_topic = max(15, available_time // max(len(weak_points), 1))

    for i, topic in enumerate(weak_points, 1):
        daily_plan.append({
            "day": i,
            "topic": topic,
            "duration": f"{time_per_topic}分钟",
            "tasks": [
                f"📖 复习{topic}基础概念（10分钟）",
                f"✏️ 做2道{topic}练习题（10分钟）",
                f"🔍 整理错题笔记（5分钟）"
            ]
        })

    return {
        "daily_plan": daily_plan,
        "total_days": len(weak_points),
        "total_time": len(weak_points) * time_per_topic
    }


if __name__ == "__main__":
    mcp.run()