# 📁 项目结构详解

> 本文件是 `README.md` 中「项目结构」一节的细化版，逐目录、逐文件说明整个 RAG 系统的职责。
> 技术栈：LangGraph + LangChain + FastAPI + Milvus + PostgreSQL + Vue 3。

---

## 项目全貌

```
Rag_System/
├── docker-compose.yml / .env.example / README.md
├── docs/                        # 截图与文档
├── backend/                     # FastAPI + LangGraph RAG 后端（核心）
│   ├── main.py                  # 后端入口
│   ├── agents/                  # LangGraph Agent 层（RAG 流水线 / Supervisor / 子 Agent）
│   ├── app/                     # FastAPI 三层结构（api / core / db / models / services）
│   └── langgraph.json / requirements.txt / .env.example
├── frontend/                    # Vue 3 + Vite + Element Plus 前端
├── knowledge-table/             # WhyHow 开源子项目（结构化提取 + 知识图谱）
└── .kiro/ .idea/ .vs/ .vscode/  # 设计文档 + IDE 配置
```

---

## 1. 根目录

| 文件 / 目录 | 作用 |
|---|---|
| `README.md` | 项目文档：功能亮点、启动步骤、RAG 流水线 Mermaid 图、技术栈、端口表、FAQ |
| `docker-compose.yml` | 一键启动基础设施：`milvus-etcd`（元数据）、`milvus-minio`（Milvus 存储，Console 19001）、`milvus-standalone`（向量库，19530）、`postgres`（业务库 5432）、`attu`（Milvus GUI，18080），全部挂在 `kb-net` 网络 |
| `.env.example` | 根级环境变量样例（被 docker-compose 引用：MinIO/PG 的 docker 口令） |
| `docs/` | 界面截图（首页、对话检索效果、图文对话、多模态效果等）与文档 |
| `.kiro/` | 设计文档：`doc-upload-slice/`（上传切分模块的 requirements/design/tasks）、`knowledge-agent-system/`（知识库 Agent 系统设计） |
| `.idea/` `.vs/` `.vscode/` | 各 IDE 的本地配置（MarsCode、VS、VSCode），无业务代码 |

---

## 2. backend/ — 后端核心

### 2.1 顶层文件

| 文件 | 作用 |
|---|---|
| `main.py` | **后端入口**。`create_app()` 工厂：注册 CORS、全局异常处理器（`AppError` → HTTP 状态码）、挂载 `/api/v1` 路由；`lifespan` 启动时 `init_db()` 建表 + `init_checkpointer()` 建 LangGraph 对话记忆连接池；全局禁用 SSL 校验 |
| `langgraph.json` | LangGraph CLI/平台配置文件（注册 graph、env）。项目实际用 `get_knowledge_agent()` 在代码里手动编译，此文件偏模板/占位 |
| `requirements.txt` | 依赖清单：LangGraph/LangChain、FastAPI、psycopg2 + psycopg3（checkpoint 专用）、pymilvus、dashscope、oss2、pymupdf、python-docx、pandas/openpyxl 等 |
| `.env.example` | 环境变量样例：阿里云凭据、LLM 模型、Milvus/PG 连接、Embedding（模型/维度/批大小）、切分参数、OSS 等 |
| `.langgraph_api/*.pckl` | LangGraph API server 运行时产生的本地 checkpoint 缓存文件，可忽略 |

### 2.2 agents/ — LangGraph Agent 层

#### agents/knowledge/ — RAG 核心流水线

图拓扑（StateGraph）：

```
START → query_rewrite → query_classify → determine_retrieval_strategy → kg_query_route → graph_retrieve
  → route_by_query_type（条件分支）
     ├─ single_doc_retrieve ──────→ select_top_k_chunks (rerank)
     └─ multi_doc_retrieve → filter_chunks → select_top_k_chunks (rerank)
  → generate_answer →（should_check_quality 条件分支）→ check_quality → finalize_metrics → END
```

| 文件 | 作用 |
|---|---|
| `graph.py` | 定义 StateGraph 拓扑：注册 12 个节点、2 条条件边（single/multi 分流、质量检查跳过），`create_knowledge_agent(checkpointer, interrupt_before)` 编译图 |
| `state.py` | `KnowledgeAgentState` TypedDict，约 50+ 共享字段（对话记忆、改写/分类/检索/重排/图谱/生成/质量/指标），外加 `RetrievedChunk`、`RAGConfig`、`PerformanceMetrics` 等数据类和 `create_initial_state()` |
| `openai_stream.py` | 把 DashScope 多模态 messages 转成 OpenAI 格式，用 `AsyncOpenAI` 流式调用千问兼容 API，逐 token 产出文本增量，供 SSE 接口使用 |
| `HOW_TO_ADD_NEW_NODE.md` | 开发者手册：如何往图中加节点（新建文件 → 导出 → graph.py 连边 → 扩展 state），含完整示例 |

