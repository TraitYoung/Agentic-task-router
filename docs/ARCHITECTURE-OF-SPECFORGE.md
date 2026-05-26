# SpecForge 架构详解（面试用）

## 一句话概述

SpecForge 是一个 AI 软件工程规格生成器——用户输入产品想法或粘贴代码，系统自动输出结构化工程文档（需求规格、Sprint 规划、实现草案、测试方案、代码审查报告）。

技术栈：FastAPI + Next.js 16 + LangChain + Pydantic v2 + SQLite FTS5 + Redis + Docker

---

## 系统架构总览

```
┌─────────────────────────────────────────────────┐
│  用户浏览器 (Next.js 前端)                        │
│  - 聊天 UI + Trace 面板                           │
│  - SSE 流式接收                                   │
└──────────────────┬──────────────────────────────┘
                   │ HTTP POST → Next.js API Route → 代理至 FastAPI
                   ▼
┌─────────────────────────────────────────────────┐
│  FastAPI 后端 (main.py)                           │
│  - 路由层：鉴权、限流、请求校验                     │
│  - 中间件：CORS、RateLimit、RequestLog、Prometheus │
└──────────────────┬──────────────────────────────┘
                   │ 委托给 ChatTurnRunner
                   ▼
┌─────────────────────────────────────────────────┐
│  服务层 (services/)                                │
│  - chat_turns.py：协调一次对话回合的完整生命周期      │
│  - retrieval_context.py：构建 RAG 检索上下文         │
│  - pipeline_memory.py：回写产物到知识库               │
└──────────────────┬──────────────────────────────┘
                   │ 调用流水线编排器
                   ▼
┌─────────────────────────────────────────────────┐
│  编排器 (agents/dev_pipeline/orchestrator.py)       │
│  - 正向 6 步流水线 / 逆向单步审查                    │
│  - 步骤间只传 JSON 摘要（控制 Token 成本）            │
│  - 每步生成 Trace（耗时、Token、摘要、内存）          │
│  - 支持同步 / SSE 流式双模式                         │
└──────────────────┬──────────────────────────────┘
                   │ 每一步调用对应 Agent
                   ▼
┌─────────────────────────────────────────────────┐
│  Step Agents (agents/dev_pipeline/step_agents.py)  │
│  - 6 个独立 Agent，各有自己的 System Prompt          │
│  - 每个 Agent 输出对应一个 Pydantic v2 结构化模型     │
│  - 可独立路由到不同 LLM 模型                         │
└──────────────────┬──────────────────────────────┘
                   │ 结构化输出校验
                   ▼
┌─────────────────────────────────────────────────┐
│  数据层 (schemas/ + memory/)                       │
│  - Pydantic v2 模型：字段级约束 + field_validator    │
│  - SQLite FTS5：全文检索历史 Spec + 高频 Issue       │
│  - Redis：会话缓存（降级不影响核心能力）               │
└─────────────────────────────────────────────────┘
```

---

## 完整数据流（一次对话回合）

### 正向 Spec 模式：想法 → SPEC.md（6 步流水线）

**Step 0 — 请求入口**

用户在前端输入框填写产品想法（如"做一个个人记账 App，支持多账户、分类预算"），选择 "Spec" 模式，点击发送。

→ Next.js API Route `frontend/app/api/chat/stream/route.ts` 接收请求
→ 添加 `x-session-id`、`x-api-key` 等头，转发至 FastAPI `/api/v1/chat/stream`
→ FastAPI 在 `main.py` 中经过 Auth 中间件 → RateLimit 中间件 → 请求日志中间件
→ 解析请求体 `{text, mode: "spec"}`，创建 `ChatTurnRunner` 实例

**Step 1 — RAG 检索上下文构建**

`ChatTurnRunner` 首先调用 `build_retrieval_context()`：

- Spec 模式下：用用户输入的关键词在 SQLite FTS5 中全文搜索，检索 Top-3 相似历史 Spec
- 提取历史 Spec 的 goal（目标）、user_stories（用户故事）、modules（模块拆分）
- 组装为 retrieval_context 字符串，后续注入各步骤的 Prompt
- 中文分词：FTS5 内置 tokenizer 对中文支持有限，自动降级为 LIKE 通配符模糊匹配
- 为什么用 FTS5 而不是向量数据库：规格文档是术语匹配场景（"用户登录"、"权限管理"），关键词搜索比语义搜索更精准；零外部依赖，部署更简单

**Step 2 — 项目画像检测**

