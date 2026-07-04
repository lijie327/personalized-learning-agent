"""
FastAPI 应用入口
通过 lifespan 管理 Agent 初始化、预设学生数据、CORS 和静态文件。
"""

import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Dict, Any

# Windows: 强制 UTF-8 输出，避免 emoji 等字符导致 UnicodeEncodeError
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, HTMLResponse
from pydantic import BaseModel

# 确保项目根目录在 Python 路径中
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.config import HOST, PORT, UPLOAD_DIR
from backend.llm import QwenEmbeddings
from backend.memory import LearningMemory
from backend.rag import EducationKnowledgeBase
from backend.agents.router_agent import RouterAgent
from backend.agents.math_tutor import MathTutor
from backend.agents.programming_tutor import ProgrammingTutor
from backend.agents.knowledge_agent import KnowledgeAgent, set_shared_knowledge_base
from backend.agents.assessor_agent import AssessorAgent
from backend.tools.mcp_tools import mcp_manager
from backend.api import router as api_router, init_agents


# ===================================================================
#  预设学生数据
# ===================================================================

PRESET_STUDENTS: Dict[str, Dict[str, Any]] = {
    "student_001": {
        "name": "小明",
        "grade": "高一",
        "weak_points": {
            "python": {
                "函数": {"score": 0.35, "attempts": 3},
                "循环": {"score": 0.45, "attempts": 2},
            },
            "math": {
                "一元二次方程": {"score": 0.50, "attempts": 2},
            },
        },
        "preferences": {
            "learning_style": "视觉型",
            "preferred_time": "晚上",
        },
    },
    "student_002": {
        "name": "小红",
        "grade": "高二",
        "weak_points": {
            "python": {
                "类": {"score": 0.30, "attempts": 4},
                "异常处理": {"score": 0.40, "attempts": 1},
            },
            "data_structures": {
                "链表": {"score": 0.55, "attempts": 2},
            },
        },
        "preferences": {
            "learning_style": "实践型",
            "preferred_time": "下午",
        },
    },
    "student_003": {
        "name": "小华",
        "grade": "大一",
        "weak_points": {
            "python": {
                "变量": {"score": 0.70, "attempts": 1},
                "列表": {"score": 0.60, "attempts": 2},
            },
        },
        "preferences": {
            "learning_style": "理论型",
            "preferred_time": "早晨",
        },
    },
}


