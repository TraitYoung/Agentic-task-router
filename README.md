## Axiodrasil Core（简历项目版）

基于 LangGraph + 千问 (Qwen) 的个人「内阁」工作流内核，包含：

- **多 Agent 路由引擎**：按任务类型路由到逻辑执行官 Taki、情感官 Bina、战略官持正 (Chizheng)、医疗熔断千金 (Qianjin)。
- **L3 记忆矩阵**：将重要/战略级别的对话切片存入 SQLite 持久层。
- **Hybrid RAG 引擎**：对 Q2 战略记忆做 FTS5 + 向量召回 + RRF 融合，实现工业级的「长期规划回忆」。

这是一个可以直接运行的「AI 简历项目」：既展示设计思路，又可真实落地跑通。

---

## 项目结构

```text
aixodrasil_core/
├─ agents/
│  └─ router.py              # LangGraph 路由引擎（多 Agent 内阁）
├─ memory/
│  └─ database.py            # L3 记忆矩阵 + FTS5 + 向量表
├─ tools/
│  └─ ai_client.py           # 千问 DashScope embedding 客户端
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

## 核心架构总览

- `agents/router.py`  
  LangGraph 构建的路由图：
  - `node_parser`：调用千问大模型 + Pydantic 协议 `TaskIntent`，将用户输入映射到逻辑 / 情感 / 战略 / 医疗四类任务，并标注认知象限 Q1〜Q4。
  - `node_taki_bit`：逻辑执行节点，挂载工具链（如代码执行、文件写入等）。
  - `node_bina`：情感疏导。
  - `node_chizheng`：宏观战略。
  - `node_qianjin`：医疗熔断（高痛感直接切断工作流）。
  - `route_by_intent`：根据 `task_type` 与 `pain_level` 决定路由。

- `memory/database.py`  
  负责 L3 记忆的落盘与索引：
  - 表结构：
    - `memory_matrix`：主表，存储 `id / thread_id / quadrant / content / status / created_at`。
    - `memory_embeddings`：向量表，`memory_id -> embedding (BLOB)`，约定为 1536 维 float32。
    - `memory_fts`：SQLite FTS5 external-content 虚拟表，对 `content / quadrant / thread_id` 建全文索引。
  - 触发器：
    - INSERT / UPDATE / DELETE 时自动更新 `memory_fts`，保证关键词检索与主表一致。

- `hybrid_engine.py`  
  Hybrid 检索核心类 `HybridRetriever`：
  - `_get_keyword_scores`：基于 FTS5 + BM25 的关键词召回。
  - `_get_vector_scores`：基于 `memory_embeddings` + 余弦相似度的语义召回。
  - `rrf_fusion`：对两路召回结果按 rank 做 RRF 融合。
  - `search_hybrid`：统一入口，返回前 `top_k` 条最相关的记忆（支持按 `thread_id` / `quadrant` 过滤）。

- `tools/ai_client.py`  
  千问 Embedding 客户端：
  - 使用 `DashScopeEmbeddings(model="text-embedding-v2")`。
  - 暴露 `get_embedding(text) -> np.ndarray[float32, 1536]`。

---

## RAG 流程说明（Q2 战略记忆）

1. **写入记忆**  
   - 当解析到 `quadrant` 为 `Q2` 时，`router` 会调用 `PersonaMemory.save_memory` 将原始输入落盘到 `memory_matrix`。
   - SQLite 触发器自动将文本同步到 `memory_fts`，支持后续 FTS5 检索。

2. **冷启动向量化**  
   - 脚本：`migration.py`
   - 功能：扫描所有 `quadrant='Q2'` 且尚未写入向量表的记录，调用 `get_embedding` 生成 1536 维向量后写入 `memory_embeddings`。
   - 命令：
     ```bash
     python migration.py
     ```

3. **Hybrid 检索压测**  
   - 脚本：`test_rag.py`
   - 使用方式：
     ```bash
     python test_rag.py
     ```
   - 行为：
     - 对查询「关于 Career_Nuke 的长线职业规划是什么？」执行：
       - FTS5 关键词召回（Q2 + 主线程）。
       - 千问 embedding 向量召回。
       - RRF 融合重排。
     - 输出：
       - 【主命中】：RRF 排名第一条的完整内容。
       - 【其他候选】：余下候选的摘要，便于审计与调参。

4. **演化记录**  
   - 所有从「测试失败」到「真·成功」的细节过程，记录在：
     - `logs/rag.log`
   - 内容包括：
     - 数据库 schema 的演化。
     - OpenAI 兼容模式失败 → DashScope 官方 SDK 适配。
     - Career_Nuke 记忆缺失 → 插入 Q2 样本 → 检索命中。

---

## 环境与运行方式

### 1. Python 环境

- 推荐：Python 3.10+（当前开发环境为 3.13）。
- 必要依赖（示例）：

```bash
pip install -r requirements.txt
```

> 若暂未提供 `requirements.txt`，关键依赖包括：  
> `langgraph`, `langchain-openai`, `langchain-community`, `qwen`, `dashscope`, `python-dotenv`, `numpy`, `rank-bm25`, `sqlite3`（内置）。

### 2. 环境变量配置（.env）

在项目根目录创建 `.env`，示例：

```bash
# 千问 Qwen（聊天 + Embedding）
QWEN_API_KEY=你的千问Key
QWEN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1