调用 `detect_dev_profile()`，通过关键词匹配识别项目类型：

- 支持 5 种类型：Web 应用、移动端、API 服务、数据流水线、游戏工具
- 每种类型有专属的 prompt_injection（工程偏好）和 output_focus（输出关注点列表）
- 例如检测到 "React"、"网页" → 注入"前后端分离、组件复用、响应式布局、SEO、首屏性能"等关注点
- 生成 `profile` 字典，传入各步骤 Prompt

**Step 3 — 模型路由解析**

每个步骤调用 `resolve_step_llm(step_id)`：

- 从环境变量读取步骤级模型配置（如 discovery 用 kimi-k2.6，test_code 用 moonshot-v1-8k）
- 按步骤粒度调配：需求分析用强模型保证质量，代码生成可用便宜模型降成本
- 支持独立配置 max_tokens、reasoning_effort、timeout
- 实例化 `ChatOpenAI` 并缓存，同一配置复用

**Step 4 — 6 步顺序流水线执行**

编排器 `run_dev_pipeline()` 按序执行（有依赖关系的串行，无依赖的并行）：

| 步骤 | Agent | 输入 | 输出 | Pydantic 模型 |
|------|-------|------|------|---------------|
| 1. Discovery | 需求教练 | 用户原文 + profile + RAG上下文 | 用户故事、验收标准、Sprint目标 | DevTaskSpec |
| 2. Sprint | Tech Lead | Discovery输出JSON + profile | 模块拆分、数据流、有序待办、技术风险 | DevOutline |
| 3. Implementation | 实现工程师 | Discovery + Sprint输出 | 目录结构、核心组件代码草稿 | DevCodeSketch |
| 4. Delivery | QA Coach | Implementation草案 + Discovery验收标准 | 测试用例、DoD清单、CI/CD建议 | DevTestsChangelog |
| 5. Test Code | 测试工程师 | Implementation代码 + Delivery测试方案 | 2~3个可粘贴的测试文件 | DevTestBundle |
| 6. Merge | 发布经理 | 前5步全部输出 | 汇总 SPEC.md + Release Notes | — |

关键设计：
- 步骤间只传 JSON 摘要，不传原始 Prompt 全文。例如 Step 2 只接收 Step 1 输出的 `DevTaskSpec.model_dump()`，不是 Step 1 的完整 System Prompt + LLM 回复
- 用户原文有硬截断上限（`WORKFLOW_USER_TEXT_MAX_CHARS`），防止超长输入撑爆上下文
- Delivery 步骤在 Implementation 完成后才执行，确保测试用例与代码草案对齐（串行对齐）
- Implementation 和 Delivery 在同一级流水线中，但 Delivery 的输入包含了 Implementation 的输出

**Step 5 — SSE 流式返回 + 产物落盘**

- 每步执行时通过 `event_queue` 发送 SSE 事件：
  - `status`：当前执行到哪一步（如 "正在分析需求..."）
  - `partial`：每步完成后的部分摘要 Markdown（前端逐段显示）
  - `done`：全部完成，附带完整 SPEC.md 和 chat 摘要
- 聊天气泡只显示短摘要
- 完整 SPEC.md 写入 `output/chats/` 目录
- 前端 Trace 面板显示每步耗时、估算 Token、内存使用

---

### 逆向 Review 模式：代码 → REVIEW.md（单步）

用户粘贴代码片段，选择 "Review" 模式：

- 不走 6 步流水线，走单步 `Reverse Engineer Agent`
- 从代码反推：推测的业务目标、缺失的测试、架构问题（耦合、职责不清）、代码质量问题（命名、硬编码）
- 按优先级排列改进计划
- 附带可直接粘贴到 Cursor 的重构 Prompt
- RAG 检索：检索 Top-8 高频 Issue（如"缺少错误处理"、"硬编码配置"）和对应建议，注入 Prompt 作为参考模式

---

## 模块职责速查

### 后端核心模块

**`backend/main.py`** — FastAPI 入口
- 路由注册、中间件挂载、异常映射、健康检查
- 不做业务逻辑，只做 HTTP 层的请求/响应处理
- 暴露端点：`/api/v1/chat`、`/api/v1/chat/stream`、`/api/v1/chat/history`、`/api/v1/chat/export`、`/api/v1/health`

**`backend/services/chat_turns.py`** — 对话回合协调器
- 一个 ChatTurn 的完整生命周期：检索 → 模型选择 → 流水线执行 → 记忆写入 → Redis 会话更新 → 流完结
- 支持 `start`（新对话）和 `continue`（断点续跑）两种 action
- 断点续跑：流水线在某个步骤完成后暂停，用户选择后续方向后继续

