# Tutor Agent 教学辅导系统 —— 架构、运行过程与不足分析

> 分析对象：`D:\python\PythonProject\education_agent`（Tutor Agent 教学辅导系统）
> 分析依据：逐文件阅读 `backend/`、`frontend/`、`mcp_servers/`、`docker-compose.yml`、`Dockerfile`、`README.md`、`requirements.txt` 的实际代码，对照文档声明。
> 结论先行：**文档（README 架构图）与实际实现存在多处重大偏差**；核心"多 Agent / RAG / MCP"能力在真正的主链路（`/api/tutor`）中并未落地，多个 Agent 方法为死代码；代码沙箱存在任意代码执行风险；LLM 调用阻塞事件循环。

---

## 一、项目结构概览

```
education_agent/
├── run.py / Dockerfile           # 启动入口（uvicorn，开发 8000 / 容器 8003）
├── backend/
│   ├── main.py                   # FastAPI 应用 + lifespan 初始化（8 步）
│   ├── api.py                    # 全部 API 路由 + SSE 主流程 stream_llm_response
│   ├── config.py / models.py     # 环境变量配置 / 数据模型
│   ├── llm.py                    # QwenLLM / QwenEmbeddings / QwenVisionLLM（OpenAI 兼容 DashScope）
│   ├── rag.py                    # EducationKnowledgeBase（ChromaDB + 混合检索）
│   ├── memory.py                 # 三层记忆：SessionMemory / WeakPointTracker / KnowledgeGraphStore
│   ├── agents/                   # base_tutor + router/math/programming/knowledge/assessor
│   └── tools/                    # code_executor / code_validator / exercise_generator / mcp_tools
├── frontend/                     # index.html / app.js / style.css（原生 JS）
├── mcp_servers/                  # 3 个 stdio MCP Server（代码执行/练习/评估）
├── chroma_db/ data/ uploads/     # 持久化目录
└── docker-compose.yml            # Traefik + 3 实例（python/ds/math）
```

分层职责清晰、注释详尽、降级策略（Redis→内存、MCP→本地、RAG→直答）考虑周到，是项目的优点。

---

## 二、实际运行过程（端到端）

### 1. 启动（`run.py` → `main.py` lifespan）
依次初始化：Embeddings → ChromaDB 知识库 → LearningMemory → 写入预设学生 → 加载 MCP 工具 → 构造 4 个 Tutor Agent + RouterAgent → 注册到 `api.init_agents()`。所有实例挂在 `app.state` 与模块级全局变量上。

### 2. 一次 `/api/tutor` SSE 请求的真实流程（`api.py:stream_llm_response`）
这是系统的**主链路**，实际只做了以下事情：
1. 取学生画像、取最近 10 条对话历史。
2. **意图识别**（`_detect_intent`）：基于硬编码关键词列表（问候/自我介绍/问名字/历史引用/自我查询），命中即绕过 LLM 直接拼文本返回。
3. **路由分类**（`RouterAgent.classify`）：调一次 LLM 输出 JSON（subject / agent_type / confidence），失败则规则兜底。
4. **教学生成**：直接从 `AGENT_MAP` 取 agent 的 `_system_prompt`，再用**手工拼装的 prompt** 调一次 `llm.stream_with_history(...)`，逐 token 通过 SSE 推回前端。`asyncio.sleep(0.01)` 模拟流式间隔。
5. **收尾**：对回复里的代码块做语法校验（`code_validation` 事件）；用"话题是否在问答文本中出现"的启发式更新薄弱点（命中即记 0.60）；根据最弱知识点**推荐练习题**（优先调 MCP `generate_exercise`，失败回退本地 LLM）。

