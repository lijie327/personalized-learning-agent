"""学生画像 / 学习计划 / 知识图谱可视化接口。"""

from datetime import datetime
from typing import Dict, Any, Optional

from fastapi import APIRouter, HTTPException

from backend.rag import load_course_data

import backend.runtime as runtime

router = APIRouter(tags=["student"])


@router.get("/student/{student_id}/profile")
async def get_student_profile(student_id: str, session_id: Optional[str] = None):
    """
    获取学生完整画像。

    整合三层记忆：
    - 短期：当前会话上下文
    - 中期：跨学科薄弱点追踪
    - 长期：知识图谱概览
    """
    if runtime.memory is None:
        raise HTTPException(status_code=500, detail="Memory 未初始化")

    profile = runtime.memory.get_student_profile(student_id, session_id)

    # 添加格式化统计
    profile["summary"] = {
        "total_weak_points": len(profile.get("weak_points", [])),
        "total_strengths": len(profile.get("strengths", [])),
        "subjects_covered": profile.get("knowledge_graph", {}).get("statistics", {}).get("subjects", []),
        "avg_mastery": profile.get("knowledge_graph", {}).get("statistics", {}).get("avg_mastery", 0),
    }

    return profile


@router.get("/student/{student_id}/study-plan")
async def get_study_plan(student_id: str, target_subject: Optional[str] = None):
    """
    获取个性化学习计划。

    根据学生薄弱点和知识图谱，生成针对性的学习建议。
    """
    if runtime.memory is None:
        raise HTTPException(status_code=500, detail="Memory 未初始化")

    profile = runtime.memory.get_student_profile(student_id)
    weak_points = profile.get("weak_points_detail", [])
    strengths = profile.get("strengths_detail", [])
    knowledge_graph = profile.get("knowledge_graph", {})

    # 构建学习计划
    plan = {
        "student_id": student_id,
        "generated_at": datetime.now().isoformat(),
        "priority_topics": [],
        "review_topics": [],
        "new_topics": [],
        "daily_schedule": [],
        "estimated_duration": "2-3 周",
    }

    # 优先攻克薄弱点
    for wp in weak_points[:5]:  # 最多 5 个优先项
        topic = wp.get("topic", "")
        score = wp.get("score", 0)
        subject = wp.get("subject", "")

        if target_subject and subject != target_subject:
            continue

        plan["priority_topics"].append({
            "topic": topic,
            "subject": subject,
            "current_mastery": score,
            "target_mastery": 0.8,
            "recommended_exercises": 5,
            "priority": "high" if score < 0.4 else "medium",
        })

    # 复习已掌握但可能遗忘的知识点
    for s in strengths[:3]:
        topic = s.get("topic", "")
        subject = s.get("subject", "")

        if target_subject and subject != target_subject:
            continue

        plan["review_topics"].append({
            "topic": topic,
            "subject": subject,
            "review_frequency": "每周 1 次",
        })

    # 建议新知识点（从知识库中获取）
    if runtime.knowledge_base:
        available_subjects = runtime.knowledge_base.list_subjects()
        for subj in available_subjects:
            if target_subject and subj != target_subject:
                continue

            topics = runtime.knowledge_base.list_topics(subj)
            for topic in topics:
                # 排除已学过的
                if topic not in [wp.get("topic") for wp in weak_points] and \
                   topic not in [s.get("topic") for s in strengths]:
                    plan["new_topics"].append({
                        "topic": topic,
                        "subject": subj,
                        "difficulty": "easy",  # 新知识点建议从简单开始
                    })

    # 生成每日学习计划（示例）
    if plan["priority_topics"]:
        plan["daily_schedule"] = [
            {
                "day": "周一",
                "focus": plan["priority_topics"][0].get("topic", "基础概念"),
                "duration": "45 分钟",
                "activities": ["观看讲解", "做练习题", "提交答案"],
            },
            {
                "day": "周二",
                "focus": "巩固复习",
                "duration": "30 分钟",
                "activities": ["回顾前一天内容", "做拓展练习"],
            },
            {
                "day": "周三",
                "focus": plan["priority_topics"][1].get("topic", "进阶内容") if len(plan["priority_topics"]) > 1 else "自由练习",
                "duration": "45 分钟",
                "activities": ["观看讲解", "做练习题"],
            },
        ]

    return plan


