#!/usr/bin/env python
"""
生成虚拟学生数据脚本
在 ChromaDB 和 JSON 文件中创建模拟的学生学习数据，
用于开发、测试和演示。

用法：
    python scripts/generate_mock_data.py              # 生成默认测试数据
    python scripts/generate_mock_data.py --students 5  # 生成 5 个学生
    python scripts/generate_mock_data.py --reset       # 清除旧数据后重新生成
"""

import sys
import json
import os
import argparse
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any

# 确保项目根目录在 Python 路径中
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from backend.config import UPLOAD_DIR
from backend.llm import QwenEmbeddings
from backend.memory import LearningMemory
from backend.rag import EducationKnowledgeBase


# ===================================================================
#  虚拟学生数据模板
# ===================================================================

MOCK_STUDENTS = [
    {
        "id": "student_001",
        "name": "小明",
        "grade": "高一",
        "weak_points": {
            "python": {
                "函数": {"score": 0.35, "attempts": 3},
                "循环": {"score": 0.45, "attempts": 2},
                "变量": {"score": 0.55, "attempts": 4},
            },
            "data_structures": {
                "链表": {"score": 0.30, "attempts": 2},
            },
        },
        "preferences": {"learning_style": "视觉型", "preferred_time": "晚上"},
    },
    {
        "id": "student_002",
        "name": "小红",
        "grade": "高二",
        "weak_points": {
            "python": {
                "类": {"score": 0.30, "attempts": 4},
                "异常处理": {"score": 0.40, "attempts": 1},
                "列表": {"score": 0.50, "attempts": 3},
            },
            "data_structures": {
                "链表": {"score": 0.55, "attempts": 2},
                "树": {"score": 0.35, "attempts": 1},
            },
        },
        "preferences": {"learning_style": "实践型", "preferred_time": "下午"},
    },
    {
        "id": "student_003",
        "name": "小华",
        "grade": "大一",
        "weak_points": {
            "python": {
                "变量": {"score": 0.70, "attempts": 1},
                "列表": {"score": 0.60, "attempts": 2},
            },
            "data_structures": {
                "栈": {"score": 0.65, "attempts": 2},
            },
        },
        "preferences": {"learning_style": "理论型", "preferred_time": "早晨"},
    },
    {
        "id": "student_004",
        "name": "Alice",
        "grade": "大二",
        "weak_points": {
            "python": {
                "类": {"score": 0.25, "attempts": 5},
                "装饰器": {"score": 0.20, "attempts": 2},
            },
            "data_structures": {
                "队列": {"score": 0.40, "attempts": 3},
                "树": {"score": 0.30, "attempts": 1},
            },
        },
        "preferences": {"learning_style": "听觉型", "preferred_time": "下午"},
    },
    {
        "id": "student_005",
        "name": "小刚",
        "grade": "初三",
        "weak_points": {
            "python": {
                "函数": {"score": 0.60, "attempts": 5},
                "循环": {"score": 0.75, "attempts": 3},
                "变量": {"score": 0.85, "attempts": 2},
            },
            "data_structures": {
                "数组": {"score": 0.70, "attempts": 3},
                "栈": {"score": 0.65, "attempts": 2},
            },
        },
        "preferences": {"learning_style": "实践型", "preferred_time": "早晨"},
    },
]


def generate_session_history(student_id: str, num_sessions: int = 3) -> list:
    """为指定学生生成模拟会话历史。"""
    topic_pool = {
        "student_001": ["Python 函数", "for 循环", "变量与类型", "链表基础"],
        "student_002": ["面向对象编程", "异常处理", "列表操作", "二叉树遍历"],
        "student_003": ["变量赋值", "列表推导式", "栈的应用"],
        "student_004": ["类与继承", "装饰器原理", "队列与BFS", "树的遍历"],
        "student_005": ["函数定义", "递归函数", "数组操作", "栈实现"],
    }
    topics = topic_pool.get(student_id, ["Python 基础", "数据结构入门"])

    sessions = []
    for session_idx in range(num_sessions):
        session_id = f"{student_id}_session_{session_idx}"
        messages = []
        for turn in range(4):
            topic = topics[turn % len(topics)]
            messages.append({
                "role": "user",
                "content": f"请讲解 {topic} 的概念和用法",
                "timestamp": (
                    datetime.now() - timedelta(days=num_sessions - session_idx, hours=turn)
                ).isoformat(),
            })
            messages.append({
                "role": "assistant",
                "content": f"好的，让我来详细讲解 {topic}...\n\n这是关于 {topic} 的详细内容...",
                "agent": "knowledge",
                "timestamp": (
                    datetime.now() - timedelta(days=num_sessions - session_idx, hours=turn, minutes=1)
                ).isoformat(),
            })
        sessions.append({"session_id": session_id, "messages": messages})
    return sessions