### 3. 真实链路中"缺席"的能力（关键）
- **RAG 检索未进入教学链路**：`KnowledgeAgent.answer_with_sources()`（带教材召回+来源引用）在 `/api/tutor` 中从未被调用。主链路只把学生薄弱点文本和 MCP 工具描述塞进 prompt，**LLM 拿不到检索到的教材内容**。
- **MCP 工具未被 LLM 真正调用**：工具仅以"文字描述"形式注入 prompt；所谓"集成"只有练习推荐时手动调一次 `generate_exercise`。没有 function-calling / ReAct 循环，LLM 无法自主选择并执行工具。
- **AssessorAgent 完全未被任何路由调用**（死代码）。
- **各 Tutor 的 `handle_question / socratic_guide / direct_teach` 方法从未被调用**（死代码）。主链路绕过 Agent 类，直接裸调 `QwenLLM`。

---

## 三、文档声明 vs 代码实现（差距表）

| README 声明 | 代码实际情况 | 严重度 |
|---|---|---|
| "基于 **LangGraph** 多 Agent 架构" | 全仓零 `langgraph`/`StateGraph`/`compile()` 引用；`langgraph` 仅在 `requirements.txt` 中（未 import）。实为手动 `if/else` + 一次 LLM 分类 | 🔴 高（名不副实） |
| "Router → 多专业 Agent 协作" | 仅 Router 分类 + 取 system_prompt；无状态图、无 Agent 间消息传递、无 supervisor | 🔴 高 |
| "RAG 知识库（带混合检索、来源引用）" | RAG 仅在 `/knowledge/search` 与知识图谱接口可用；**主辅导流未接入检索** | 🔴 高 |
| "MCP 工具集成，可扩展练习/代码/评估" | 工具以文本形式注入 prompt，LLM 不能真调用；仅练习推荐手动调一次 | 🟠 中 |
| "三层记忆：短期 Redis / 中期 JSON+Redis / 长期 ChromaDB" | 短期=Redis(可降级内存)；**中期=JSON 文件**（非 Redis）；长期 ChromaDB 仅被 `update_weak_point` 顺带写入，**知识图谱实际数据来自中期 JSON** | 🟠 中 |
| "知识图谱可视化（D3 力导向图）" | 节点=课程知识点清单；**边仅按同科目顺序连成链**，非真实知识依赖关系 | 🟡 低 |
| "Docker 多课程部署（Traefik + Python/DS/数学 3 实例）" | `COURSE_NAME` 在任意 `.py` 文件中**从未被读取**；3 个实例运行完全相同的应用，只是标签不同 → 多租户名存实亡 | 🔴 高 |
| 三层记忆"长期持久化学生画像" | 重启后从 ChromaDB 恢复中期数据（`sync_long_to_mid`）逻辑存在，但图谱统计仍主要依赖 JSON | 🟡 低 |

---

## 四、主要不足（按严重度）

### 🔴 P0 —— 安全 / 功能性硬伤
1. **代码沙箱任意代码执行风险**（`tools/code_executor.py`）
   `execute_python` 用 `subprocess` 跑用户代码，仅做 `ast` 语法检查 + 拦截 `input()`。**未限制 `import os / subprocess / socket / shutil`、未限制文件写出路径、无 seccomp/资源 cgroup**。学生可 `import os; os.system('...')` 以服务器权限执行任意命令（删除文件、反弹 shell 等）。这是最该优先修复的问题。
2. **阻塞式 LLM 调用跑在 async 路由里**（`llm.py` 的 `stream_with_history` 是**同步生成器**，`api.py` 在 async 函数内 `for token in ...` 消费）
   每个 token 的底层网络读取都阻塞事件循环，导致单条长请求会拖垮整个服务的并发能力。应使用 `AsyncOpenAI` 或将同步调用丢进线程池（`run_in_executor`）。
3. **核心能力名不副实（架构诚信/功能性）**
   见第三节。RAG、MCP 真调用、多 Agent 编排均未在主链路落地，文档与实现脱节，对"简历项目"的可信度伤害最大。

### 🟠 P1 —— 正确性与健壮性
4. **掌握度被"话题提及"污染**（`api.py` 第 867–883 行）
   只要知识点名（如"函数"）出现在问题或回复文本里，就调用 `update_weak_point(score=0.60)`。这会把"聊过"误判为"已掌握 60%"，且整段包在 `try/except: pass` 中，失败静默。正确做法：仅当真实练习**答对**才上调掌握度。
