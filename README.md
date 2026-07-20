# Tutor Agent 教学辅导系统

基于 **FastAPI + LangGraph 多 Agent 编排**的智能教学辅导系统，集成 RAG 知识库、三层记忆管理与 MCP 工具协议，提供个性化、流式（SSE）的 AI 辅导。

## 界面预览

![智慧教育平台界面预览](assets/ui-screenshot.png)

## 核心特性

- **多 Agent 协作**：Router 路由 + 4 个 ReAct specialist（math / programming / knowledge / assessor），真实 tool-calling 而非文本注入
- **RAG 知识库**：ChromaDB 向量存储 + 混合检索（向量相似度 + 关键词重排），可扩展课程资料
- **三层记忆**：短期（Redis，TTL 过期）/ 中期（JSON + Redis 薄弱点追踪）/ 长期（ChromaDB 知识图谱）
- **SSE 流式交互**：逐 token 推送，含路由 / token / 代码校验 / 完成等多类型事件
- **代码沙箱**：浏览器内 Python 执行，沙箱守卫拦截 os/subprocess/socket 与 eval/exec（RCE 防护）
- **图片分析**：上传题目截图，qwen-vl-max 视觉模型识别公式 / 代码 / 图表
- **MCP 工具**：以 Model Context Protocol 暴露代码执行能力，可插拔扩展

## LangGraph 多 Agent 编排

主链路采用 **supervisor 多 Agent** 模式（`StateGraph` 调度）：

- **Supervisor 路由**：复用 Router 分类结果 `agent_type`，经条件边直达对应 specialist，无额外 LLM 调用
- **4 个 ReAct specialist**：`create_react_agent` 编译，LLM 自主决策调用工具（RAG 检索 / 代码沙箱 / 练习生成 / 答案评估）
- **共享状态**：基于 `MessagesState` 的 `add_messages`，specialist 与 supervisor 共享对话历史
- **流式输出**：编译图经 `astream_events(v2)` 把模型流 / 工具结束 / 链结束事件映射为 SSE，逐 token 推送到前端

链路：`START →(按 agent_type 路由)→ specialist → update_memory → generate_exercises → END`

## 系统架构

```
┌──────────────────────────────────────────────────────────┐
│                       Frontend                           │
│          HTML5 + CSS3 + Vanilla JS + D3.js               │
│               SSE Stream Consumer                        │
└──────────────────────┬───────────────────────────────────┘
                       │ HTTP/SSE
┌──────────────────────▼───────────────────────────────────┐
│                   FastAPI Server                         │
│  ┌─────────────────────────────────────────────────────┐ │
│  │                  Router Agent                       │ │
│  │          (关键词预分类 + LLM分类 + 规则兜底)           │ │
│  └──────┬──────────┬──────────┬───────────┬───────────┘ │
│         │          │          │           │              │
│  ┌──────▼──┐ ┌─────▼───┐ ┌───▼────┐ ┌───▼────────┐     │
│  │  Math   │ │Program- │ │Know-   │ │ Assessor   │     │
│  │  Tutor  │ │ming     │ │ledge   │ │ Agent      │     │
│  │         │ │Tutor    │ │Agent   │ │            │     │
│  └────┬────┘ └────┬────┘ └───┬────┘ └─────┬──────┘     │
│       │           │          │             │             │
│  ┌────▼───────────▼──────────▼─────────────▼──────┐     │
│  │              LearningMemory                     │     │
│  │   Short-term(Redis) / Mid-term(JSON) /          │     │
│  │   Long-term(ChromaDB)                           │     │
│  └──────────────────────┬──────────────────────────┘     │
│                         │                                 │
│  ┌──────────────────────▼──────────────────────────┐     │
│  │        EducationKnowledgeBase (ChromaDB)         │     │
│  │         Python / Data Structures RAG             │     │
│  └─────────────────────────────────────────────────┘     │
│                                                          │
│  ┌─────────────────────────────────────────────────┐     │
│  │            MCP Tool Server: Code Executor         │     │
│  └─────────────────────────────────────────────────┘     │
└──────────────────────┬───────────────────────────────────┘
                       │
┌──────────────────────▼───────────────────────────────────┐
│            Alibaba Cloud DashScope (Qwen)                 │
│       LLM: qwen-max  |  Embedding: text-embedding-v2      │
│       Vision: qwen-vl-max                                 │
└──────────────────────────────────────────────────────────┘
```

## 核心链路