**nodes/ 目录（每个节点一个文件）：**

| 节点文件 | 作用 |
|---|---|
| `query_rewrite.py` | 用轻量模型改写用户问题，截取最近 N 轮历史做**多轮指代消解**；失败回退原问题 |
| `query_classify.py` | LLM 判断 `single_doc` / `multi_doc`；`force_multi_doc` 可强制跳过 LLM |
| `retrieval_strategy.py` | 规则引擎（正则匹配错误码/代码片段）决定 `KEYWORD_ONLY` / `HYBRID` 检索策略 |
| `single_doc_retrieve.py` | 单文档路径：调 `RetrievalService` 做 Milvus RRF 混合检索 |
| `multi_doc_retrieve.py` | 多文档路径：按 `file_name` 分组搜索，保证跨文档多样性 |
| `multimodal_retrieve.py` | 三路检索（文本 dense + BM25 + 图片 dense），支持用户传图查询；被 single/multi 节点内部调用 |
| `kg_query_route.py` | LLM 判断是否需要**知识图谱深度遍历**（更多跳） |
| `graph_retrieve.py` | 通过 WhyHow/Knowledge-Table API 查知识图谱，返回关联 chunk |
| `filter.py` | 按 `vector_score_threshold` 过滤低分 chunk（仅 multi_doc 路径） |
| `relevance_filter.py` | LLM 批量判断 query 与 chunk 相关性并过滤（图中已注释，代码保留） |
| `rerank.py`（= select_top_k_chunks） | 汇合节点：`rerank_enabled` 时调 qwen3-rerank 精排；否则按 RRF 分数排序截断 top_k |
| `generate.py` | **生成节点**：组装「向量切片 + 图谱切片」两节上下文，按图文/图谱组合选 8 种 prompt 模板之一，调 DashScope 生成答案，支持 `precomputed_answer` 短路 |
| `quality_check.py` | 检查答案长度 + 置信度阈值，不合格且 `enable_fallback` 时替换为 fallback 文案 |
| `metrics.py` | 计算总耗时、按模型成本估算美元费用（图末节点） |

**services / tools：**

| 文件 | 作用 |
|---|---|
| `services/retrieval.py` | `RetrievalService` 单例，封装 vector / keyword / hybrid 三种检索，底层委托 `MilvusService.hybrid_search()` |
| `tools/__init__.py` | 空包，预留未来 tool 扩展 |

#### agents/supervisor/ — 总调度 Agent

| 文件 | 作用 |
|---|---|
| `graph.py` | Supervisor 协调图：LLM 绑定子 Agent 工具 → 有 tool_call 走 tools → 循环直到直接回复；用 `MemorySaver()` |
| `state.py` | 仅 `messages` 字段（`add_messages` reducer） |
| `nodes/router.py` | `should_continue()`：最后一条消息含 tool_calls 则去 tools，否则结束 |
| `services/coordinator.py` | 把 Email / Search 两个子 Agent 包装成 `@tool`（`call_email_agent` / `call_search_agent`），维护注册表和子 Agent 能力描述（拼进 system prompt） |

#### agents/specialized/ — 专用子 Agent（均为标准 ReAct 循环）

| 文件 | 作用 |
|---|---|
| `email/graph.py` + `state.py` + `nodes/email_processor.py` + `services/email_service.py` | 邮件 Agent：agent ↔ tools 循环；`email_service.py` 定义 send_email / check_inbox / search_emails 三个工具（当前为 **stub 模拟实现**），导出 `EMAIL_AGENT_INFO` |
| `search/graph.py` + `state.py` + `services/search_service.py` | 搜索 Agent：同样的 ReAct 循环；定义 search_web / get_weather / get_news 三个工具（也是 **stub**），导出 `SEARCH_AGENT_INFO` |

### 2.3 app/ — FastAPI 应用层（三层：路由 → 服务 → 仓储）

#### app/api/v1/ — REST 路由（最终前缀 `/api/v1/...`）