5. **CORS 配置非法且不安全**（`main.py`）
   `allow_origins=["*"]` 与 `allow_credentials=True` 同时设置：浏览器会拒绝带凭据的通配，且该组合本身不安全。应明确白名单。
6. **无鉴权、无限流、无启动期 API Key 校验**
   任何人都可调用 `/api/execute-code`、`/api/upload-image`；`DASHSCOPE_API_KEY` 为空时服务照常启动，首个 LLM 调用才在运行时报错。
7. **死代码与冗余依赖**
   `AssessorAgent`、`MathTutor/ProgrammingTutor/KnowledgeAgent` 的多数方法、`langgraph` 依赖、大量 `QwenLLM` 重复实例化（每次请求 new 一个 client，连接池浪费）——均未被主链路使用。

### 🟡 P2 —— 工程卫生
8. **无离线单元测试**：`test_api.py` 需已启动服务 + 有效 DashScope Key 才能跑；业务逻辑零单测。
9. **仓库被依赖污染**：根目录 `test_langchain/`（393 文件，含 `.exe`）、`packages/`（138 个 `.whl`）疑似误提交的 vendored 依赖，应移出或加 `.gitignore`。
10. **`asyncio.get_event_loop()` 已弃用**（`base_tutor.py`、`api.py` 同步 MCP 调用），在运行中的事件循环里调 `asyncio.run` 会抛 `RuntimeError`。
11. **`/exercise/evaluate` 中 `subject="general"` 硬编码**，与 `update_weak_point` 的科目粒度不一致。
12. **意图识别靠脆弱关键词**：如"函数"既在数学规则又在编程规则出现，优先级顺序易误判；无模型兜底分类。

---

## 五、改进建议（按优先级）

**立即做（P0）**
- 沙箱加固：用受限解释器（`ast` 白名单 + 禁用危险 builtins/import）、或丢进独立容器/沙箱进程（如 `nsjail`/Docker、gVisor），限制网络、文件系统、CPU/内存/超时。
- 异步化 LLM：改 `AsyncOpenAI`，让 SSE 流不阻塞事件循环；或把同步 `create(stream=True)` 包进 `run_in_executor`。
- 对齐文档与实现：要么**真把 RAG 检索接进 `/api/tutor` 的 prompt**、用真正的 tool-calling 让 LLM 调 MCP、用 LangGraph/状态机编排（推荐，最能体现"多 Agent"），要么如实修改 README，避免夸大。

**近期做（P1）**
- 用真实评测信号更新掌握度：练习/诊断测试**答对**才上调，移除"提及即 0.60"；去掉静默 `except pass`。
- 修复 CORS（明确 origins），加简单鉴权（如 API Key / 会话令牌）与基础限流。
- 启动时校验 `DASHSCOPE_API_KEY`，缺失即告警/退出。
- 清理死代码与未用依赖，复用单例 `QwenLLM`/Embeddings 客户端。

**工程化（P2）**
- 补离线单元测试（`pytest`，mock LLM/Embeddings），把 `test_langchain/`、`packages/` 移出仓库或纳入 `.gitignore`。
- 用 `asyncio.get_running_loop()` 替代弃用 API；统一 subject 传递。
- 知识图谱边改为基于真实先修关系（如"变量→函数→类"），而非顺序链。

---

## 六、总结

这是一个**文档与前端完成度很高、但核心 Agent/RAG/MCP 编排未真正落地**的演示型项目：结构分层合理、降级与提示词设计用心，但主链路只是"一次路由 LLM + 一次教学 LLM + 关键词意图"，并未发挥多 Agent、RAG 检索增强与工具调用的价值；同时存在代码沙箱任意执行、事件循环阻塞两项实质性风险。作为学习/原型值得肯定，若要作为简历亮点，建议优先补齐 **RAG 真接入 + 真工具调用（或 LangGraph 编排）+ 沙箱加固** 三件事，并使文档与代码一致。