# ===================================================================
#  Lifespan —— 启动时初始化所有组件
# ===================================================================


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    应用生命周期管理。
    """
    print("=" * 50)
    print("[START] Initializing Tutor Agent System...")
    print("=" * 50)

    # 1. 初始化 Embeddings
    print("[1/8] Initializing QwenEmbeddings...")
    embeddings = QwenEmbeddings()
    print("   [OK] Embeddings ready")

    # 2. 初始化知识库
    print("[2/8] Initializing ChromaDB KnowledgeBase...")
    knowledge_base = EducationKnowledgeBase(
        persist_directory=str(ROOT_DIR / "chroma_db"),
    )
    for subject in ["python", "data_structures"]:
        knowledge_base._get_or_create_collection(subject)
    # 注册全局共享知识库（供 knowledge_search 工具复用，避免重复初始化）
    set_shared_knowledge_base(knowledge_base)
    print("   [OK] KnowledgeBase ready (python / data_structures)")

    # 3. 初始化 Memory
    print("[3/8] Initializing LearningMemory...")
    memory = LearningMemory(
        session_max_history=50,
        session_ttl=3600,
        persist_directory=str(ROOT_DIR / "chroma_db"),
    )
    print("   [OK] Memory ready (3-layer: short/mid/long)")

    # 4. 加载预设学生数据（中期 + 长期，update_weak_point 自动同步长期）
    print("[4/8] Loading preset students...")
    for student_id, data in PRESET_STUDENTS.items():
        weak_points = data.get("weak_points", {})
        for subject, topics in weak_points.items():
            for topic, stats in topics.items():
                score = stats.get("score", 0.5)
                memory.update_weak_point(
                    student_id=student_id,
                    topic=topic,
                    score=score,
                    subject=subject,
                )
    print(f"   [OK] Loaded {len(PRESET_STUDENTS)} preset students (synced to knowledge graph)")

    # 5. 加载 MCP 工具
    print("[5/8] Loading MCP tools...")
    mcp_tools = []
    try:
        mcp_tools = await mcp_manager.load_tools()
    except RuntimeError as e:
        print(f"   [WARN] MCP tools load failed (continuing with local tools): {e}")
    print(f"   [OK] MCP tools loaded: {len(mcp_tools)} total")

    # 6. 初始化各 Tutor Agent（注入 MCP 工具和 Memory）
    print("[6/8] Initializing Tutor Agents...")
    math_tutor = MathTutor(name="MathTutor", mcp_tools=mcp_tools, memory=memory)
    print("   [OK] MathTutor ready")
    programming_tutor = ProgrammingTutor(name="CodeTutor", mcp_tools=mcp_tools, memory=memory)
    print("   [OK] CodeTutor ready")
    knowledge_agent = KnowledgeAgent(name="KnowledgeAgent", mcp_tools=mcp_tools, memory=memory, knowledge_base=knowledge_base)
    print("   [OK] KnowledgeAgent ready")
    assessor_agent = AssessorAgent(name="AssessorAgent", mcp_tools=mcp_tools, memory=memory)
    print("   [OK] AssessorAgent ready")

    # 7. 初始化 Router Agent
    print("[7/8] Initializing RouterAgent...")
    router_agent = RouterAgent()
    print("   [OK] RouterAgent ready")

    # 8. 注册到 api 模块
    print("[8/8] Registering agents to API...")
    init_agents(
        router=router_agent,
        math=math_tutor,
        programming=programming_tutor,
        knowledge=knowledge_agent,
        assessor=assessor_agent,
        mem=memory,
        kb=knowledge_base,
        mcp_tool_list=mcp_tools,
    )
    print("   [OK] API registration done")

    print("=" * 50)
    print("[READY] Tutor Agent System initialized!")
    print(f"   URL: http://{HOST}:{PORT}")
    print(f"   Docs: http://{HOST}:{PORT}/docs")
    print("=" * 50)

    app.state.embeddings = embeddings
    app.state.knowledge_base = knowledge_base
    app.state.memory = memory
    app.state.router_agent = router_agent
    app.state.math_tutor = math_tutor
    app.state.programming_tutor = programming_tutor
    app.state.knowledge_agent = knowledge_agent
    app.state.assessor_agent = assessor_agent
    app.state.mcp_tools = mcp_tools

    yield

    print("\n[CLEANUP] Cleaning resources...")
    memory.cleanup_expired_sessions()
    # 关闭 MCP Server 连接
    try:
        await mcp_manager.close()
        print("[CLEANUP] MCP connections closed")
    except Exception as e:
        print(f"[CLEANUP] MCP cleanup warning: {e}")
    print("[CLEANUP] Done. Goodbye!")


# ===================================================================
#  创建 FastAPI 应用
# ===================================================================

app = FastAPI(
    title="Tutor Agent 教学辅导系统",
    description="基于 LangGraph 的多 Agent 教学辅导系统",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 静态文件
uploads_path = Path(UPLOAD_DIR)
uploads_path.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(uploads_path)), name="uploads")

frontend_dir = ROOT_DIR / "frontend"
if frontend_dir.exists():
    app.mount("/static", StaticFiles(directory=str(frontend_dir)), name="frontend")

# 注册路由
app.include_router(api_router)


# ===================================================================
#  根路由 - 返回前端页面
# ===================================================================

@app.get("/", tags=["root"])
async def root():
    """返回前端页面"""
    index_path = ROOT_DIR / "frontend" / "index.html"
    if index_path.exists():
        return HTMLResponse(index_path.read_text(encoding="utf-8"))
    return {
        "name": "Tutor Agent 教学辅导系统",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
        "api_prefix": "/api",
        "available_agents": ["router", "math", "programming", "knowledge", "assessor"],
    }


@app.get("/health", tags=["health"])
async def health_check():
    return {
        "status": "healthy",
        "timestamp": __import__("datetime").datetime.now().isoformat(),
    }


# ===================================================================
#  预设学生信息接口
# ===================================================================

class StudentInfo(BaseModel):
    id: str
    name: str
    grade: str
    weak_points_summary: Dict[str, int]


@app.get("/students/preset", tags=["students"])
async def list_preset_students():
    students = []
    for sid, data in PRESET_STUDENTS.items():
        weak_count = sum(len(topics) for topics in data.get("weak_points", {}).values())
        students.append({
            "id": sid,
            "name": data.get("name", ""),
            "grade": data.get("grade", ""),
            "weak_points_count": weak_count,
            "preferences": data.get("preferences", {}),
        })
    return {"students": students, "count": len(students)}


@app.get("/students/preset/{student_id}", tags=["students"])
async def get_preset_student(student_id: str):
    if student_id not in PRESET_STUDENTS:
        raise HTTPException(status_code=404, detail=f"学生 {student_id} 不存在")
    data = PRESET_STUDENTS[student_id]
    return {
        "id": student_id,
        "name": data.get("name", ""),
        "grade": data.get("grade", ""),
        "weak_points": data.get("weak_points", {}),
        "preferences": data.get("preferences", {}),
    }


# ===================================================================
#  全局异常处理
# ===================================================================

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": True, "status_code": exc.status_code, "message": exc.detail, "path": str(request.url.path)},
    )


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    return JSONResponse(
        status_code=400,
        content={"error": True, "status_code": 400, "message": str(exc), "type": "ValueError", "path": str(request.url.path)},
    )


@app.exception_handler(RuntimeError)
async def runtime_error_handler(request: Request, exc: RuntimeError):
    return JSONResponse(
        status_code=500,
        content={"error": True, "status_code": 500, "message": str(exc), "type": "RuntimeError", "path": str(request.url.path)},
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    import traceback
    return JSONResponse(
        status_code=500,
        content={
            "error": True, "status_code": 500,
            "message": f"内部错误: {str(exc)}",
            "type": exc.__class__.__name__,
            "path": str(request.url.path),
            "traceback": traceback.format_exc() if app.debug else None,
        },
    )


# ===================================================================
#  启动入口
# ===================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host=HOST, port=PORT, reload=True, log_level="info")