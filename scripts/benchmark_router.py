"""
路由准确率评测脚本（Router Accuracy Benchmark）

用途：
- 用一份人工标注的测试集，调用 RouterAgent.aclassify 对每条学生问题做意图分类，
- 与标注的「期望 Agent」对比，统计整体准确率、各类别 Precision / Recall / F1、混淆矩阵。
- 结果可复现：默认把路由 LLM 的 temperature 强制置 0。

运行方式：
    python scripts/benchmark_router.py                 # 跑全部
    python scripts/benchmark_router.py --limit 10       # 只跑前 10 条（省钱试水）
    python scripts/benchmark_router.py --out report.json  # 导出 JSON 报告

依赖：
- 需要 DASHSCOPE_API_KEY（在 .env 或环境变量中）并联网调用 DashScope。
- 若缺失，RouterAgent 会走关键词规则兜底，仍会产出预测——此时测的是「规则」而非「LLM」。
- 不会自动运行，也不会在后台消耗 token；只有你手动执行上面命令时才跑一次。

说明：
- 测试集是自带的标注样例，覆盖 4 类目标 Agent。如需更贴近真实分布，可增删 TEST_CASES。
- 边界问题（如「栈是什么」可能被分到 programming 或 knowledge）属于真实歧义，
  评测下来若发现大量错分，正好用来定位 Router 的 prompt / 规则短板。
"""

import argparse
import asyncio
import json
import sys
from collections import defaultdict
from pathlib import Path

# 确保项目根目录在 sys.path，使 `import backend` 可用（无论从哪个 cwd 运行）
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except Exception:
    pass

from backend.agents.router_agent import RouterAgent
from backend.models import AgentType

# 目标 Agent 类型（路由可能落到的 4 个 specialist）
AGENT_TYPES = ["math", "programming", "knowledge", "assessor"]

# 人工标注测试集：(学生问题, 期望路由到的 AgentType 值)
# 覆盖四类，尽量贴近真实学生提问口吻。
TEST_CASES = [
    # ------------------------- math -------------------------
    ("帮我求解一元二次方程 x^2 - 5x + 6 = 0", "math"),
    ("什么是导数？怎么求 f(x)=x^3 的导数", "math"),
    ("请证明勾股定理", "math"),
    ("概率论里条件概率 P(A|B) 怎么算", "math"),
    ("帮我算一下这个积分 ∫x^2 dx", "math"),
    ("线性代数里两个矩阵怎么相乘", "math"),
    ("这题极限 lim(x→0) sin x / x 等于多少", "math"),

    # ---------------------- programming ----------------------
    ("Python 里怎么定义一个类？", "programming"),
    ("我的代码报 NameError: name 'x' is not defined 怎么改", "programming"),
    ("用 Python 写一个递归求斐波那契数列", "programming"),
    ("链表和数组有什么区别？", "programming"),
    ("怎么用 Python 读取一个 CSV 文件", "programming"),
    ("帮我 debug 这段 Python 代码为什么死循环", "programming"),
    ("什么是算法的时间复杂度", "programming"),

    # ---------------------- knowledge ----------------------
    ("能给我讲讲什么是面向对象编程吗", "knowledge"),
    ("解释一下 HTTP 和 HTTPS 的区别", "knowledge"),
    ("操作系统里的进程和线程有什么区别", "knowledge"),
    ("数据库索引是用来做什么的", "knowledge"),
    ("讲解一下 TCP 三次握手的过程", "knowledge"),
    ("什么是数据结构里的栈", "knowledge"),

    # ---------------------- assessor ----------------------
    ("帮我出一套 Python 函数的练习题来测测我的水平", "assessor"),
    ("评估一下我对链表知识点的掌握程度", "assessor"),
    ("分析一下我目前的薄弱点在哪里", "assessor"),
    ("给我做个小测验看看我学得怎么样", "assessor"),
    ("测试一下我对 Python 类的理解", "assessor"),
    ("帮我测评一下现在的编程水平", "assessor"),
]