**`backend/services/retrieval_context.py`** — RAG 检索上下文构建
- Spec 模式：FTS5 全文检索 Top-3 历史 Spec，提取 goal + user_stories + modules
- Review 模式：检索 Top-8 高频 Issue，按出现频率降序
- 中文降级策略：FTS5 分词失败 → LIKE 通配符模糊匹配

**`backend/services/pipeline_memory.py`** — 流水线记忆回写
- 将生成的 Spec 的关键字段（goal、user_stories、modules）写入 SQLite FTS5 索引
- 将 Review 中发现的 Issue 按频率聚合写入知识库
- 实现"越用越准"的持续学习

**`backend/agents/dev_pipeline/orchestrator.py`** — 核心编排器
- 正向 Spec：6 步顺序流水线，步骤间有依赖关系
- 逆向 Review：单步执行
- 支持双模式：同步返回 JSON / SSE 流式
- 每步生成 Trace 记录：步骤名、序号、耗时、摘要、Token 估算、内存
- 断点续跑机制：流水线可在特定步骤后暂停，等待用户选择继续
- Pydantic 校验失败自动重试（每步最多重试 2 次）

**`backend/agents/dev_pipeline/step_agents.py`** — 6 个 Step Agent
- 每个 Agent：独立 System Prompt + 独立结构化输出 Schema + 独立模型路由
- Discovery Agent：需求教练角色，拆分用户故事与验收条件
- Sprint Agent：Tech Lead + Scrum Master 角色，输出架构设计和 Sprint 规划
- Implementation Agent：实现工程师角色，输出代码草稿
- Delivery Agent：QA Coach 角色，对照草案编写测试方案与 DoD
- Test Code Agent：生成可粘贴的测试代码文件
- Merge Agent：汇总所有输出，生成 SPEC.md

**`backend/schemas/workflows.py`** — Pydantic v2 结构化输出模型
- `DevTaskSpec`：需求规格（goal, user_stories, acceptance_criteria, sprint_goal, measurable_outcome）
- `DevOutline`：Sprint 设计（modules, data_flow, ordered_backlog, tech_spikes, parking_lot）
- `DevCodeSketch`：代码草案（directory_structure, core_files，含 language 和 dependencies）
- `DevTestBundle`：测试方案（test_cases, dod_checklist, ci_cd_hints, changelog）
- `DevTestsChangelog`：测试代码草案 + Release Notes
- `ReverseEngineerSpec`：逆向审查输出
- 所有模型有 field_validator 做字段级校验，LLM 输出不符合 schema 则触发重试

**`backend/config/context_budget.py`** — Token 预算控制
- `WORKFLOW_USER_TEXT_MAX_CHARS`：用户输入硬截断上限
- `WORKFLOW_STEP_JSON_MAX_CHARS`：步骤间传递的 JSON 摘要截断上限
- `clip_text()`：超长文本截断函数

**`backend/config/step_model_routing.py`** — 步骤级模型路由
- 每个步骤可配置不同模型（同 API Key 下切换 model 参数）
- 按步骤粒度调配成本：强步骤用强模型，轻步骤用轻模型
- 模型实例缓存，避免重复创建

**`backend/prompts/dev_pipeline_profiles.py`** — 项目画像检测
- 5 种项目类型关键词匹配
- 每种类型的 prompt_injection（领域知识注入）和 output_focus（输出偏好）
- 自动识别不依赖用户手动指定

**`backend/memory/spec_store.py`** — SQLite FTS5 规格存储
- 建表：specs（正向规格）+ issues（逆向审查发现的问题）
- FTS5 全文索引：对 goal、user_stories、modules 等关键字段建索引
- `search_specs()`：BM25 相关性搜索
- `get_top_issues()`：按 frequency 降序返回高频问题
- 启动时自动 `_migrate()` 建表

**`backend/memory/session_cache.py`** — Redis 会话缓存
- 存储最近 N 轮对话历史（`append_turn`、`get_history`）
- Redis 不可用时降级：核心生成能力不受影响，只是丢失会话历史

---

### 前端核心模块

**`frontend/app/page.tsx`** — 聊天主页面
- 聊天气泡 + 输入框 + 模式切换（Spec/Review）
- SSE 流式接收，逐段渲染摘要
- Trace 面板：展开查看每步耗时和关键指标
- StageChoicePanel：流水线暂停时的选项面板
- StreamingStatusBar：流式状态指示

