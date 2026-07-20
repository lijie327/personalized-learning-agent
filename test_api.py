#!/usr/bin/env python
"""
API 测试脚本
用于测试 Tutor Agent 系统的各个 API 接口。

用法：
    python test_api.py                # 运行全部测试（不含 SSE）
    python test_api.py --all          # 运行全部测试（含 SSE 流式）
    python test_api.py --quick        # 快速冒烟测试（只测关键接口）
    python test_api.py --url http://localhost:8003  # 指定目标地址
"""

import asyncio
import httpx
import json
import sys
import argparse
from datetime import datetime

# Windows: 强制 UTF-8 输出
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

BASE_URL = "http://localhost:8000"

# 测试统计
_stats = {"passed": 0, "failed": 0, "skipped": 0}


def _record(test_name: str, success: bool, detail: str = ""):
    """记录测试结果。"""
    status = "✅" if success else "❌"
    _stats["passed" if success else "failed"] += 1
    print(f"    {status} {detail}" if detail else f"    {status}")


async def test_root():
    """测试服务信息端点（JSON）"""
    print("\n[1] 测试服务信息 GET /api/info...")
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{BASE_URL}/api/info")
            assert resp.status_code == 200, f"期望 200，实际 {resp.status_code}"
            data = resp.json()
            assert "name" in data, "响应缺少 name 字段"
            _record("root", True, f"状态码: {resp.status_code}")
    except Exception as e:
        _record("root", False, str(e))


async def test_health():
    """测试健康检查"""
    print("\n[2] 测试健康检查 GET /health...")
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{BASE_URL}/health")
            assert resp.status_code == 200
            data = resp.json()
            assert data.get("status") == "healthy"
            _record("health", True)
    except Exception as e:
        _record("health", False, str(e))


async def test_preset_students():
    """测试预设学生列表"""
    print("\n[3] 测试预设学生列表 GET /students/preset...")
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{BASE_URL}/students/preset")
            assert resp.status_code == 200
            data = resp.json()
            assert "students" in data
            assert data.get("count", 0) >= 3  # 至少 3 个预设学生
            _record("preset_students", True, f"共 {data['count']} 名学生")
    except Exception as e:
        _record("preset_students", False, str(e))


async def test_preset_student_detail():
    """测试单个预设学生详情"""
    print("\n[4] 测试预设学生详情 GET /students/preset/student_001...")
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{BASE_URL}/students/preset/student_001")
            assert resp.status_code == 200
            data = resp.json()
            assert data.get("name") == "小明"
            assert "weak_points" in data
            _record("student_detail", True, f"学生: {data['name']}")
    except Exception as e:
        _record("student_detail", False, str(e))


async def test_student_not_found():
    """测试不存在的学生返回 404"""
    print("\n[5] 测试不存在的学生 GET /students/preset/nonexistent...")
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{BASE_URL}/students/preset/nonexistent")
            assert resp.status_code == 404
            _record("student_404", True)
    except Exception as e:
        _record("student_404", False, str(e))


async def test_student_profile():
    """测试学生画像"""
    print("\n[6] 测试学生画像 GET /api/student/student_001/profile...")
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{BASE_URL}/api/student/student_001/profile")
            assert resp.status_code == 200
            data = resp.json()
            assert data.get("student_id") == "student_001"
            assert "weak_points" in data
            assert "summary" in data
            _record("student_profile", True,
                    f"薄弱点: {len(data.get('weak_points', []))} 个, "
                    f"强项: {len(data.get('strengths', []))} 个")
    except Exception as e:
        _record("student_profile", False, str(e))


async def test_study_plan():
    """测试学习计划"""
    print("\n[7] 测试学习计划 GET /api/student/student_001/study-plan...")
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{BASE_URL}/api/student/student_001/study-plan")
            assert resp.status_code == 200
            data = resp.json()
            assert "priority_topics" in data
            assert "daily_schedule" in data
            _record("study_plan", True,
                    f"优先学习: {len(data.get('priority_topics', []))} 个知识点")
    except Exception as e:
        _record("study_plan", False, str(e))


async def test_knowledge_topics():
    """测试知识库主题列表"""
    print("\n[8] 测试知识库主题列表 GET /api/knowledge/topics...")
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{BASE_URL}/api/knowledge/topics?subject=python")
            assert resp.status_code == 200
            data = resp.json()
            assert "topics" in data
            assert len(data["topics"]) >= 2
            _record("knowledge_topics", True,
                    f"科目: {data['subject']}, 主题: {data['topics']}")
    except Exception as e:
        _record("knowledge_topics", False, str(e))


async def test_knowledge_search():
    """测试知识库检索"""
    print("\n[9] 测试知识库检索 GET /api/knowledge/search...")
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{BASE_URL}/api/knowledge/search",
                params={"query": "Python 变量", "subject": "python", "k": 3},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert "results" in data
            _record("knowledge_search", True, f"检索到 {data['count']} 条结果")
    except Exception as e:
        _record("knowledge_search", False, str(e))