def _normalize(agent_type) -> str:
    """把 RouterAgent 返回的 agent_type（可能是枚举或字符串）归一为值字符串。"""
    if isinstance(agent_type, AgentType):
        return agent_type.value
    if hasattr(agent_type, "value"):
        return str(agent_type.value)
    return str(agent_type)


async def run_benchmark(limit: int, out_path: str) -> dict:
    router = RouterAgent()
    # 可复现：强制把路由 LLM 的温度置 0（RouterAgent 默认 0.3）
    try:
        router.llm.temperature = 0
    except Exception:
        pass

    cases = TEST_CASES[:limit] if limit and limit > 0 else TEST_CASES
    total = len(cases)
    correct = 0

    # 混淆矩阵：confusion[gold][pred]
    confusion = {a: {b: 0 for b in AGENT_TYPES} for a in AGENT_TYPES}
    details = []

    for i, (question, expected) in enumerate(cases, 1):
        try:
            res = await router.aclassify(question)
            predicted = _normalize(res.get("agent_type"))
        except Exception as exc:  # 极端兜底，理论上 aclassify 内部已吞异常
            predicted = f"ERROR:{type(exc).__name__}"

        is_ok = (predicted == expected)
        correct += is_ok

        if expected in confusion and predicted in confusion:
            confusion[expected][predicted] += 1

        details.append({
            "index": i,
            "question": question,
            "expected": expected,
            "predicted": predicted,
            "correct": is_ok,
        })

        mark = "OK " if is_ok else "XX "
        print(f"[{i:>2}/{total}] {mark} exp={expected:<11} pred={predicted:<11} {question[:28]}")

    # ---- 汇总指标 ----
    accuracy = (correct / total) if total else 0.0
    per_class = {}
    for a in AGENT_TYPES:
        tp = confusion[a][a]
        fn = sum(confusion[a][p] for p in AGENT_TYPES if p != a)
        fp = sum(confusion[e][a] for e in AGENT_TYPES if e != a)
        support = tp + fn
        precision = (tp / (tp + fp)) if (tp + fp) else 0.0
        recall = (tp / (tp + fn)) if (tp + fn) else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
        per_class[a] = {
            "support": support,
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
        }

    report = {
        "task": "router_accuracy",
        "model_temperature": 0,
        "total": total,
        "accuracy": round(accuracy, 4),
        "per_class": per_class,
        "confusion_matrix": confusion,
        "details": details,
    }

    # ---- 打印报告 ----
    print("\n" + "=" * 56)
    print(f"路由准确率评测报告  (temperature=0, 共 {total} 条)")
    print("=" * 56)
    print(f"整体准确率 (Accuracy): {accuracy * 100:.1f}%  ({correct}/{total})")
    print("-" * 56)
    print(f"{'Agent':<12}{'Prec':>8}{'Recall':>8}{'F1':>8}{'Support':>9}")
    for a in AGENT_TYPES:
        m = per_class[a]
        print(f"{a:<12}{m['precision']:>8.2f}{m['recall']:>8.2f}{m['f1']:>8.2f}{m['support']:>9}")
    print("-" * 56)
    print("混淆矩阵 (行=期望 / 列=预测):")
    header = "        " + "".join(f"{b[:4]:>6}" for b in AGENT_TYPES)
    print(header)
    for a in AGENT_TYPES:
        row = f"{a:<8}" + "".join(f"{confusion[a][b]:>6}" for b in AGENT_TYPES)
        print(row)
    print("=" * 56)

    if out_path:
        out_file = ROOT / out_path if not Path(out_path).is_absolute() else Path(out_path)
        out_file.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"报告已导出: {out_file}")

    return report


def main():
    parser = argparse.ArgumentParser(description="Router 路由准确率评测")
    parser.add_argument("--limit", type=int, default=0, help="只跑前 N 条（默认 0=全部）")
    parser.add_argument("--out", type=str, default="", help="导出 JSON 报告路径")
    args = parser.parse_args()
    asyncio.run(run_benchmark(args.limit, args.out))


if __name__ == "__main__":
    main()
