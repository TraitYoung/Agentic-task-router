# Axiodrasil 数字助理团 — 项目结构与技术说明

本文档描述 **Axiodrasil（数字助理团）** 仓库的目录结构、技术要点与核心数据定义，便于 onboarding、面试陈述与二次开发。

---

## 1. 项目概述

- **定位**：面向高压学习 / 项目场景的多 Agent 路由系统，基于 **LangGraph** 编排、**千问（Qwen）** 对话与 Embedding，配套 **L3 记忆矩阵** 与 **Hybrid RAG**。
- **核心能力**：
  - **路由层**：将用户输入解析为结构化 `TaskIntent`，分发至情绪（Bina）、文档（Jean）、技术（Bit）、战略（Juzheng）等节点；`pain_level > 6` 时优先走情绪节点（安全熔断）。
  - **记忆层**：Q1/Q2 写入 SQLite；会话最近 N 轮由 Redis 热缓存；Q2 支持 FTS5 + 向量 + RRF 混合检索。
  - **服务层**：FastAPI 提供同步聊天、SSE 流式、会话历史与导出等接口；Next.js 前端演示路由与对话。

---

## 2. 目录结构

```text
aixodrasil_core/
├── agents/
│   └── router.py                 # LangGraph StateGraph：parser + 四节点 + 条件边
├── memory/
│   ├── database.py               # PersonaMemory：SQLite 表、FTS5、向量表、触发器
│   └── session_cache.py         # SessionCache：Redis 会话滑窗
├── prompts/
│   ├── system_prompts.py         # 各 Agent 的 System Prompt 模板
│   └── bit_sft_system.txt        # 日志清洗等场景的 system instruction 示例
├── schemas/
│   └── protocols.py              # TaskIntent 等 Pydantic 协议
├── tools/
│   ├── agent_tools.py            # web_search / execute_python / write_local_file
│   ├── ai_client.py              # DashScope Embedding 客户端
│   ├── logs_to_sft.py            # 日志 → SFT JSONL 流水线
│   └── rerank_client.py          # 可选外部 Rerank（Jina / SiliconFlow）
├── test_suite/
│   ├── test.py                   # 路由整体流转
│   ├── test_memory.py            # 记忆矩阵
│   ├── test_rag.py               # Hybrid RAG
│   └── test_system_prompts.py    # Prompt 回归
├── scripts/
│   ├── migration.py              # Q2 冷启动 / 增量向量化
│   ├── inspect_q2.py             # 调试：查看 Q2
│   ├── clear_Q1.py               # 清理指定线程 Q1（若存在）
│   ├── locustfile.py             # 压测
│   └── …                         # 其他运维/转换脚本
├── frontend/                     # Next.js：SSE、会话、清洗模式等
├── docs/                         # 设计文档、ADR、PDF 等
├── data/                         # axiodrasil_core.db（默认不提交，见 .gitignore）
├── input/、output/、logs/        # 输入样本、产物、本地日志（按需）
├── hybrid_engine.py              # HybridRetriever：FTS5 + 向量 + RRF + 可选 rerank
├── main.py                       # FastAPI 应用入口
├── requirements.txt
├── README.md
└── .env                          # 本地密钥（不提交）
```

---

## 3. 技术要点

### 3.1 编排与模型

| 项 | 说明 |
|----|------|
| 编排 | **LangGraph** `StateGraph`：入口 `parser`，条件边 `route_by_intent`，出口为各 Agent 节点后 `END`。 |
| 对话模型 | `langchain_openai.ChatOpenAI`，兼容 OpenAI 协议；默认 `qwen-plus`，`base_url` 指向 DashScope 兼容模式。 |
| 结构化意图 | `llm.with_structured_output(TaskIntent)`，输出必须符合 Pydantic `TaskIntent`。 |
| 技术节点工具 | `langgraph.prebuilt.create_react_agent`，工具列表为 `BIT_TOOLS`（供 Bit 节点使用）。 |

### 3.2 路由与安全

- **Parser**：系统提示 + 最近会话文本，调用 `parser_llm` 得到 `TaskIntent`；若 `quadrant ∈ {Q1, Q2}` 则 `PersonaMemory.save_memory` 写入 L3。
- **条件路由** `route_by_intent`：
  - `pain_level > 6` → 强制 `emotion_route`（医疗红线逻辑下沉 Bina）。
  - 用户输入命中清洗 / `jsonl` / `sft` / `logs` 等关键词 → `bit_route`。
  - 否则按 `task_type` 分发；`unknown` 走 `juzheng_route`（当前产品默认）。

### 3.3 记忆与检索

- **Redis（L1 热缓存）**：键 `session:{session_id}:chat_turns`，`LPUSH + LTRIM` 固定窗口；默认 **5 轮**、**TTL 3600s**；供 parser 拼接 `recent_history`。
- **SQLite（L3）**：`memory_matrix` + `memory_fts`（FTS5 external content）+ `memory_embeddings`（1536 维 float32 BLOB）；触发器同步主表与 FTS。
- **Hybrid RAG**：`HybridRetriever.search_hybrid` — FTS5（BM25）与余弦向量两路召回 → **RRF** 融合 → 可选 `maybe_rerank` 截断为 `top_k`。Embedding 失败时 Jean 可退化为仅关键词路。

### 3.4 API 与前端

- **FastAPI**（`main.py`）：
  - `GET /api/v1/health`：探活；探测 Redis 是否可用。
  - `POST /api/v1/chat`：同步完整回复 + `TaskIntent`。
  - `POST /api/v1/chat/stream`：**SSE**；先 `invoke` 完整生成再按块推送（伪流式）。
  - `GET /api/v1/chat/history`、`POST /api/v1/chat/export`：基于 Redis 会话列表。