async def test_exercise_generate():
    """测试练习题生成"""
    print("\n[10] 测试练习题生成 POST /api/exercise/generate...")
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            payload = {
                "topic": "函数",
                "difficulty": "medium",
                "subject": "python",
                "count": 2,
            }
            resp = await client.post(f"{BASE_URL}/api/exercise/generate", json=payload)
            assert resp.status_code == 200
            data = resp.json()
            assert len(data.get("exercises", [])) > 0
            _record("exercise_generate", True,
                    f"生成了 {len(data['exercises'])} 道题")
    except Exception as e:
        _record("exercise_generate", False, str(e))


async def test_exercise_evaluate():
    """测试答案评估"""
    print("\n[11] 测试答案评估 POST /api/exercise/evaluate...")
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            payload = {
                "question": "写一个 Python 函数，计算两个数的和。",
                "student_answer": "def add(a, b):\n    return a + b",
                "correct_answer": "def add(a, b):\n    \"\"\"计算两个数的和。\"\"\"\n    return a + b",
                "student_id": "student_001",
                "topic": "函数",
            }
            resp = await client.post(f"{BASE_URL}/api/exercise/evaluate", json=payload)
            assert resp.status_code == 200
            data = resp.json()
            assert "score" in data
            assert "feedback" in data
            _record("exercise_evaluate", True, f"得分: {data.get('score', 0)}/100")
    except Exception as e:
        _record("exercise_evaluate", False, str(e))


async def test_execute_code():
    """测试代码执行"""
    print("\n[12] 测试代码执行 POST /api/execute-code...")
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            payload = {
                "code": "print('Hello, World!')\nresult = sum([1, 2, 3])\nprint(f'Sum: {result}')",
                "language": "python",
                "timeout": 5,
            }
            resp = await client.post(f"{BASE_URL}/api/execute-code", json=payload)
            assert resp.status_code == 200
            data = resp.json()
            assert data.get("success") is True
            _record("execute_code", True,
                    f"输出: {data.get('output', '')[:50]}... "
                    f"耗时: {data.get('execution_time', 0)}ms")
    except Exception as e:
        _record("execute_code", False, str(e))


async def test_execute_code_error():
    """测试代码执行——语法错误"""
    print("\n[13] 测试代码执行——语法错误 POST /api/execute-code...")
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            payload = {"code": "def broken(", "language": "python", "timeout": 5}
            resp = await client.post(f"{BASE_URL}/api/execute-code", json=payload)
            assert resp.status_code == 200
            data = resp.json()
            assert data.get("success") is False
            _record("execute_code_error", True, f"正确返回错误: {data.get('error', '')[:60]}")
    except Exception as e:
        _record("execute_code_error", False, str(e))


async def test_execute_code_unsupported_language():
    """测试代码执行——不支持的语言"""
    print("\n[14] 测试代码执行——不支持的语言 POST /api/execute-code...")
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            payload = {"code": "console.log('hi')", "language": "javascript", "timeout": 5}
            resp = await client.post(f"{BASE_URL}/api/execute-code", json=payload)
            assert resp.status_code == 200
            data = resp.json()
            assert data.get("success") is False
            assert "不支持" in data.get("error", "")
            _record("unsupported_lang", True)
    except Exception as e:
        _record("unsupported_lang", False, str(e))