# 其他模型 / 服务可按需扩展
```

### 3. 快速自测步骤

1. 初始化/迁移数据库（含 Q2 向量化）：

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

4. 示例：插入一条 Career_Nuke 规划样本：

   ```bash
   python insert_career_nuke.py
   python migration.py
   python test_rag.py
   ```

---

## 作为简历项目的亮点

- **工业级 Hybrid RAG 设计**  
  而不是简单的「向量相似度检索」，采用 FTS5 + 向量召回 + RRF 融合，符合大规模检索系统的工程范式。

- **可观测性与演化日志**  
  专门的 `logs/rag.log` 记录了从「失败」到「成功」的完整推理与演进过程，体现问题定位与系统性思考能力。

- **与多 Agent 工作流深度集成**  
  RAG 不是孤立模块，而是服务于 Q2 战略记忆，与 `TaskIntent` 协议、认知象限划分、LangGraph 流程协同工作。

- **可移植、可扩展**  
  记忆层基于 SQLite + FTS5 + 向量表设计，方便迁移到更大规模的后端（如 Postgres pgvector / Milvus 等）。

---

## 后续可扩展方向（Roadmap）

- 为 Q1/Q3 构建不同权重的 RAG 通道（紧急任务优先级更高）。
- 将 `HybridRetriever` 的结果自动注入 `node_chizheng` 的系统 Prompt，形成「长期规划一体化回忆」。
- 封装 Web API / CLI 接口，对外暴露统一的「认知引擎 + 记忆检索」服务。

# Axiodrasil: Multi-Agent Task Router

[![Python 3.13](https://img.shields.io/badge/Python-3.13-blue.svg)](https://www.python.org/)
[![LangGraph](https://img.shields.io/badge/Orchestration-LangGraph-orange.svg)](https://github.com/langchain-ai/langgraph)
[![Pydantic](https://img.shields.io/badge/Protocol-Pydantic_V2-red.svg)](https://docs.pydantic.dev/)

Axiodrasil 是一个基于 LangGraph 的多智能体任务路由引擎。针对高压任务环境，系统通过大模型结构化输出 (Structured Output) 与严格的 Pydantic 协议，将非结构化的自然语言映射为 4 条独立执行轨道，实现“逻辑处理”与“情绪/医疗干预”的物理隔离。

## 📊 MVP 阶段性能与测试数据 (Data & Metrics)

本系统在构建过程中，重点解决了大模型在意图解析时的**“同理心泛滥 (Empathy Overflow)”**与**“Schema 语义丢失”**问题。

* **医疗熔断误报率 (FPR) 降低：** * *测试场景*：输入极端情绪词汇（如“想哭”、“全军覆没”），但无躯体化症状。
    * *优化前*：大模型倾向于给出 `pain_level >= 8`，导致 75% 以上的情绪输入被错误路由至“医疗干预”节点。
    * *优化后*：通过显式 System Message 注入严格量表（7分以上必须具备手抖、心脏狂跳等生理特征），**误触发率降至 0%**，精准回落至 4-6 分（情绪支持节点）。
* **状态机流转延迟 (Latency)：**
    * 核心路由引擎（包含一次 LLM API 网络开销与 Pydantic 校验）单次判断耗时稳定在 **~800ms - 1.2s** 之间（基于 Qwen-Plus 接口测试），无死锁跳出。

## 🛠️ 核心执行管线 (Execution Pipeline)

数据在系统内部的流转遵循严格的 DAG (有向无环图) 拓扑：

1.  **L1 Cache (GraphState)**：捕获用户的 `current_input`。
2.  **强类型防波堤 (Node Parser)**：调用绑定的 LLM 将文本解析为 `TaskIntent` 对象。若格式违规，Pydantic 异常捕获机制将阻断脏数据向下游扩散。
3.  **双重权重路由 (Conditional Edge)**：
    * **Tier 1 (生存优先)**：若 `pain_level > 6`，强制覆写任务类型，切入 `medical_route`。
    * **Tier 2 (业务分发)**：识别 `logic`, `emotion`, `strategy`，分发至对应 Agent。

## 🚀 快速启动

1.  **环境配置**:
    ```bash
    pip install langchain-openai langgraph pydantic python-dotenv
    ```
2.  **密钥挂载**: 在根目录创建 `.env`，物理隔离 API 密钥。
    ```env
    QWEN_API_KEY="sk-xxxxxx"
    ```
3.  **点火测试**:
    ```bash
    python test.py
    ```

**终端输出示例 (Terminal Log)：**
```text
=== Axiodrasil 核心流转测试启动 ===
[Root 原始输入]: 我今天在自习室熬了8个小时，情绪已经见底了，真的好累，快夸夸我。

--- 开启节点流转监控 ---
-> [系统] 正在呼叫大模型进行意图解析...
-> [审计] 大模型解析结果: 任务=emotion, 痛感=5
📍 [系统追踪] 数据到达节点 -> parser
📍 [系统追踪] 数据到达节点 -> emotion_agent
   [Bina]: 正在提供情绪价值与能量补给。

```

## 📚 架构蓝图与决策记录 (Docs)

> 下方链接指向最初的公开版本（Agentic-task-router 仓库），
> 当前项目在此基础上增加了 L3 记忆矩阵与 Hybrid RAG 引擎，可视为 Axiodrasil 的「记忆内核 + 检索升级版」。

* [Axiodrasil System BIOS (全局设定与认知法案)](https://github.com/TraitYoung/Agentic-task-router/blob/main/docs/Axiodrasil_BIOS_V15.0.md)
* [ADR-001: 关于“身心痛感指标”量化标尺的校准决策](https://github.com/TraitYoung/Agentic-task-router/blob/main/docs/adr/ADR-001-pain_level_calibration.md)
