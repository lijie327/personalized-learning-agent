"""意图识别：检测学生对话意图类型，并生成免 LLM 的即时回应。"""

from enum import Enum
from typing import Any, Dict, List, Optional

# 问候语
_GREETING_KEYWORDS = [
    "你好", "嗨", "hello", "hi", "在吗", "早上好", "下午好", "晚上好",
    "老师好", "哈喽", "hey",
]

# 询问自己的名字/身份（优先级高于自我介绍）
_NAME_QUERY_KEYWORDS = [
    "我叫什么", "我叫啥", "我的名字是什么", "我的名字叫啥",
    "我是谁", "还记得我吗", "你知道我是谁", "知道我叫什么",
    "我的名字是啥", "我名字是什么", "我名字叫啥",
    "你记得我吗", "你认识我吗", "知道我是谁吗",
    "猜猜我是谁",
]

# 自我介绍（提供名字）
_SELF_INTRO_KEYWORDS = [
    "我叫", "我是", "我的名字", "我姓", "我叫作",
]

# 对话历史引用
_HISTORY_REF_KEYWORDS = [
    "上面讲了", "刚才说了", "之前讲了", "你刚才", "你之前",
    "还记得吗", "回顾一下", "再说一遍", "重复一遍", "复习一下",
    "之前那个", "上一次", "上次那个", "刚刚那个",
]

# 自我查询关键词：学生询问自己的学习状况
_SELF_QUERY_KEYWORDS = [
    "我的薄弱", "我的弱项", "我哪里不好", "我不会", "我不懂",
    "我的学习", "我的掌握", "我的进度", "我还需要", "我哪些",
    "我薄弱", "我不太会", "我搞不懂", "我不理解", "还有什么薄弱",
    "薄弱点", "弱点", "弱项", "学习情况", "学习状况",
    "已掌握", "强项", "我的强项", "我擅长", "我学会",
    "知识图谱", "学习统计", "我的水平",
]

# 已知教学科目（模块级别常量，避免每次函数调用时重复创建）
_KNOWN_SUBJECTS = (
    "python", "programming", "编程", "math", "数学",
    "data_structures", "数据结构", "assessment", "评估",
    "general",  # 通用但可能是教学相关，继续走教学流程
)


class IntentType(Enum):
    NAME_QUERY = "name_query"       # 询问自己的名字/身份
    SELF_INTRO = "self_intro"       # 自我介绍（提供了名字）
    HISTORY_REF = "history_ref"      # 引用对话历史
    SELF_QUERY = "self_query"        # 询问学习状况
    GREETING = "greeting"            # 打招呼
    NORMAL = "normal"                # 普通学习问题


def detect_intent(question: str) -> IntentType:
    """
    检测学生问题的意图类型。

    按优先级从高到低检测：
    1. 询问名字（"我叫什么" / "我的名字是什么"）
    2. 对话历史引用（"上面讲了什么"）
    3. 自我介绍（"我叫张三"）—— 注意：必须在名字询问之后检测
    4. 自我查询（"我的薄弱点"）
    5. 问候（"你好"）
    6. 普通问题
    """
    # 优先级最高：询问自己的名字（必须在自我介绍之前，因为"我叫什么"也包含"我叫"）
    if any(kw in question for kw in _NAME_QUERY_KEYWORDS):
        return IntentType.NAME_QUERY

    # 对话历史引用
    if any(kw in question for kw in _HISTORY_REF_KEYWORDS):
        return IntentType.HISTORY_REF

    # 自我介绍：匹配关键词且能提取到有效姓名
    if any(kw in question for kw in _SELF_INTRO_KEYWORDS):
        name = _extract_name_from_intro(question)
        if name:
            return IntentType.SELF_INTRO
        # 有关键词但提取不到名字（如"我是谁"），归为名字询问
        return IntentType.NAME_QUERY

    # 自我查询
    if any(kw in question for kw in _SELF_QUERY_KEYWORDS):
        return IntentType.SELF_QUERY

    # 问候
    stripped = question.strip().lower()
    if any(kw in stripped for kw in _GREETING_KEYWORDS):
        return IntentType.GREETING

    return IntentType.NORMAL


def extract_name_from_intro(question: str) -> Optional[str]:
    """从自我介绍中提取学生姓名（支持中文和英文名）。"""
    import re

    patterns = [
        r"我叫\s*([一-龥]{2,4})",
        r"我是\s*([一-龥]{2,4})",
        r"我的名字\s*(?:是|叫)?\s*([一-龥]{2,4})",
        r"我姓\s*([一-龥]{1,2})",
        # 英文名支持
        r"我叫\s*([A-Za-z]{2,20})",
        r"我是\s*([A-Za-z]{2,20})",
        r"我的名字\s*(?:是|叫)?\s*([A-Za-z]{2,20})",
        r"[Mm]y\s+name\s+is\s+([A-Za-z]{2,20})",
        r"[Ii]'?[Mm]\s+([A-Za-z]{2,20})",
    ]
    for pat in patterns:
        m = re.search(pat, question)
        if m:
            return m.group(1)
    return None