async def test_update_weak_point():
    """测试更新薄弱点"""
    print("\n[15] 测试更新薄弱点 POST /api/student/student_001/update-weak-point...")
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{BASE_URL}/api/student/student_001/update-weak-point",
                params={"topic": "测试知识点", "score": 0.75, "subject": "python"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data.get("success") is True
            _record("update_weak_point", True)
    except Exception as e:
        _record("update_weak_point", False, str(e))


async def test_session_management():
    """测试会话管理"""
    print("\n[16] 测试会话管理 DELETE/GET /api/session/...")
    test_sid = "test_session_api_001"
    try:
        async with httpx.AsyncClient() as client:
            # 清除会话
            resp_del = await client.delete(f"{BASE_URL}/api/session/{test_sid}")
            assert resp_del.status_code == 200
            # 获取历史
            resp_get = await client.get(f"{BASE_URL}/api/session/{test_sid}/history")
            assert resp_get.status_code == 200
            _record("session_management", True)
    except Exception as e:
        _record("session_management", False, str(e))


async def test_mcp_tools_list():
    """测试 MCP 工具列表"""
    print("\n[17] 测试 MCP 工具列表 GET /api/mcp/tools...")
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{BASE_URL}/api/mcp/tools")
            assert resp.status_code == 200
            data = resp.json()
            _record("mcp_tools", True, f"MCP 工具数: {data.get('count', 0)}")
    except Exception as e:
        _record("mcp_tools", False, str(e))


async def test_tutor_stream():
    """测试 SSE 流式辅导"""
    print("\n[18] 测试 SSE 流式辅导 POST /api/tutor...")
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            payload = {
                "question": "什么是 Python 的函数？怎么定义一个函数？",
                "session_id": "test_session_sse_001",
                "student_id": "student_001",
                "subject": "python",
                "mode": "direct",
            }

            async with client.stream("POST", f"{BASE_URL}/api/tutor", json=payload) as resp:
                assert resp.status_code == 200
                assert "text/event-stream" in resp.headers.get("content-type", "")

                route_found = False
                token_count = 0
                done_found = False

                async for line in resp.aiter_lines():
                    if line.startswith("data:"):
                        data = json.loads(line[5:].strip())
                        msg_type = data.get("type", "")
                        if msg_type == "route":
                            route_found = True
                        elif msg_type == "token":
                            token_count += 1
                        elif msg_type == "done":
                            done_found = True
                        elif msg_type == "error":
                            raise RuntimeError(f"SSE 错误: {data.get('error')}")

                assert route_found, "未收到 route 事件"
                assert token_count > 0, "未收到任何 token"
                assert done_found, "未收到 done 事件"
                _record("tutor_stream", True, f"收到 {token_count} 个 token")
    except Exception as e:
        _record("tutor_stream", False, str(e))


async def test_tutor_greeting():
    """测试 SSE 流式——问候语意图识别"""
    print("\n[19] 测试 SSE 流式——问候语 POST /api/tutor...")
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            payload = {
                "question": "你好",
                "session_id": "test_session_greeting",
                "student_id": "student_001",
                "mode": "direct",
            }
            async with client.stream("POST", f"{BASE_URL}/api/tutor", json=payload) as resp:
                assert resp.status_code == 200
                async for line in resp.aiter_lines():
                    if line.startswith("data:"):
                        data = json.loads(line[5:].strip())
                        if data.get("type") == "route":
                            assert data.get("agent") == "memory"
                            _record("tutor_greeting", True, "意图正确识别为 greeting")
                            return
                _record("tutor_greeting", False, "未收到 route 事件")
    except Exception as e:
        _record("tutor_greeting", False, str(e))


async def test_self_intro():
    """测试 SSE 流式——自我介绍"""
    print("\n[20] 测试 SSE 流式——自我介绍 POST /api/tutor...")
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            payload = {
                "question": "我叫张三",
                "session_id": "test_session_intro",
                "student_id": "student_001",
                "mode": "direct",
            }
            async with client.stream("POST", f"{BASE_URL}/api/tutor", json=payload) as resp:
                assert resp.status_code == 200
                async for line in resp.aiter_lines():
                    if line.startswith("data:"):
                        data = json.loads(line[5:].strip())
                        if data.get("type") == "route":
                            assert data.get("agent") == "memory"
                            _record("self_intro", True, "自我介绍被正确识别")
                            return
                _record("self_intro", False, "未收到 route 事件")
    except Exception as e:
        _record("self_intro", False, str(e))


# ===================================================================
#  测试套件
# ===================================================================

QUICK_TESTS = [
    test_root,
    test_health,
    test_preset_students,
    test_knowledge_topics,
    test_student_profile,
]

FULL_TESTS = QUICK_TESTS + [
    test_preset_student_detail,
    test_student_not_found,
    test_study_plan,
    test_knowledge_search,
    test_exercise_generate,
    test_exercise_evaluate,
    test_execute_code,
    test_execute_code_error,
    test_execute_code_unsupported_language,
    test_update_weak_point,
    test_session_management,
    test_mcp_tools_list,
]

STREAM_TESTS = [
    test_tutor_stream,
    test_tutor_greeting,
    test_self_intro,
]


async def run_all_tests(include_streaming: bool = False, quick: bool = False):
    """运行所有测试"""
    if quick:
        test_list = QUICK_TESTS
    elif include_streaming:
        test_list = FULL_TESTS + STREAM_TESTS
    else:
        test_list = FULL_TESTS

    print("=" * 60)
    print("🧪 Tutor Agent API 测试")
    print("=" * 60)
    print(f"测试时间: {datetime.now().isoformat()}")
    print(f"目标地址: {BASE_URL}")
    print(f"测试模式: {'快速冒烟' if quick else '含SSE流式' if include_streaming else '标准'}")
    print(f"测试数量: {len(test_list)}")
    print("=" * 60)

    for test in test_list:
        try:
            await test()
        except Exception as e:
            print(f"    ❌ 未捕获异常: {e}")
            _stats["failed"] += 1

    print("\n" + "=" * 60)
    print(f"📊 测试结果: {_stats['passed']} 通过 / {_stats['failed']} 失败 / {_stats['skipped']} 跳过")
    print("=" * 60)

    return _stats["failed"] == 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Tutor Agent API 测试")
    parser.add_argument("--all", action="store_true", help="运行全部测试（含 SSE 流式）")
    parser.add_argument("--quick", action="store_true", help="快速冒烟测试")
    parser.add_argument("--url", type=str, default=BASE_URL, help="API 地址")
    args = parser.parse_args()

    BASE_URL = args.url
    success = asyncio.run(run_all_tests(
        include_streaming=args.all,
        quick=args.quick,
    ))
    sys.exit(0 if success else 1)
