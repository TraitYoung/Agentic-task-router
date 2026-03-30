## Axiodrasil: 多 Agent 路由与记忆内核

[![Python 3.13](https://img.shields.io/badge/Python-3.13-blue.svg)](https://www.python.org/)
[![LangGraph](https://img.shields.io/badge/Orchestration-LangGraph-orange.svg)](https://github.com/langchain-ai/langgraph)
[![Pydantic](https://img.shields.io/badge/Protocol-Pydantic_V2-red.svg)](https://docs.pydantic.dev/)

Axiodrasil 是一个基于 LangGraph + 千问 (Qwen) 的多智能体任务路由与记忆内核，用于应对高压任务环境：

- **路由层**：将自然语言输入解析为结构化 `TaskIntent`，路由到「情绪官 Bina」「文档管理 taki」「技术/代码 bit」「战略官 juzheng」四条轨道；当 `pain_level > 6` 时触发医疗熔断逻辑，但已并入情绪节点。
- **记忆层**：将重要/战略级别（Q1/Q2）的对话片段写入 SQLite「L3 记忆矩阵」，并建立 FTS5 全文索引与向量表。
- **检索层（Hybrid RAG）**：对 Q2 战略记忆使用 FTS5 + 向量召回 + RRF 融合，实现工业级「长期规划回忆」。

本项目可直接运行，适合作为简历中的「多 Agent 工作流 + 记忆/RAG」综合工程示例。

---

## 第一章：系统整体概念

- **目标场景**：高压、自我管理场景（刷题、备考、项目冲刺），需要同时处理：
  - 严肃的逻辑任务（代码审计、算法推导等）
  - 情绪宣泄与心理缓冲
  - 中长期规划与复盘
  - 极端身心状态下的「医疗红线熔断」（已并入情绪节点）
- **核心理念**：
  - 用 **多 Agent 路由** 把「情绪 / 文档 / 技术 / 战略」物理隔离；医疗红线通过路由优先级下沉到情绪节点执行。
  - 用 **强类型协议 (Pydantic)** 把大模型输出收紧在安全边界内。
  - 用 **L3 记忆矩阵 + Hybrid RAG** 让 Q2 战略对话可以在长期内被准确「回忆」和复用。

---

## 第二章：系统宏观结构

从 10,000 米高度看 Axiodrasil，可分为三层：

1. **路由引擎层（agents/router.py）**
   - 基于 **LangGraph StateGraph**；
   - 状态 `GraphState = {current_input, thread_id, recent_history, intent, final_response}`；
   - 入口节点：`parser`；出口节点：`emotion_agent / taki_agent / bit_agent / juzheng_agent`。
2. **记忆矩阵层（memory/database.py）**
   - SQLite 主表 `memory_matrix` 存储 `thread_id / quadrant / content / status / created_at`；
   - 向量表 `memory_embeddings` 以 BLOB 形式存储 1536 维 float32 向量；
   - FTS5 虚拟表 `memory_fts` 作为 external-content 索引。
3. **热缓存层（memory/session_cache.py）**
   - Redis 会话热缓存（Session 缓存与滑动窗口），为本次路由意图解析提供最近 5 轮上下文；TTL 默认 1 小时。
4. **Hybrid RAG 层（hybrid_engine.py + tools/ai_client.py）**
   - 关键词召回：FTS5 + BM25；
   - 语义召回：向量余弦相似度；
   - 融合排序：RRF (Reciprocal Rank Fusion)。

系统总体结构（简化）：

```text
User Input
   ↓
[Router: LangGraph]
   ↓ (若 quadrant ∈ Q1/Q2)
[PersonaMemory: SQLite + FTS5 + Embeddings]
   ↓ (Q2 冷启动 / 增量向量化)
[HybridRetriever: FTS5 + Vector + RRF]
```

---

## 第三章：项目结构与角色分工

```text
├─ agents/
│  └─ router.py              # LangGraph 路由引擎（多 Agent 内阁）
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
├─ migration.py              # Q2 冷启动向量化脚本
├─ test_rag.py               # RAG 压测脚本（主命中+候选）
├─ inspect_q2.py             # Q2 内容查看（本地调试工具）
├─ insert_career_nuke.py     # 插入 Career_Nuke 样本（demo 专用）
├─ test.py                   # 路由引擎总体流转测试
├─ even_sum.py               # Taki 工具链生成的示例脚本
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
  - 如 `inspect_q2.py`、`insert_career_nuke.py`、`clear_Q1.py` 等，用于本地注入样本、查看记忆矩阵、清理测试数据。
    如果你克隆仓库后发现它们不存在，可以按 README 中的说明自行创建。

这些忽略规则与 `.gitignore` 中的配置一一对应，保证系统结构完整，同时不泄露任何个人敏感信息。

---

## 第四章：路由引擎 — 多 Agent 内阁

- **核心文件**：`agents/router.py`
- **关键概念**：
  - `TaskIntent`（见 `schemas/protocols.py`）：
    - `task_type ∈ {emotion, taki, bit, juzheng, unknown}`
    - `urgency_level ∈ [1,5]`
    - `pain_level ∈ [1,10]`，>6 触发医疗熔断优先级
    - `quadrant ∈ {Q1, Q2, Q3, Q4}`（艾森豪威尔象限）
  - `GraphState`：`{current_input, thread_id, recent_history, intent, final_response}`
  - `parser_llm = llm.with_structured_output(TaskIntent)`：大模型输出强制符合 Pydantic Schema。

### 路由逻辑（总览）

1. **Parser 节点**：
   - 将用户输入交给千问大模型；
   - 使用 `with_structured_output(TaskIntent)` 解析成强类型对象；
   - 若 `quadrant ∈ {Q1, Q2}`，调用 `PersonaMemory.save_memory` 写入 L3 记忆。
2. **熔断优先级**：
   - 若 `pain_level > 6` → 无视 `task_type`，强制路由到 `emotion_agent`（医疗逻辑并入情绪节点）。
3. **业务分发**：
   - `task_type = emotion` → `emotion_agent`（bina）
   - `task_type = taki` → `taki_agent`
   - `task_type = bit` → `bit_agent`
   - `task_type = juzheng` → `juzheng_agent`

### 四个 Agent 简述

- `emotion_agent`（bina）：
  - 负责情绪支持；当 `pain_level > 6` 时注入医疗红线内容，强制阻断工作流并给出身体动作建议。
- `taki_agent`：
  - 文档管理节点：基于 `hybrid_engine.HybridRetriever` 对 Q2 材料做 Hybrid 检索，输出关键要点 + 阅读/处理路线。
- `bit_agent`：
  - 代码/专业知识管理节点：采用 `create_react_agent(llm, tools=TAKI_TOOLS)` 进行工具链调用（联网/沙盒执行/写文件受控授权等）。
  - 会从 SQLite 的 Q1 未完成任务读取上下文，注入到 Bit 的执行 prompt。
- `juzheng_agent`：
  - 战略管理节点：提供计划拆解、步骤安排与复盘框架（结论先行、可落地）。

---

## 第五章：记忆矩阵与 Hybrid RAG

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

### 5.2 冷启动向量化（migration.py）

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
- 对外接口 `search_hybrid(query, query_embedding, top_k, thread_id, quadrant)`：
  - 返回 top_k 条最相关的 Q2 记忆，按 RRF 排序。

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

# 其他模型 / 服务可按需扩展
```

### 6.3 快速自测流程（从记忆到 RAG）

1. 初始化 / 迁移数据库（含 Q2 向量化）：

   ```bash
   python migration.py
   ```

2. 压测 Hybrid RAG 行为：

   ```bash
   python test_rag.py
   ```

3. 查看 Q2 记忆矩阵当前内容：

   ```bash
   python inspect_q2.py
   ```

4. 示例：插入一条 Career_Nuke 规划样本并验证检索：

   ```bash
   python insert_career_nuke.py
   python migration.py
   python test_rag.py
   ```

5. 测试路由引擎整体流转：

   ```bash
   python test.py
   ```

6. 启动 FastAPI（服务接口）并进行流式调用测试：

   - 接口：`POST /api/v1/chat/stream`（SSE，建议用于前端演示）

7. 启动 Next.js 演示页（展示路由分区）：

   - 访问：`frontend/` 目录并运行 `npm run dev`

---

## 第七章：MVP 指标与工程亮点

### 7.1 MVP 指标（示例）

- **医疗熔断误报率 (FPR) 降低**：
  - 测试场景：输入「想哭」「全军覆没」等极端情绪词汇但无明显躯体症状；
  - 优化前：`pain_level >= 8` 过于频繁，约 75% 情绪输入会触发医疗红线；
  - 优化后：通过 System Prompt 注入严格量表（7 分以上必须有心跳狂跳、手抖等生理特征），误触发率降至 **0%**，正确回落到情绪支持节点。
- **状态机流转延迟 (Latency)**：
  - 路由引擎（一次 LLM 调用 + Pydantic 校验）单次判断耗时约 **800ms–1.2s**（基于 Qwen-Plus 实测），稳定无死锁。

### 7.2 工程亮点

- **多 Agent + 条件路由的工程化落地**：用 LangGraph StateGraph 组织多节点，清晰的入口/出口与条件边逻辑。
- **Structured Output + Pydantic 强类型防波堤**：意图解析完全结构化，避免靠正则/字符串 parse。
- **Redis 会话热缓存 + 滑动窗口**：为路由意图解析提供最近 5 轮上下文，TTL 默认 1h；SQLite 负责冷数据持久化。
- **工业级 Hybrid RAG 设计**：FTS5 + 向量召回 + RRF 融合，而非单一路径的向量检索。
- **可观测性与演化日志**：`logs/rag.log` 等记录从失败到成功的调优过程，便于复盘与展示工程思维。
- **轻量但可迁移的存储设计**：SQLite + FTS5 + BLOB 向量，未来可无缝迁移至 Postgres + pgvector / Milvus 等。

---

## 第八章：参考文档与设计记录

下方链接指向最初公开版本（Agentic-task-router 仓库）的系统设定与 ADR，当前项目在此基础上增加了 L3 记忆矩阵与 Hybrid RAG，可视为「记忆内核 + 检索升级版」：

- [Axiodrasil System BIOS (全局设定与认知法案)](https://github.com/TraitYoung/Agentic-task-router/blob/main/docs/Axiodrasil_BIOS_V17.0.md)
- [ADR-001: 关于“身心痛感指标”量化标尺的校准决策](https://github.com/TraitYoung/Agentic-task-router/blob/main/docs/adr/ADR-001-pain_level_calibration.md)