| 文件 | 端点 | 作用 |
|---|---|---|
| `__init__.py` | — | 聚合 11 个子路由到 `APIRouter(prefix="/v1")` |
| `chat.py` | `/chat` | 与 Supervisor Agent 的**普通多 Agent 对话** |
| `knowledge.py` | `/knowledge`、`/knowledge/stream` | **RAG 问答**：非流式 + SSE 流式；流式前把用户图片传 OSS 换预签名 URL |
| `documents.py` | `/documents/*` | 上传（单文件直传 / 传类目 / 批量）、Excel 列获取与切分、批量提交切分、`/search` 检索命中测试、`/image-proxy` OSS 私有图代理 |
| `files.py` | `/files` | 知识库文件列表 / 单个删除 / 批量删除 |
| `jobs.py` | `/jobs` | 处理任务列表 / 详情 / 手动触发向量化（upsert） |
| `categories.py` | `/categories` | 类目 CRUD、类目下文件列表与删除 |
| `chunks.py` | `/chunks/*` | 切片 CRUD、编辑 / 清洗 / 还原（单条 / 批量 / 全局）、上传向量库、切片图片管理、图片占位符解析 |
| `conversations.py` | `/conversations` | 对话会话列表 / 新建 / 历史消息 / 删除 |
| `knowledge_graph.py` | `/knowledge-graph/kb/{kb_name}` | 查询知识库下已同步图谱文件的三元组 |
| `system.py` | `/`、`/models`、`/health` | 系统根信息、模型列表、健康检查 |
| `admin/__init__.py` | — | Admin 路由聚合 |
| `admin/collection.py` | `/admin/collections` | **知识库 CRUD**（"collection" = 知识库）：创建时同步在 Milvus 建 collection + PG 写记录，删除时联动清理；内含 `RetrievalConfig` 默认检索参数 |
| `admin/config.py` | `/admin/config` | 系统配置摘要（Milvus / PG / Embedding 信息） |
| `admin/_deps.py` | — | Admin 公共依赖占位 |

#### app/core/ — 配置、日志、异常、Prompt、持久化

| 文件 | 作用 |
|---|---|
| `config.py` | `Settings` 单例：从 `.env` 读全部运行参数（LLM / Milvus / PG / Embedding / 切片 / OSS / API），启动时校验必填变量；`SUPPORTED_MODELS` 记录 5 个 qwen 模型能力与成本 |
| `logging.py` | JSON 结构化日志（JsonFormatter），静默第三方库噪音 |
| `exceptions.py` | `AppError` 基类派生 404 / 400 / 403 / 409 / 502，由全局 handler 映射状态码 |
| `prompts.py` | **所有 LLM prompt 模板集中地**：切片清洗、8 种 RAG 生成模板（按图文 / 图谱 / 用户图片组合）、图谱深度路由、单多文档分类、查询改写（含指代消解示例）、相关性过滤、Supervisor 系统提示 |
| `checkpointer.py` | LangGraph 记忆持久化单例：生产用 psycopg3 `AsyncPostgresSaver`（独立连接池），失败降级 `MemorySaver` |

#### app/db/ — PostgreSQL 仓储层（psycopg2 连接池 + Repository 模式）

| 文件 | 作用 |
|---|---|
| `pg_client.py` | 连接池封装，提供 execute_sql / execute_returning / execute_select / execute_many 四个参数化查询，自动管理事务 |
| `base_repository.py` | `BaseRepository` 基类，把上面四个方法包装成实例方法 |
| `init_db.py` | 按外键依赖顺序幂等建 10 张表：knowledge_base → category → category_file → file → job → chunk → chunk_origin → chunk_image → conversation_session → conversation_message；插入默认类目；建 LangGraph checkpoint 表 |
| `kb_repository.py` | 知识库配置表（含 metadata_fields、retrieval_config JSON） |
| `category_repository.py` | 类目表 |
| `category_file_repository.py` | 类目文件表（仅 OSS 引用，不参与切分） |
| `file_repository.py` | 知识库文件表（含 sync_graph、状态） |
| `job_repository.py` | 处理任务表，维护 `pending → chunking → chunked → embedding → done/error` 状态机 |
| `chunk_repository.py` | 切片表 + 原始备份表（用于撤回 / 还原） |
| `chunk_image_repository.py` | 切片图片表（占位符 → OSS key 反查） |
| `conversation_repository.py` | 会话 + 消息表（含 sources JSON、图片占位符） |

#### app/models/ — Pydantic 模型

| 文件 | 作用 |
|---|---|
| `requests.py` | 请求体：`Message`、`ChatRequest`、`KnowledgeRequest`（query / session / collection / force_multi_doc / keyword_filter / query_image） |
| `responses.py` | 响应体：`ChatResponse`、`KnowledgeResponse`（answer / confidence / sources / image_map）、`ModelInfo`、`HealthResponse` |

#### app/services/ — 业务逻辑层（19 个服务）

**核心流程**：