**`frontend/app/api/chat/stream/route.ts`** — Next.js API Route
- 反向代理到 FastAPI 后端
- 保留 `x-session-id` 等请求头透传
- SSE 响应直接透传给前端
- `maxDuration: 300`（5 分钟，匹配后端 LLM 调用超时）

---

## 关键设计决策 & 面试话术

### 1. 为什么用 Pydantic v2 约束 LLM 输出？

**问题：** LLM 输出格式不稳定，多步流水线中上一步的输出漂移会被下一步放大，最终生成的 SPEC.md 可能有字段缺失、类型错误、结构不一致。

**方案：** 每个步骤输出对应一个 Pydantic v2 模型，`field_validator` 做字段级校验。不符合 schema 的输出自动触发 LLM 重试（最多 2 次）。

**效果：** 步骤间传递的数据有契约保证，下游 Agent 收到的 JSON 结构可预期，不会出现"字段名变了"或"类型错了"的问题。

**面试时一句讲清：** "多步 AI 流水线最大的问题是输出漂移会级联放大，我在每一步加了结构化校验做'质量门禁'——生成的 JSON 必须符合预定义 schema，否则重试。"

---

### 2. 为什么步骤间只传 JSON 摘要？

**问题：** 如果把上一步的完整 Prompt + LLM 回复原样传给下一步，6 步下来上下文会指数膨胀，Token 成本失控。

**方案：** 步骤间只传 Pydantic 模型的 `model_dump()`（JSON 摘要），不传原始 Prompt。用户输入有硬截断上限，JSON 摘要也有截断上限。

**效果：** 每步的上下文只包含：当前步骤的 System Prompt + 上游 JSON 摘要（通常几百 token）+ 用户原始输入（截断至 N 字符）。总 Token 消费是线性增长而不是指数增长。

**面试时一句讲清：** "流水线步骤间如果不做控制，上下文会像滚雪球一样膨胀。我设计的是只传结构化摘要——Discovery 的输出只取 user_stories 和 acceptance_criteria 给 Sprint，不传完整 Prompt。"

---

### 3. 为什么用 FTS5 而不是向量数据库？

**问题：** RAG 检索需要找到相似的历史 Spec，常见方案用 embedding + 向量相似度。

**方案：** 选 SQLite FTS5（全文搜索引擎）。

**理由：**
- 规格文档是术语匹配场景。"用户登录"、"权限管理"、"账单报表"这类术语，关键词搜索（BM25）比语义搜索更精准
- 零外部依赖。不需要额外部署向量数据库或 embedding 服务
- SQLite 文件即数据库，部署和备份极简
- 中文分词有局限（FTS5 内置 tokenizer 不支持中文分词），做了降级策略：FTS5 匹配失败时改用 LIKE 模糊搜索

**面试时一句讲清：** "规格文档的搜索是术语匹配，不是语义理解——'用户登录'就是'用户登录'，不需要向量相似度来近似。FTS5 的 BM25 关键词搜索更准，而且零依赖。"

---

### 4. 步骤级模型路由的设计意图？

**问题：** 整条流水线锁死一个模型，要么贵要么弱。

**方案：** 每个步骤可以独立配置模型。需求分析（Discovery）用强模型保证质量，代码生成（Test Code）可以用便宜模型降成本，Merge 汇总又用回强模型。

**实现：** `resolve_step_llm(step_id)` 从环境变量读取步骤级模型配置，实例化不同 `ChatOpenAI`，按 `step_id` 缓存。

**面试时一句讲清：** "不是所有步骤都需要最强的模型。按步骤粒度调配——分析类步骤用强模型，生成类步骤用经济模型，既控制成本又不牺牲关键步骤的质量。"

---

### 5. 为什么 Delivery（测试方案）要等 Implementation（实现草案）完成后再执行？

**问题：** 如果测试方案和代码草案并行生成，两者会基于各自的 LLM 推理产生不一致——测试用例测的可能是代码草案里根本没有的功能。

**方案：** Delivery 步骤串行等 Implementation 完成，接收代码草案作为输入，由此生成测试用例和 DoD。这份测试方案是针对"已经写出的代码"的，不是针对"想象中的需求"的。

**面试时一句讲清：** "并行提速但会牺牲一致性。测试方案和代码草案如果同时生成，测试用例可能测的是不存在的东西。我让测试串行对齐代码——先出草案，再对照草案写测试。"

---