1. 前端 POST `/api/tutor`（SSE），携带 `question / student_id / session_id / subject / mode`
2. Router 先**关键词预分类**（数学/数据结构概念题直接定类），未命中再走 LLM 分类 + 规则兜底
3. supervisor 按 `agent_type` 路由到对应 specialist 子图，子图通过 tool-calling 调用 RAG / 沙箱 / 练习工具
4. 结果经 `astream_events` 映射为 SSE 事件流回前端；会话记忆写入 Redis，薄弱点与知识图谱写入 ChromaDB

## 工程难点与亮点

- **全链路异步 + 真流式**：FastAPI `async` + `astream_events(v2)` 映射 SSE，视觉模型等同步调用下沉线程池，不阻塞事件循环
- **真实 tool-calling 编排**：LangGraph `create_react_agent` 让 LLM 自主决定工具调用，而非把工具结果硬塞进 Prompt
- **代码沙箱 RCE 防护**：子进程隔离 + 沙箱守卫（拦截危险模块与 `eval/exec`）+ 交互输入拦截 + 超时熔断
- **RAG 混合检索**：向量相似度召回 + 关键词重排，检索增强教学回答
- **Redis 降级**：`protocol=2` 兼容老版本 Redis，连接失败自动降级为内存存储，启动不崩
- **MCP 健壮性**：单 server 重试 + 错开启动，缓解 Windows stdio 子进程握手竞态；加载失败自动降级本地工具
- **路由评测闭环**：`scripts/benchmark_router.py` 内置 26 条标注集，可复现测量路由准确率

## 测试结果

- **路由准确率**：benchmark 实测 **≥90%**（关键词预分类修复了数学/数据结构概念题误分到 knowledge 的问题；早期 80.8%）
- **沙箱安全**：`python backend/test_sandbox.py` 离线验证危险模块（os/subprocess/socket/urllib）与 eval/exec 均被拦截
- **接口冒烟**：`python test_api.py` 覆盖健康检查、练习、代码执行、知识检索、画像、知识图谱、上传、MCP

## 快速开始

```bash
# 1. 依赖（uv.lock 为唯一可信源）
uv sync

# 2. 配置：复制 .env.example 为 .env，填入 DASHSCOPE_API_KEY
cp .env.example .env

# 3. 启动
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

- 前端：http://localhost:8000  ·  API 文档：http://localhost:8000/docs
- 可选 Redis 用于短期记忆（未安装时自动降级内存存储）；`DASHSCOPE_API_KEY` 必填

### Docker

```bash
docker-compose up -d   # app + redis（Chroma 走本地持久卷）
```

## 项目结构

```
education_agent/
├── backend/
│   ├── main.py              # FastAPI 入口，lifespan 初始化
│   ├── api.py               # 路由层（SSE / 练习 / 代码 / 画像 / 上传）
│   ├── config.py            # 配置（环境变量）
│   ├── llm.py               # LLM / Embedding / Vision 封装
│   ├── rag.py               # RAG 知识库（ChromaDB）
│   ├── memory.py            # 三层记忆
│   ├── test_sandbox.py      # 沙箱安全测试
│   ├── agents/router_agent.py   # 路由 Agent（关键词 + LLM + 规则兜底）
│   ├── graph/               # LangGraph supervisor 编排
│   │   ├── agents.py        # 4 个 specialist 提示词 + 构建
│   │   ├── tools.py         # 工具定义
│   │   ├── nodes.py / builder.py / state.py / llm.py
│   └── tools/               # 工具函数（code_executor / code_validator / mcp_tools）
├── frontend/                # HTML/CSS/JS + D3.js
├── mcp_servers/code_executor_server.py  # 唯一 MCP server（复用沙箱）
├── scripts/benchmark_router.py          # 路由评测脚本
├── chroma_db/ data/ uploads/             # 运行产物（已 gitignore）
├── Dockerfile docker-compose.yml pyproject.toml uv.lock
```

## 技术栈

| 类别 | 技术 |
|------|------|
| Web 框架 | FastAPI + Uvicorn（异步 SSE） |
| AI 编排 | LangGraph supervisor 多 Agent（create_react_agent + 真实 tool-calling） |
| 模型 | 阿里云百炼 qwen-max / text-embedding-v2 / qwen-vl-max |
| 向量库 | ChromaDB |
| 记忆 | Redis（短期/中期）+ ChromaDB（长期，可降级） |
| 前端 | 原生 HTML/CSS/JS + D3.js |
| 协议 | SSE / MCP |
| 部署 | Docker + Docker Compose |

MIT License