@router.post("/student/{student_id}/update-weak-point")
async def update_weak_point(
    student_id: str,
    topic: str,
    score: float,
    subject: str = "general",
):
    """
    更新学生知识点得分。

    用于记录学生练习成绩，更新薄弱点追踪。
    """
    if runtime.memory is None:
        raise HTTPException(status_code=500, detail="Memory 未初始化")

    runtime.memory.update_weak_point(
        student_id=student_id,
        topic=topic,
        score=score,  # 0-1，越高越好
        subject=subject,
    )

    return {
        "success": True,
        "student_id": student_id,
        "topic": topic,
        "new_score": score,
        "subject": subject,
    }


@router.get("/student/{student_id}/knowledge-graph")
async def get_knowledge_graph_data(student_id: str):
    """
    获取学生知识图谱可视化数据。

    数据来源：
    1. 节点 = 知识库 (knowledge_base) 中的全部课程知识点（作为"应学范围"）
    2. 学生掌握度 = 中期记忆 (WeakPointTracker) 中该学生的实际得分
       - 有数据 → 按实际分数着色
       - 无数据 → 标记为"未学习"（灰色）
    """
    if runtime.memory is None:
        raise HTTPException(status_code=500, detail="Memory 未初始化")

    # 1. 从知识库获取全部课程知识点（图谱的"全集"）
    all_curriculum_topics: Dict[str, list] = {}  # {subject: [topic_name, ...]}
    if runtime.knowledge_base is not None:
        for subject in runtime.knowledge_base.list_subjects():
            all_curriculum_topics[subject] = runtime.knowledge_base.list_topics(subject)
    else:
        # 知识库未初始化时使用外置课程数据兜底
        all_curriculum_topics = load_course_data()

    # 2. 从学生记忆获取实际掌握数据
    profile = runtime.memory.get_student_profile(student_id)
    student_topics = profile.get("all_topics", {})  # {subject: {topic: {score, attempts, ...}}}

    # 3. 合并：课程知识点为底，学生数据叠加
    nodes = []
    links = []
    subject_order: Dict[str, list] = {}  # {subject: [node_id, ...]}  用于生成边

    for subject, topic_names in all_curriculum_topics.items():
        subject_order[subject] = []
        for topic_name in topic_names:
            node_id = f"{subject}_{topic_name}"
            subject_order[subject].append(node_id)

            # 查找学生在该知识点的实际数据
            topic_data = student_topics.get(subject, {}).get(topic_name)
            if topic_data is not None:
                # 有学习记录：使用真实掌握度
                score = topic_data.get("score", 0.5)
                attempts = topic_data.get("attempts", 0)
                status = "mastered" if score >= 0.8 else ("weak" if score < 0.4 else "learning")
            else:
                # 无学习记录：标记为"未学习"
                score = 0.0
                attempts = 0
                status = "unstudied"

            nodes.append({
                "id": node_id,
                "label": topic_name,
                "subject": subject,
                "mastery": round(score, 2),
                "attempts": attempts,
                "mastered": status == "mastered",
                "weak": status == "weak",
                "learning": status == "learning",
                "unstudied": status == "unstudied",
                "size": 6 + score * 8 if status != "unstudied" else 5,
            })

    # 4. 构建边（同一学科内相邻知识点相连，模拟知识依赖关系）
    for subject, node_ids in subject_order.items():
        for i in range(len(node_ids) - 1):
            links.append({
                "source": node_ids[i],
                "target": node_ids[i + 1],
                "weight": 0.5,
            })

    # 5. 统计（只统计有学习记录的知识点）
    studied_nodes = [n for n in nodes if not n.get("unstudied")]
    studied_scores = [n["mastery"] for n in studied_nodes]
    stats = {
        "total_nodes": len(nodes),
        "studied_nodes": len(studied_nodes),
        "unstudied_nodes": len(nodes) - len(studied_nodes),
        "avg_mastery": round(sum(studied_scores) / len(studied_scores), 2) if studied_scores else 0,
        "mastered": len([n for n in studied_nodes if n["mastered"]]),
        "needs_work": len([n for n in studied_nodes if n["weak"]]),
        "subjects": list(all_curriculum_topics.keys()),
    }

    return {
        "student_id": student_id,
        "nodes": nodes,
        "links": links,
        "statistics": stats,
    }
