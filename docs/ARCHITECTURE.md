# 架构与实现映射

本文档将 SpecForge 的核心设计落点到具体源码路径，便于 code review 或面试时快速核对实现。

## 双模式 AI 流水线

| 模式 | 行为 | 入口与编排 |
|------|------|--------------|
| 正向工程（spec） | 想法 → 多步规格与交付物 | `backend/agents/workflow_pipelines.py` → `run_dev_pipeline`；核心步骤在 `backend/agents/dev_pipeline/orchestrator.py` |
| 逆向审查（review） | 代码 → 推测需求、问题与改进计划 | `run_reverse_engineer`（同上模块）；HTTP `mode` 见 `backend/main.py` |

## 五个 Pydantic v2 结构化模型

均在 `backend/schemas/workflows.py`，均含字段长度约束与 `field_validator`，步骤间以 JSON 摘要传递以控制 Token：

1. `DevTaskSpec` — 需求发现（用户故事、验收标准、Sprint 目标等）
2. `DevOutline` — Sprint 规划与设计（模块、数据流、待办、Parking lot、技术探针）
3. `DevCodeSketch` — 实现草案（语言、代码草图、备注）
4. `DevTestsChangelog` — 测试用例、DoD、CI/CD 提示、CHANGELOG、回顾
5. `ReverseEngineerSpec` — 逆向分析（推测目标、缺失测试、架构/质量问题、改进计划）

同文件还提供面向 Cursor 的 `to_implementation_prompt` / `to_test_prompt` / `to_review_prompt`。

## 并行执行

正向流水线中实现草案与测试交付阶段通过 `ThreadPoolExecutor` 并行，降低端到端延迟：`backend/agents/dev_pipeline/orchestrator.py`（搜索 `ThreadPoolExecutor`）。

## 项目类型画像

五类（Web / Mobile / API / 数据流水线 / 游戏工具）关键词检测与领域偏好注入：`backend/prompts/dev_pipeline_profiles.py`，由 orchestrator 侧解析后与提示词组合使用。

## 步骤级模型路由与上下文预算

- 各步所用 LLM 解析：`backend/config/step_model_routing.py`（环境变量驱动模型与 Base URL）
- 摘要截断与预算：`backend/config/context_budget.py`

## API、会话与观测

- FastAPI 路由与 SSE：`backend/main.py`（`/api/v1/chat/stream` 等）
- Redis 会话：`backend/memory/session_cache.py`；健康检查中的 Redis 探测见 `/api/v1/health`
- 全链路 Trace 模型：`backend/schemas/trace.py`；步骤结果随响应返回

## RAG / 知识积累

- 规格与 issue 的 SQLite FTS 检索与写入：`backend/memory/spec_store.py`
- 正向检索历史规格、逆向侧高频 issue 上下文：`backend/main.py` 中 `_execute_turn`

## 前端

- Next.js App Router、SSE 消费与 Trace UI：`frontend/app/page.tsx` 及 `frontend/app/api/*`（BFF 代理至后端）
