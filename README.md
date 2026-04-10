## Axiodrasil: AI 软件工程开发优化系统（可插拔多 Agent 内核）

[![Python 3.13](https://img.shields.io/badge/Python-3.13-blue.svg)](https://www.python.org/)
[![LangGraph](https://img.shields.io/badge/Orchestration-LangGraph-orange.svg)](https://github.com/langchain-ai/langgraph)
[![Pydantic](https://img.shields.io/badge/Protocol-Pydantic_V2-red.svg)](https://docs.pydantic.dev/)

Axiodrasil 目前主打 **AI 赋能软件工程开发优化**：

- **A 方向（主能力）— AI 软件工程流水线**：`workflow_mode=dev_pipeline`，将需求发现、Sprint 设计、实现草案、测试/DoD/交付闭环做成结构化多步编排。
- **Token 优化**：每步只传上一步 JSON 摘要，统一上下文预算（history / RAG / step JSON）控制成本与时延。
- **全链路追踪**：每轮返回 `trace_id + trace[]`，支持步骤级复盘。
- **默认路由系统（次能力）**：保留为可热插拔模块（优先 `AX_DEFAULT_ROUTER_BACKEND`，兼容 `AX_CABINET_BACKEND`），用于软件工程任务的正反手教学、路由策略测试与历史能力兼容。

本项目适合作为「AI + 软件工程流程化 + 成本意识 + 可观测性」的工程化示例，而非单次聊天 Demo。

## 目录导航

- [快速开始（先看这个）](#快速开始先看这个)
- [第一章：项目定位（软件工程开发优化优先）](#第一章项目定位软件工程开发优化优先)
- [第二章：系统宏观结构（A 方向主链路）](#第二章系统宏观结构a-方向主链路)
- [第三章：项目结构与角色分工](#第三章项目结构与角色分工)
- [第四章：AI 软件工程流水线（主能力）](#第四章ai-软件工程流水线主能力)
- [第五章：记忆矩阵与 Hybrid RAG（基础能力）](#第五章记忆矩阵与-hybrid-rag基础能力)
- [第六章：部署与运行说明](#第六章部署与运行说明)
- [第七章：MVP 指标与工程亮点](#第七章mvp-指标与工程亮点)
- [第八章：参考文档与设计记录](#第八章参考文档与设计记录)

**开发者向（比本章 README 更细的目录与模块说明）**：[docs/项目结构与技术要点.md](docs/项目结构与技术要点.md)

## 快速开始（先看这个）

### 手动启动（推荐：三个终端，可见报错、端口清晰）

在项目根目录（本仓库根，含 `main.py` 的那一层）与 `frontend/` 分别操作。

**终端 1 — Redis（会话热缓存，可选）**

未启动 Redis 时，接口仍可工作，但最近 5 轮热上下文可能为空。

```powershell
cd G:\1groupOfReporAndHomework\aixodrasil_core
redis-server --port 6379
```

若提示 6379 已被占用，请先结束占用进程，或改用其他端口并在 `.env` 中设置 `REDIS_URL=redis://127.0.0.1:<端口>/0`。

**终端 2 — 后端 FastAPI**

```powershell
cd G:\1groupOfReporAndHomework\aixodrasil_core
pip install -r requirements.txt
python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

看到 `Uvicorn running on http://127.0.0.1:8000` 后再开前端。确认 `.env` 中已配置 `QWEN_API_KEY` 等。
可先复制 `.env.example` 为 `.env`，再按需修改。

**终端 3 — 前端 Next.js**

```powershell
cd G:\1groupOfReporAndHomework\aixodrasil_core\frontend
npm install
npm run dev
```

看到 `Ready` 与本地地址后，在浏览器打开 **`http://localhost:3000`**（或 `http://127.0.0.1:3000`）。不要用 `file:///` 打开本地文件。

若提示端口被占用或「已有另一个 next dev」，请先结束占用 3000 的进程后再启动，例如：

```powershell
Get-NetTCPConnection -LocalPort 3000 -State Listen -ErrorAction SilentlyContinue | Select-Object OwningProcess
taskkill /PID <上一步的PID> /F
```

### 手动关闭

在各运行服务的终端窗口按 **`Ctrl + C`** 即可结束该服务。Redis、后端、前端各关一次。

### 常用脚本（`scripts/` 目录，与启停无关）

- `scripts/migration.py`：Q2 冷启动向量化
- `scripts/inspect_q2.py`：查看 Q2 记忆
- `scripts/insert_career_nuke.py`：插入示例战略记忆
- `scripts/clear_Q1.py`：清理指定线程记忆
- `scripts/md_to_pdf.py`：文档转 PDF
- `scripts/locustfile.py`：Locust 压测入口（若使用）

---

## 第一章：项目定位（软件工程开发优化优先）

- **主目标**：把软件工程课里常见的理想流程（需求、迭代、DoD、回顾）变成可执行的 AI 多步流水线产物。
- **主场景（A 方向）**：开发任务输入后，输出结构化交付：需求规格 → Sprint 待办与设计 → 代码草案 → 测试/DoD/CHANGELOG。
- **次能力**：保留默认多 Agent 路由、记忆和 RAG，作为教学/测试与兼容能力，而非首页主叙事。
- **工程原则**：
  - 用 **Pydantic 结构化协议** 保持每一步可验证；
  - 用 **上下文预算** 控制 Token 成本与延迟；
  - 用 **trace_id + trace[]** 支持步骤级复盘。

---

## 第二章：系统宏观结构（A 方向主链路）

从 10,000 米高度看 Axiodrasil，可分为两条主链路 + 一组基础能力：

1. **A 方向主链路（dev_pipeline）**
   - `main.py` 按 `workflow_mode=dev_pipeline` 进入 `agents/workflow_pipelines.py`；
   - 固定四步结构化编排：需求发现 → Sprint 设计 → 实现草案 → 测试/DoD/交付；
   - 步骤间仅传 JSON 摘要（见 `config/context_budget.py`）。
2. **可插拔内阁链路（default）**
   - `main.py` 通过 `agents/default_router/registry.py` 获取执行器（`AX_DEFAULT_ROUTER_BACKEND` 可切换，兼容 `AX_CABINET_BACKEND`）；
   - 默认实现当前复用 `agents/cabinet/graph.py`，对外主入口为 `agents/default_router/graph.py`。
3. **基础能力层（记忆/RAG/缓存）**
   - SQLite 主表 `memory_matrix` 存储 `thread_id / quadrant / content / status / created_at`；
   - 向量表 `memory_embeddings` 以 BLOB 形式存储 1536 维 float32 向量；
   - FTS5 虚拟表 `memory_fts` 作为 external-content 索引。
4. **热缓存层（memory/session_cache.py）**
   - Redis 会话热缓存（Session 缓存与滑动窗口），为本次路由意图解析提供最近 5 轮上下文；TTL 默认 1 小时。
5. **Hybrid RAG 层（hybrid_engine.py + tools/ai_client.py）**
   - 关键词召回：FTS5 + BM25；
   - 语义召回：向量余弦相似度；
   - 融合排序：RRF (Reciprocal Rank Fusion)。

系统总体结构（简化）：

```text
User Input
   ↓
workflow_mode = dev_pipeline
   ↓
[SE Pipeline: 4-step structured outputs]
   ↓
[Trace + Redis conversation append]

or

workflow_mode = default
   ↓
[Pluggable Cabinet Runner]
   ↓
[LangGraph Cabinet + Memory/RAG]
   ↓
[Trace + Redis conversation append]
```

---

## 第三章：项目结构与角色分工

```text
├─ agents/
│  ├─ default_router/
│  │  ├─ graph.py            # 默认路由图入口（当前复用 cabinet 内核）
│  │  ├─ runner.py           # 默认路由执行器
│  │  └─ registry.py         # AX_DEFAULT_ROUTER_BACKEND 热插拔入口（兼容 AX_CABINET_BACKEND）
│  ├─ cabinet/
│  │  ├─ graph.py            # 可插拔内阁图（LangGraph）
│  │  ├─ runner.py           # 默认内阁执行器
│  │  └─ registry.py         # 历史兼容层（保留）
│  ├─ workflow_pipelines.py  # AI 软件工程流水线（A 方向主能力）
│  └─ router.py              # 兼容层（re-export）
├─ config/
│  └─ context_budget.py      # 上下文预算（Token 控制）
├─ memory/
│  ├─ database.py           # L3 记忆矩阵 + FTS5 + 向量表
│  └─ session_cache.py     # Redis 会话热缓存（滑动窗口，TTL 1h）
├─ tools/
│  └─ ai_client.py           # 千问 DashScope embedding 客户端
├─ frontend/
│  └─ ...                    # Next.js 演示页（SSE 流式输出 + 路由分区展示）
├─ logs/
│  ├─ memory_system_evolution.log   # 记忆系统演化日志（本地调试）
│  └─ rag.log                       # RAG 架构演化日志
├─ data/
│  └─ axiodrasil_core.db     # SQLite 记忆库（由于隐私原因，默认不提交）
├─ hybrid_engine.py          # HybridRetriever：FTS5 + 向量召回 + RRF 融合
├─ scripts/
│  ├─ migration.py           # Q2 冷启动向量化脚本
│  ├─ inspect_q2.py          # Q2 内容查看（本地调试工具）
│  ├─ insert_career_nuke.py  # 插入 Career_Nuke 样本（demo 专用）
│  ├─ clear_Q1.py            # 清理指定线程记忆
│  ├─ md_to_pdf.py           # 文档转 PDF
│  └─ locustfile.py          # Locust 压测入口
├─ test_suite/
│  ├─ test.py                # 路由引擎总体流转测试
│  ├─ test_memory.py         # 记忆矩阵回归测试
│  ├─ test_rag.py            # RAG 压测脚本（主命中+候选）
│  └─ test_system_prompts.py # Prompt 节点回归测试
├─ output/
│  ├─ even_sum.py            # 工具链生成示例脚本（归档）
│  └─ primes_upto_100.py     # 工具链生成示例脚本（归档）
├─ .gitignore
└─ README.md
```

### 未提交 / 本地专用文件说明

出于安全与隐私考虑，仓库中有部分文件不会随 Git 提交（在 `.gitignore` 中忽略），包括：

- **环境配置**
  - `.env`：包含千问 `QWEN_API_KEY` 等真实密钥，仅在本地创建，仓库中不提供。
- **本地数据**
  - `data/axiodrasil_core.db`：真实对话记忆与个人笔记的 SQLite 数据库，避免将私人内容上传。
- **日志文件**
  - `logs/*.log`：包含调试轨迹与可能的敏感上下文，仅用于本地观测与问题排查。
- **本地调试脚本（可选）**
  - 如 `scripts/inspect_q2.py`、`scripts/insert_career_nuke.py`、`scripts/clear_Q1.py` 等，用于本地注入样本、查看记忆矩阵、清理测试数据。
    如果你克隆仓库后发现它们不存在，可以按 README 中的说明自行创建。

这些忽略规则与 `.gitignore` 中的配置一一对应，保证系统结构完整，同时不泄露任何个人敏感信息。

---

## 第四章：AI 软件工程流水线（主能力）

- **核心文件**：`agents/workflow_pipelines.py`、`schemas/workflows.py`、`config/context_budget.py`
- **入口方式**：`POST /api/v1/chat` 或 `/api/v1/chat/stream` 传 `workflow_mode=dev_pipeline`
- **核心目标**：把「需求 -> 设计 -> 实现 -> 交付」压成可追踪、可复盘的结构化四步输出。

### 阶段 1 + 阶段 2 编排

1. **需求发现（Discovery）**
   - 产出 `DevTaskSpec`：`goal`、`acceptance_criteria`、`user_stories`、`mvp_sprint_goal`、`measurable_outcomes`。
2. **Sprint 设计（Sprint Design）**
   - 产出 `DevOutline`：模块拆分、数据流、`backlog_mvp_ordered`、`technical_spikes`、`parking_lot`。
3. **并行分支（Phase-2）**
   - **实现草案 Agent**：产出 `DevCodeSketch`（MVP 核心路径代码草稿）。
   - **测试交付 Agent**：产出 `DevTestsChangelog`（DoD / CI / CHANGELOG）。
4. **汇总（Merge）**
   - 将并行分支结果整合为统一发布说明与下迭代建议。

### Token 与可观测性策略

- 步骤间只传 JSON 摘要，避免重复喂长上下文；
- 长文本受 `config/context_budget.py` 限制（用户输入、步骤 JSON、历史截断）；
- 每步写入 `trace[]`，前端可展开查看节点、耗时、摘要（并行分支与 merge 可见）。

### 可插拔默认路由（次位能力）

- `workflow_mode=default` 仍可用；
- `main.py` 通过 `agents/default_router/registry.py` 加载默认路由执行器（优先 `AX_DEFAULT_ROUTER_BACKEND`，兼容 `AX_CABINET_BACKEND`）；
- 作为软件工程教学/测试与兼容能力保留，不作为当前主叙事。

---

## 第五章：记忆矩阵与 Hybrid RAG（基础能力）

### 5.1 L3 记忆矩阵（memory/database.py）

- 主表 `memory_matrix`：
  - 字段：`id, thread_id, quadrant, content, status, created_at`
  - 索引：`(thread_id, quadrant, status)` 联合索引，提升高频查询。
- 向量表 `memory_embeddings`：
  - `memory_id` 主键 + `embedding` BLOB（1536 维 float32 向量）。
- FTS5 表 `memory_fts`：
  - external-content 模式，索引 `content / quadrant / thread_id`。
- 触发器：
  - `INSERT / UPDATE / DELETE` 时自动同步 `memory_matrix` 与 `memory_fts`，避免双写不一致。

### 5.1.5 L1 热缓存（Redis 会话滑窗，memory/session_cache.py）

- 以 HTTP Header `x-session-id` 标识用户会话；
- 每次请求前读取最近 5 轮对话并注入到 `GraphState.recent_history`，用于意图解析语境；
- 每次回复后写回 Redis，并刷新 TTL（默认 1 小时）；SQLite 仍保留为冷数据持久化。

### 5.2 冷启动向量化（scripts/migration.py）

- 找到所有 `quadrant='Q2'` 且尚未写入 `memory_embeddings` 的记录；
- 调用 `tools.ai_client.get_embedding(content)` 得到 1536 维向量；
- 写入 `memory_embeddings(memory_id, embedding)`；
- 支持多次运行，天然幂等。

### 5.3 Hybrid 检索（hybrid_engine.py）

- 关键词通路 `_get_keyword_scores`：
  - 对 `memory_fts` 使用 `MATCH` + `bm25(memory_fts)` 排序；
  - 支持按 `thread_id / quadrant` 过滤。
- 向量通路 `_get_vector_scores`：
  - 读出 BLOB，反序列化为 `np.ndarray[float32]`；
  - 与查询向量做余弦相似度，取 top-N。
- RRF 融合 `rrf_fusion`：
  - 对每条候选文档 d：`score(d) = Σ 1/(k + rank_i(d))`；
  - 只依赖排名，不依赖原始分数尺度，适合跨模态/异构通路融合。
- 对外接口 `search_hybrid(query, query_embedding, top_k, thread_id, quadrant, rerank_pool_size=10)`：
  - RRF 融合后先取前 `rerank_pool_size` 条候选；若配置了外部 Rerank API（见下），再重排并返回 top_k；否则按 RRF 顺序截断为 top_k。
- **可选：外部 Rerank**（`tools/rerank_client.py`）：支持 Jina `v1/rerank` 与 SiliconFlow `v1/rerank`，无需本地 Cross-Encoder。未设置密钥时行为与原先 RRF 截断一致。

---

## 第六章：部署与运行说明

### 6.1 Python 环境

- 推荐：Python 3.10+（当前开发环境为 3.13）。
- 安装依赖（示例）：

```bash
pip install -r requirements.txt
```

> 若暂未提供 `requirements.txt`，关键依赖包括：  
> `langgraph`, `langchain-openai`, `langchain-community`, `qwen`, `dashscope`, `python-dotenv`, `numpy`, `sqlite3`（内置）。

### 6.2 环境变量配置（.env）

在项目根目录创建 `.env`：

```bash
# 千问 Qwen（聊天 + Embedding）
QWEN_API_KEY=你的千问Key
QWEN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1

# Redis（会话热缓存）
REDIS_URL=redis://localhost:6379/0

# 可选：Hybrid 检索后的外部重排序（Jina 或 SiliconFlow，不设密钥则跳过）
# RERANK_PROVIDER=jina
# RERANK_API_KEY=  # 或使用 JINA_API_KEY / SILICONFLOW_API_KEY
# RERANK_MODEL=jina-reranker-v2-base-multilingual
# RERANK_API_URL=https://api.jina.ai/v1/rerank
# SiliconFlow 示例：RERANK_PROVIDER=siliconflow RERANK_MODEL=BAAI/bge-reranker-v2-m3
# RERANK_DISABLED=1  # 有关闭需求时设为 1
```

### 6.3 手动启动与关闭（与 6.2 环境变量配合）

与「快速开始」一致：**Redis（可选）→ 后端 `127.0.0.1:8000` → 前端 `npm run dev` → 浏览器访问 `http://localhost:3000`**。关闭时各终端 `Ctrl + C`。

### 6.4 快速自测流程（从记忆到 RAG）

1. 初始化 / 迁移数据库（含 Q2 向量化）：

   ```bash
   python scripts/migration.py
   ```

2. 压测 Hybrid RAG 行为：

   ```bash
   python test_suite/test_rag.py
   ```

3. 查看 Q2 记忆矩阵当前内容：

   ```bash
   python scripts/inspect_q2.py
   ```

4. 示例：插入一条 Career_Nuke 规划样本并验证检索：

   ```bash
   python scripts/insert_career_nuke.py
   python scripts/migration.py
   python test_suite/test_rag.py
   ```

5. 测试路由引擎整体流转：

   ```bash
   python test_suite/test.py
   ```

6. 启动 FastAPI（服务接口）并进行流式调用测试：

   - 接口：`POST /api/v1/chat/stream`（SSE，建议用于前端演示）

7. 启动 Next.js 演示页（展示路由分区）：

   - 在 `frontend/` 目录运行 `npm run dev`，浏览器打开 `http://localhost:3000`

8. 运行日志清洗飞轮（input -> SFT jsonl -> archive）：

   ```bash
   # 默认读取 ./input/*.log，输出到 ./output/SFT_training_data.jsonl
   python tools/logs_to_sft.py
   ```

   ```bash
   # 自定义输入输出目录 + 自定义 system instruction
   python tools/logs_to_sft.py --input-dir logs --output-dir output --system-instruction "你是一个高可靠训练数据清洗器。"
   ```

   ```bash
   # 从文件注入 system instruction（优先级高于 --system-instruction）
   python tools/logs_to_sft.py --system-instruction-file prompts/bit_sft_system.txt
   ```

   - 产物说明：
     - `output/SFT_training_data.jsonl`：清洗后的训练样本（JSONL，一行一条记录，可直接用于 SFT）。
     - `output/sft_manifest.json`：本次跑批的执行清单（输入目录、样本条数、源日志文件、归档路径等元数据）。
     - `output/archive/<时间戳>/*.log`：本次已处理的原始日志备份，用于避免重复清洗与后续追溯。

9. 前端交互界面（聊天 / 清洗模式 + 对话导航）：

   - 界面地址：`http://127.0.0.1:3000`
   - 功能特性：
     - 左侧为主交互区：支持「聊天模式」与「清洗模式」切换，清洗模式下可：
       - 从默认 `input/` 目录下拉选择日志文件，或上传本地文件；
       - 注入自定义 `system instruction`（手写或文件）；
       - 触发 Bit 自动执行「日志清洗 -> SFT_training_data.jsonl -> archive」流水线。
     - 下方展示对话记录：用户在右侧气泡、模型在左侧气泡，最近记录可滚动查看。
     - 右侧为会话导航栏：
       - 显示当前对话轮数（最多 50 轮），超过上限需新建会话；
       - 列出最近 prompt，点击可平滑滚动定位到对应轮次；
       - 提供「新建对话」「重置 session」「导出会话」等操作，导出的会话存放于 `output/chats/*.jsonl`。

---

## 第七章：MVP 指标与工程亮点

### 7.1 MVP 指标（示例）

- **开发流水线完整交付率（A 方向）**：
  - 统计 `dev_pipeline` 四步均产出结构化结果的比例（`DevTaskSpec/DevOutline/DevCodeSketch/DevTestsChangelog`）。
  - 目标：连续 N 次运行保持稳定、无字段缺失。
- **Token 预算收敛效果**：
  - 对比“全量上下文直喂”与“步骤 JSON 摘要传递”两种方案；
  - 观察输入长度、响应延迟、输出可读性，验证预算策略有效。
- **Trace 可观测性覆盖率**：
  - 每次请求是否都返回 `trace_id + trace[]`；
  - 前端是否可稳定展示每一步节点、耗时、摘要。

### 7.2 工程亮点

- **AI 软件工程流水线主导**：把需求、迭代、DoD、回顾等实践做成可执行四步结构化流程。
- **Token 成本意识内建**：通过 `context_budget` 做统一预算，步骤间 JSON 摘要传递替代长文本重复注入。
- **全链路追踪可复盘**：SSE/meta 返回 `trace_id + trace[]`，支持步骤级定位与性能分析。
- **默认路由能力可插拔**：`AX_DEFAULT_ROUTER_BACKEND`（兼容 `AX_CABINET_BACKEND`）解耦默认实现，便于重构或替换不同多 Agent 后端。
- **Structured Output + Pydantic**：输出契约强类型化，降低协议漂移与下游解析风险。
- **记忆/RAG 作为基础能力**：SQLite + FTS5 + 向量 + RRF 保留，服务通用检索与历史兼容。

---

## 第八章：参考文档与设计记录

- **本仓库 · 开发者文档**：[docs/项目结构与技术要点.md](docs/项目结构与技术要点.md)（项目结构、HTTP API、LangGraph 与记忆/RAG 模块、全链路追踪、扩展点；面向二次开发与代码级梳理。）

下方链接指向最初公开版本（Agentic-task-router 仓库）的系统设定与 ADR，当前项目在此基础上增加了 L3 记忆矩阵与 Hybrid RAG，可视为「记忆内核 + 检索升级版」：

- [Axiodrasil System BIOS (全局设定与认知法案)](https://github.com/TraitYoung/Agentic-task-router/blob/main/docs/Axiodrasil_BIOS_V17.0.md)
- [ADR-001: 关于“身心痛感指标”量化标尺的校准决策](https://github.com/TraitYoung/Agentic-task-router/blob/main/docs/adr/ADR-001-pain_level_calibration.md)