```
document_service.upload_document()
  → oss_service 上传 + PG 建 file/job 记录（status=pending）
  → 后台 job_service.run_job_pipeline()
     → OSS 下载文件
     → [图文模式] doc_image_parser（提取文字+图片，嵌入 <<IMAGE:hex>> 占位符）
     → [标准模式] chunk_splitter.split_text_with_metadata() / split_excel()
     → 写 PG chunk → 状态停在 chunked（切分与向量化解耦）
  → [手动触发] job_service.upsert_job_to_milvus()
     → embedding_service / multimodal_embedding_service 向量化
     → milvus_service.upsert() 分批写入
     →（可选）kg_graph_sync_service 同步到知识图谱
```

| 文件 | 作用 |
|---|---|
| `document_service.py` | 上传 / 切分触发入口：格式校验（8 种格式，200MB）、OSS 上传、建文件 + job 记录、BackgroundTasks 触发流水线；`search_documents()` 检索封装（hybrid + rerank + 图片 URL 回填） |
| `job_service.py` | 流水线执行器：OSS 下载 → 按 image_mode 分发解析 → 写 chunk → 状态 `chunked`；`upsert_job_to_milvus()` 手动向量化（标准每批 100 重试 5 次 / 多模态每批 50），完成后图谱同步 |
| `file_service.py` | 文件列表 + 联动删除（Milvus 向量 + 图谱数据 + OSS 图片 + PG 级联） |
| `chunk_service.py` | 切片 CRUD、LLM 清洗、手动向量化、切片内图片增删、占位符 → 预签名 URL 解析；已向量化文件禁止再改切片 |
| `chunk_splitter.py` | **纯文本 / Excel 切分器**：递归分隔符切分（`\n\n` → `，`）、短片段合并（语义断裂检测）、句子边界 overlap；Excel 按 sheet + 列配置输出 `key=value` 格式 |
| `chunk_cleaner.py` | 正则去页码 / 页眉 / 水印 + LLM 批量清洗（每批 5 条） |
| `doc_image_parser.py` | **图文解析**：PyMuPDF / python-docx 提取文字 + 图片交织切分，图片上传 OSS 并嵌入 `<<IMAGE:hex>>` 占位符 |
| `embedding_service.py` | 文本向量化（DashScope TextEmbedding，按 batch 分批、重试 5 次、指数退避） |
| `multimodal_embedding_service.py` | 多模态向量化（qwen3-vl-embedding，文本 / 图片独立向量共享语义空间，逐条调用） |
| `milvus_service.py` | Milvus 管理：每知识库一 collection（chunk_id / job_id / file_name / content + dense + sparse_bm25，多模态加 image_dense），HNSW + BM25 双索引；`hybrid_search()` Dense + BM25 双路 RRF / Weighted 融合；检索后回填 PG 原文 |
| `rerank_service.py` | qwen3-rerank 精排（单次最多 500 文档，失败降级按原分数排序） |
| `oss_service.py` | 阿里云 OSS 封装：上传 / 下载 / 批量删除 / 预签名 URL |
| `category_service.py` | 类目管理（含 `__default__` 系统类目，删除联动清理 OSS） |
| `chat_service.py` | 普通对话入口：调 Supervisor Agent，session_id 隔离记忆（thread_id），返回回复 + 使用的工具 |
| `knowledge_service.py` | **RAG 问答入口**：非流式 `invoke_knowledge_qa` + SSE `stream_knowledge_qa_sse`（interrupt 模式：检索走 agent，生成走流式，再恢复 agent 完成质量检查 / 指标）；从知识库 retrieval_config 注入检索参数；持久化对话 |
| `conversation_service.py` | 会话管理（删除时联动清理用户查询图片） |
| `kg_graph_sync_service.py` | 调 Knowledge-Table REST API 把切片同步成三元组（sync_chunks_to_graph / delete_graph_by_job / query_graph） |
| `kg_whyhow_service.py` | 图谱检索服务：KG 自然语言查询 → 提取 chunk_id → 并发拉取正文 → 回填 PG → 统一打分排序，供图谱检索节点调用 |

---

## 3. frontend/ — Vue 3 前端

### 工程配置

| 文件 | 作用 |
|---|---|
| `package.json` | Vue 3.4 + Vite 5 + Element Plus + axios + markdown-it；无 Vue Router（视图用 `v-show` 切换） |
| `vite.config.js` | 开发端口 5173；`/api` 代理到 8000；对 `/knowledge/stream` 注入 SSE 请求头 |
| `index.html` | HTML 入口 |

### src/ 源码