def build_greeting_response() -> str:
    """生成问候回复（不走 LLM，即时响应）。"""
    return (
        "👋 你好！我是你的 AI 辅导老师，很高兴见到你！\n\n"
        "我可以帮你：\n"
        "- 📖 讲解 Python 编程知识（函数、变量、类、异常处理等）\n"
        "- 📖 讲解数据结构（数组、链表、栈、队列、树等）\n"
        "- 📝 出练习题并评估你的答案\n"
        "- 📊 分析你的学习薄弱点\n\n"
        "直接问我问题就可以开始学习啦！比如：「讲讲 Python 的函数」"
    )


def build_self_intro_response(name: str) -> str:
    """生成自我介绍确认回复。"""
    return f"你好 **{name}**！我已经记住你的名字了。\n\n有什么想学习的吗？可以直接问我问题哦！"


def build_history_ref_response(context: Optional[str]) -> str:
    """
    根据会话上下文生成回顾回复。

    如果无上下文，提示学生当前没有对话历史。
    """
    if not context:
        return (
            "🤔 目前我们还没有聊过什么呢，这是一个新的对话。\n\n"
            "你想学习什么内容？直接告诉我吧！"
        )
    return (
        f"📝 **我们刚才聊了这些内容：**\n\n{context}\n\n"
        "有什么不清楚的地方吗？可以继续问我！"
    )


def build_name_query_response(student_name: str) -> str:
    """
    根据记忆中存储的学生姓名生成回复。

    如果系统记得学生名字，直接告知；否则提示学生自我介绍。
    """
    if student_name:
        return (
            f"你之前告诉我你叫 **{student_name}**，我一直记得呢！😊\n\n"
            "有什么想学习的吗？"
        )
    else:
        return (
            "我好像还不知道你的名字呢 🤔\n\n"
            "你可以告诉我，比如：「我叫张三」"
        )


def build_self_query_response(profile: Dict[str, Any]) -> str:
    """
    根据学生记忆数据直接生成自我查询回复。

    不走 LLM，直接用存储的学生画像数据构建回答，
    确保薄弱点等信息准确、全面。
    """
    weak_detail = profile.get("weak_points_detail", [])
    strong_detail = profile.get("strengths_detail", [])
    kg = profile.get("knowledge_graph", {})
    stats = kg.get("statistics", {})

    parts = ["📊 **你的学习状况总结**\n"]

    # 薄弱点
    if weak_detail:
        parts.append("## ⚠️ 需要加强的知识点\n")
        for i, wp in enumerate(weak_detail, 1):
            score_pct = wp['score'] * 100
            attempts = wp.get('attempts', 0)
            subject = wp.get('subject', '')
            emoji = "🔴" if wp['score'] < 0.4 else "🟡"
            parts.append(
                f"{i}. {emoji} **{wp['topic']}**（{subject}）— "
                f"掌握度 {score_pct:.0f}%，已练习 {attempts} 次"
            )
        parts.append("")
    else:
        parts.append("## ⚠️ 需要加强的知识点\n\n暂无记录，继续学习吧！\n")

    # 强项
    if strong_detail:
        parts.append("## ✅ 已掌握的知识点\n")
        for i, s in enumerate(strong_detail, 1):
            score_pct = s['score'] * 100
            subject = s.get('subject', '')
            parts.append(f"{i}. 🟢 **{s['topic']}**（{subject}）— 掌握度 {score_pct:.0f}%")
        parts.append("")

    # 知识图谱统计
    if stats and stats.get("total_nodes", 0) > 0:
        parts.append("## 📈 学习统计\n")
        parts.append(f"- 总知识点数: **{stats.get('total_nodes', 0)}** 个")
        parts.append(f"- 平均掌握度: **{stats.get('avg_mastery', 0) * 100:.0f}%**")
        parts.append(f"- 已掌握（≥80%）: **{stats.get('mastered', 0)}** 个")
        parts.append(f"- 需加强（<60%）: **{stats.get('needs_work', 0)}** 个")
        parts.append("")

    # 建议
    if weak_detail:
        parts.append("## 💡 学习建议\n")
        top_weak = weak_detail[0]['topic']
        parts.append(
            f"建议优先攻克 **{top_weak}**，这是你目前最薄弱的知识点。"
            f"可以直接问我：「请讲解 {top_weak}」开始学习！"
        )

    return "\n".join(parts)


def is_known_subject(subject: str) -> bool:
    """判断 subject 是否属于已知教学科目。"""
    subject_lower = (subject or "").lower()
    return any(s in subject_lower for s in _KNOWN_SUBJECTS)