### 6. RAG 双向检索设计

**正向检索（Spec 模式）：** 检索历史相似需求的 goal + user_stories + modules → 作为 Few-shot 参考，提升新 Spec 的结构一致性和完整性。

**逆向检索（Review 模式）：** 检索历史上高频出现的代码问题（如"缺少错误处理"占 15 次、"硬编码配置"占 12 次）→ 注入 Prompt，帮助发现重复问题模式。

**写回机制：** 每次 Spec 和 Review 完成后，关键字段自动写入 SQLite FTS5 索引，知识库持续增长。

**面试时一句讲清：** "正向检索是'类似需求怎么做'，逆向检索是'常见坑有哪些'。两个方向共享同一个 FTS5 引擎，每次使用后自动回写，越用越准。"

---

## 面试常见问题预案

### Q: 你在这个项目里做了什么？
A: 我独立设计和开发了整个项目。核心工作包括：6 步流水线拆分和编排、5 个 Pydantic 结构化输出模型设计、步骤间 Token 成本控制策略、基于 FTS5 的 RAG 检索系统、项目类型自动识别、步骤级模型路由、FastAPI + Next.js 端到端联调、以及 Docker 部署。

### Q: 遇到的最大挑战是什么？
A: [从你的真实经历中选一个，比如：Pydantic 约束生效不了、SSE 流断掉、LLM 输出不稳定、FTS5 中文分词问题。用"问题→分析→方案→结果"的结构讲。]

### Q: 为什么用 LangChain 而不是直接调 API？
A: LangChain 提供了 ChatOpenAI 的标准化封装和结构化输出能力（with_structured_output），不需要自己处理 JSON 解析和重试逻辑。如果直接调 API，这些基础设施都要自己写。但核心编排逻辑（流水线拆分、步骤依赖、成本控制）是我自己写的，不依赖 LangChain 的高级抽象。

### Q: 如果重新做这个项目，会改什么？
A: [建议的回答方向] 可能会把流水线从硬编码的串行顺序改为 DAG（有向无环图），让没有依赖的步骤真正并行执行，进一步降低端到端延迟。另外会考虑 WebSocket 替代 SSE，支持双向通信和更好的重连机制。

### Q: 这个项目能处理多模态输入吗？
A: 目前只支持文本输入。但架构设计上，检索和流水线编排的逻辑与输入模态无关——如果接入语音转文字 API 或图像描述 API，只需在输入层增加预处理，后续的 6 步流水线不需要改动。这是我理解的架构可扩展性：核心逻辑不依赖输入格式。

---

## 部署架构

```
┌──────────────┐     ┌──────────────────┐     ┌──────────────┐
│  Vercel       │────▶│  Hugging Face     │────▶│  Upstash      │
│  (Next.js)    │     │  Spaces (FastAPI) │     │  Redis (免费) │
│  spec-forge   │     │  ishowrelx5/      │     │  TLS 连接     │
│  .vercel.app  │     │  specforge-api    │     │               │
└──────────────┘     └────────┬─────────┘     └──────────────┘
                              │
                     ┌────────▼─────────┐
                     │  SQLite FTS5       │
                     │  data/spec_store   │
                     │  .db (本地磁盘)    │
                     └──────────────────┘
```

- 前端 Vercel：免费层，自动从 GitHub 部署
- 后端 Hugging Face Spaces Docker：免费层，监听 7860 端口
- Redis Upstash：免费层，Redis 不可用时系统降级为无会话缓存（核心生成能力不受影响）
- SQLite：Hugging Face 免费 Space 磁盘不保证长期持久化，demo 可接受，生产需迁移到托管数据库

---

## 技术亮点一句话速记

- **结构化输出** → 每个步骤有 Pydantic schema，输出不符合就重试，保证不漂移
- **Token 成本内建** → 步骤间只传 JSON 摘要，用户原文有硬截断，Token 线性增长而非指数
- **步骤级模型路由** → 发现/设计用强模型，代码生成用经济模型，按步骤粒度调配
- **RAG 双向检索** → FTS5 关键词搜索，正向查类似需求，逆向查常见坑，自动回写
- **全链路 Trace** → 每步耗时、Token、内存可追溯，支持性能复盘
- **SSE 流式输出** → 聊天气泡短摘要 + 完整 SPEC.md 落盘，兼顾体验和完整交付
- **项目画像匹配** → 自动识别 5 种项目类型，注入领域专属工程关注点
- **断点续跑** → 流水线可在特定步骤暂停，等待用户选择后继续