- **会话标识**：请求头 `x-session-id`；缺省时服务端生成 UUID。
- **前端**：`frontend/` Next.js，经 API Routes 代理后端；展示路由前缀 `bina` / `jean` / `bit` / `juzheng` 等。

### 3.5 依赖摘要（`requirements.txt`）

`fastapi`、`uvicorn`、`redis`、`pydantic`、`langgraph`、`langchain-openai`、`langchain-core`、`langchain-community`、`langchain-experimental`、`dashscope`、`numpy` 等。

---

## 4. 数据定义

### 4.1 图状态 `GraphState`（`agents/router.py`）

| 字段 | 类型 | 说明 |
|------|------|------|
| `current_input` | `str` | 当前用户输入 |
| `thread_id` | `str` | 线程/会话标识（API 层与 `x-session-id` 对齐） |
| `recent_history` | `List[str]` | 最近若干轮格式化文本，供 parser 语境 |
| `intent` | `TaskIntent` | 解析后的结构化意图 |
| `final_response` | `str` | 当前轮最终回复 |
| `active_task_type` | `str`（可选） | 实际执行节点类型，用于 API 前缀映射 |

### 4.2 意图协议 `TaskIntent`（`schemas/protocols.py`）

| 字段 | 类型 / 约束 | 说明 |
|------|-------------|------|
| `task_type` | `Literal["emotion","jean","bit","juzheng","unknown"]` | 路由目标类型 |
| `urgency_level` | `int`，默认 1，范围 1–5 | 紧急程度 |
| `pain_level` | `int`，默认 1，范围 1–10 | 身心痛感；>6 触发医疗红线路由；校验器内可打日志 |
| `raw_input` | `str` | 用户原文，要求保留 |
| `quadrant` | `Literal["Q1","Q2","Q3","Q4"]`，默认 `Q4` | 艾森豪威尔象限；Q1/Q2 会写入 L3 |

### 4.3 SQLite：`memory_matrix`

| 列 | 类型 | 说明 |
|----|------|------|
| `id` | INTEGER PK AUTOINCREMENT | 记忆主键 |
| `thread_id` | TEXT | 会话/线程 |
| `quadrant` | TEXT | 如 Q1、Q2 |
| `content` | TEXT | 记忆正文 |
| `status` | TEXT，默认 `active` | `active` / `archived` 等 |
| `created_at` | TIMESTAMP | 创建时间 |

索引：`idx_memory_thread_quadrant_status (thread_id, quadrant, status)`。

**业务约定**：parser 在 `quadrant in ("Q1","Q2")` 时插入一行；Bit 侧通过 `get_active_q1(thread_id)` 拉取未完成 Q1 注入上下文。

### 4.4 SQLite：`memory_embeddings`

| 列 | 类型 | 说明 |
|----|------|------|
| `memory_id` | INTEGER PK，FK → `memory_matrix.id` | 与主表一行对应 |
| `embedding` | BLOB NOT NULL | 1536 维 float32 向量（与 DashScope embedding 维度一致） |

向量化由 `scripts/migration.py` 等上层逻辑批量或增量写入。

### 4.5 SQLite：`memory_fts`（FTS5）

- **模式**：external content，`content='memory_matrix'`，`content_rowid='id'`。
- **索引列**：`content`, `quadrant`, `thread_id`。
- **同步**：`memory_matrix` 上 `INSERT/UPDATE/DELETE` 触发器维护 `memory_fts` 与主表一致。

### 4.6 Redis：会话轮次 JSON

每条 list 元素为 JSON 对象：

| 键 | 说明 |
|----|------|
| `user` | 用户该轮输入 |
| `assistant` | 助手该轮回复（含 API 层添加的前缀） |
| `ts` | ISO8601 时间戳（UTC） |

### 4.7 FastAPI 请求/响应模型（`main.py`）

| 模型 | 用途 |
|------|------|
| `ChatRequest` | `text: str`（1–12000 字符） |
| `ChatResponse` | `session_id`, `reply`, `intent: TaskIntent` |
| `ChatExportItem` / `ChatHistoryResponse` | `user`, `assistant`, `ts` |
| `ChatExportResponse` | 含导出文件相对路径 `file_path` |

---

## 5. 环境变量（常见）

| 变量 | 用途 |
|------|------|
| `QWEN_API_KEY` | 千问 API Key（必填，router 启动校验） |
| `QWEN_BASE_URL` | 可选；代码中 router 可写死兼容模式 URL，以实际 `.env` / 代码为准 |
| `REDIS_URL` | Redis 连接串，默认 `redis://localhost:6379/0` |
| Rerank 相关 | 见 `README.md`：`RERANK_PROVIDER`、`RERANK_API_KEY` 等（可选） |

---

## 6. 相关文档

- 根目录 **`README.md`**：启动步骤、模块说明、自测流程。
- **`docs/adr/`**：如痛感标尺等架构决策记录。
- **`docs/Axiodrasil_BIOS_*.md`**：系统设定与认知法案（版本迭代）。

---

## 7. 修订说明

- 本文档随仓库结构演进维护；表结构以 `memory/database.py` 为准，API 以 `main.py` 为准，路由以 `agents/router.py` 为准。
- `data/*.db`、`logs/`、`.env` 等通常被 `.gitignore` 忽略，克隆后需本地初始化。