| 文件 | 作用 |
|---|---|
| `main.js` | 创建 Vue 应用，全局注册 Element Plus + 图标 + 暗色主题 |
| `App.vue` | 根组件：左侧图标导航（Dashboard / 对话 / 类目 / 知识库 / 开发工具），顶部模型选择 + 后端连通状态，`v-show` 切视图 |
| `styles/dark-theme.css` | 全局暗色主题（覆盖 Element Plus 全部组件，CSS 变量颜色体系） |
| `views/DashboardView.vue` | 首页：Hero 搜索框（直达 RAG 问答）、统计卡片、知识库列表、系统状态面板 |
| `components/SimpleChat.vue` | **核心对话组件**：普通对话（Multi-Agent）/ 知识库（RAG + rerank）双模式；会话侧边栏、知识库选择器、多文档开关、关键词过滤、多模态传图；SSE 流式、Markdown、来源折叠、置信度弧形、图片 Lightbox |
| `components/AdminPanel.vue` | 知识库管理面板：列表（含检索配置弹窗）、创建（标准 / 多模态）、系统配置；内嵌 DocUpload / DocList / DocSearch |
| `components/DevTools.vue` | 开发工具页：健康检查 + 接口说明文档 |
| `components/doc/CategoryManager.vue` | 类目管理：两级视图（类目列表 / 类目详情 + 文件上传与批量删除） |
| `components/doc/ChunkEditorPanel.vue` | **切片编辑器**：分页浏览，标准模式 textarea / 图文模式 contenteditable（占位符 Token 化可 hover），支持清洗 / 还原 / 保存 / 上传向量库 |
| `components/doc/DocJobList.vue` | 任务列表弹窗（状态、进度、触发向量化，5 秒轮询） |
| `components/doc/DocList.vue` | 文件列表：待向量化 / 已向量化两个 Tab，批量上传向量库、批量删除 |
| `components/doc/DocSearch.vue` | **检索命中测试**：完整参数面板（TopK、RRF / Weight 混合、Rerank、关键词过滤），结果表格展示来源与分数 |
| `components/doc/DocUpload.vue` | 文档上传：单文件（图文 / 普通）、类目批量、Excel（委托 ExcelCategoryUpload） |
| `components/doc/ExcelCategoryUpload.vue` | Excel 上传：弹窗配置每列是否导入 + 别名，提交批量切分 |
| `components/doc/KnowledgeGraphPanel.vue` | 知识图谱面板：已同步文件数、三元组总数、单文件 RDF 三元组详情 |
| `services/api.js` | 核心 API 封装：healthCheck / getModels / chat / knowledgeQuery / knowledgeQueryStream（原生 fetch 手写 SSE，onMeta / onDelta / onDone 回调） |
| `services/docApi.js` | 文档业务 API：6 大模块约 40 个方法（文档、Job、切片 CRUD、切片图片、文件、类目、Admin、占位符解析、会话） |

---

## 4. knowledge-table/ — 独立子项目（结构化提取 + 知识图谱）

WhyHow.AI 开源的 Knowledge Table 项目（MIT 协议 vendored 进来），**与主 RAG 系统互补**：主系统在向量化完成后把切片同步到它生成三元组（文档里「同步到知识图谱」开关），问答时经 `kg_graph_sync_service` / `kg_whyhow_service` 融合图谱结果。

- `backend/`（Python / FastAPI）：document / query / graph / graph_sync 四个端点；services 用工厂模式支持 Milvus / Qdrant 双向量库、多种 LLM / loader；带完整 pytest 测试套件
- `frontend/`（React 18 + TS + Vite + Mantine）：Zustand + TanStack Query + @silevis/reactgrid 电子表格 + react-mentions
- `docker-compose.yml` / `README.md` / `.github/` 等：子项目自带
- 部署在 `http://localhost:8000`（检索）/ `8001`（同步），主系统通过 HTTP 调用它

---

## 5. 关键架构速览

- **三层分离**：API 路由层（FastAPI）只做参数校验 → service 层执行业务逻辑 → db 层（Repository 模式）只做参数化 SQL
- **双存储**：业务元数据（知识库 / 文件 / 类目 / 任务 / 切片 / 对话）在 PostgreSQL；向量数据在 Milvus；LangGraph 对话记忆走独立的 psycopg3 连接池写 PG checkpoint 表
- **切分与向量化解耦**：切分后停在 `chunked`，人工审查后手动触发向量化，失败可重试（upsert 幂等）
- **每库独立检索配置**：ranker / top_k / group_size / memory_turns / rerank 按知识库隔离，存在 `knowledge_base.retrieval_config` JSON
- **RAG 流水线**：改写 → 分类（单 / 多文档）→ 混合检索（Dense + BM25 + RRF）→ 可选 Rerank → 生成 → 质量检查 → 指标