def populate_data(memory: LearningMemory, knowledge_base: EducationKnowledgeBase,
                  reset: bool = False, num_students: int = 5):
    """填充所有虚拟数据。"""
    print("=" * 60)
    print("📊 生成虚拟学生数据")
    print("=" * 60)

    students = MOCK_STUDENTS[:num_students]

    # 1. 清空旧数据（如果需要）
    if reset:
        print("\n[1/4] 清除旧数据...")
        for student in students:
            memory.clear_student(student["id"])
        # 清除 session 数据 JSON 文件
        data_dir = ROOT_DIR / "data"
        if data_dir.exists():
            for f in data_dir.glob("*.json"):
                f.unlink()
                print(f"   🗑️  已删除 {f.name}")
        print("   ✅ 旧数据已清除")

    # 2. 填充薄弱点数据（中期记忆 + 长期记忆）
    print(f"\n[2/4] 填充薄弱点数据（{len(students)} 名学生）...")
    for student in students:
        sid = student["id"]
        # 设置学生姓名
        memory.set_metadata(sid, "name", student["name"])
        memory.set_metadata(sid, "grade", student["grade"])
        for pref_key, pref_val in student.get("preferences", {}).items():
            memory.set_metadata(sid, f"pref_{pref_key}", pref_val)

        # 填充薄弱点
        for subject, topics in student["weak_points"].items():
            for topic, stats in topics.items():
                memory.update_weak_point(
                    student_id=sid,
                    topic=topic,
                    score=stats["score"],
                    subject=subject,
                )
                # 额外更新一次以增加 attempts（模拟多次练习）
                for _ in range(stats["attempts"] - 1):
                    memory.mid_term.update_weak_point(
                        student_id=sid,
                        topic=topic,
                        score=stats["score"] + 0.05 * (_ + 1),  # 模拟逐步进步
                        subject=subject,
                    )
        print(f"   ✅ {sid} ({student['name']}): "
              f"{sum(len(t) for t in student['weak_points'].values())} 个薄弱点")

    # 3. 填充知识图谱数据（长期记忆 ChromaDB）
    print("\n[3/4] 填充知识图谱数据...")
    full_topics = {
        "python": ["变量", "函数", "类", "异常处理", "循环", "列表", "字典", "装饰器"],
        "data_structures": ["数组", "链表", "栈", "队列", "树"],
    }
    for student in students:
        sid = student["id"]
        for subject, topics in full_topics.items():
            for topic in topics:
                # 查找该学生的真实分数，否则分配随机分数
                real_score = student["weak_points"].get(subject, {}).get(topic, {}).get("score")
                if real_score is None:
                    real_score = 0.5 + 0.05 * hash(f"{sid}_{topic}") % 10 * 0.05
                memory.long_term.store_knowledge(
                    student_id=sid,
                    topic=topic,
                    content=f"知识点: {topic} (科目: {subject})",
                    mastery=round(real_score, 2),
                    subject=subject,
                )
        print(f"   ✅ {sid}: 知识图谱已更新（{sum(len(t) for t in full_topics.values())} 个节点）")

    # 4. 生成会话历史数据
    print("\n[4/4] 生成会话历史...")
    for student in students:
        sessions = generate_session_history(student["id"])
        for session in sessions:
            for msg in session["messages"]:
                memory.add_session_message(session["session_id"], msg)
        print(f"   ✅ {student['id']}: {len(sessions)} 个会话已生成")

    print("\n" + "=" * 60)
    print("✅ 虚拟数据生成完成！")
    print(f"   - {len(students)} 名学生")
    print(f"   - 薄弱点已写入 data/weak_points.json")
    print(f"   - 知识图谱已写入 chroma_db/")
    print(f"   - 会话历史已生成")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="生成虚拟学生数据")
    parser.add_argument("--students", type=int, default=5,
                        help="生成的学生数量（默认 5）")
    parser.add_argument("--reset", action="store_true",
                        help="清除旧数据后重新生成")
    args = parser.parse_args()

    # 初始化组件
    print("🔧 初始化组件...")
    memory = LearningMemory(
        session_max_history=50,
        session_ttl=3600,
        persist_directory=str(ROOT_DIR / "chroma_db"),
        data_dir=str(ROOT_DIR / "data"),
    )
    knowledge_base = EducationKnowledgeBase(
        persist_directory=str(ROOT_DIR / "chroma_db"),
    )

    # 确保知识库已初始化
    for subject in ["python", "data_structures"]:
        knowledge_base._get_or_create_collection(subject)

    populate_data(memory, knowledge_base, reset=args.reset, num_students=args.students)


if __name__ == "__main__":
    main()
