# SpecForge — AI 软件工程规格锻造

[![Python 3.13](https://img.shields.io/badge/Python-3.13-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/API-FastAPI-green.svg)](https://fastapi.tiangolo.com/)
[![Pydantic v2](https://img.shields.io/badge/Protocol-Pydantic_V2-red.svg)](https://docs.pydantic.dev/)
[![Next.js 16](https://img.shields.io/badge/Frontend-Next.js_16-black.svg)](https://nextjs.org/)
[![LangChain](https://img.shields.io/badge/LLM-LangChain-orange.svg)](https://www.langchain.com/)
[![Qwen](https://img.shields.io/badge/Model-Qwen-purple.svg)](https://tongyi.aliyun.com/)
[![Redis](https://img.shields.io/badge/Cache-Redis-red.svg)](https://redis.io/)
[![TypeScript](https://img.shields.io/badge/Lang-TypeScript-3178c6.svg)](https://www.typescriptlang.org/)
[![Tailwind CSS](https://img.shields.io/badge/CSS-Tailwind_v4-06b6d4.svg)](https://tailwindcss.com/)

**你用 AI 写出了能跑的 demo，但它能上线吗？**

Vibe coding 让每个人都能把想法变成软件，但非科班背景的用户往往止步于「toy project」——没有需求文档、没有测试、架构混乱、不可维护。SpecForge 填补这个缺口：**将你的想法（或现有代码）锻造成生产级软件工程规格**。

## 工程亮点

- **结构化输出**：Pydantic v2 强类型契约 + field_validator 字段级约束，每步可验证，不会产生协议漂移
- **Token 成本内建**：步骤间只传 JSON 摘要，上下文预算统一管理，用户原文与摘要均有硬截断上限
- **全链路追踪**：每轮返回 trace_id + trace[]，记录每步骤耗时与关键输出，支持性能复盘
- **项目画像自动匹配**：关键词检测识别 Web/Mobile/API/Data/Game Tools 共 5 种项目类型，注入对应工程关注点与输出偏好
- **步骤级模型路由**：发现/设计/实现/交付/合并各步骤可独立配置不同 LLM 模型，按步骤粒度调配成本与能力
- **阶段 2 并行执行**：实现草案与测试交付通过 ThreadPoolExecutor 并行运行，降低端到端延迟
- **RAG 检索增强**：正向自动检索历史相似规格作为参考上下文，逆向积累高频代码问题模式，越用越准
- **SSE 流式输出**：前端打字机效果 + 全链路 Trace 折叠面板，附带可直接粘贴到 Cursor 的实现/测试/重构 Prompt

## 两种工作模式

### 正向工程 (Spec)：想法 → 工程规格

输入你的需求描述，系统输出一份结构化的软件工程交付包：

1. **需求发现** — 用户故事、验收标准、Sprint 目标、可度量结果
2. **Sprint 设计** — 模块拆分、数据流、有序待办、技术探针、停车场
3. **实现草案** — MVP 核心路径代码草稿（含语言标识与依赖说明）
4. **测试与交付** — 测试用例、完成定义 (DoD)、CI/CD 提示、CHANGELOG、Sprint 回顾

附带**可直接粘贴到 Cursor/Copilot 的实现 prompt**。

### 逆向审查 (Review)：代码 → 审查报告

粘贴你通过 vibe coding 产出的代码，系统反向推导：

- 推测的业务目标与用户故事
- 缺失的测试用例
- 架构问题（耦合、职责不清、缺少抽象）
- 代码质量问题（命名、错误处理、硬编码）
- 按优先级排列的改进计划

附带**可直接粘贴到 Cursor 的重构 prompt**。

## 快速开始

### 一键启动（推荐）

双击项目根目录的 **`start_dev.bat`**，自动启动 Redis + Backend + Frontend，端口就绪后打开浏览器。

### 手动启动

**1. 环境配置**

```bash
pip install -r requirements.txt
cp .env.example .env
```

`.env` 中至少配置：
```bash
QWEN_API_KEY=你的千问API密钥
QWEN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
```

**2. 启动服务**

```powershell
# 终端 1 — Redis（可选，会话缓存）
redis-server --port 6379

# 终端 2 — 后端 FastAPI
python -m uvicorn main:app --app-dir backend --host 127.0.0.1 --port 8000 --reload

# 终端 3 — 前端 Next.js
cd frontend && npm install && npm run dev
```

浏览器打开 `http://localhost:3000`。

## 项目结构

```
├── backend/
│   ├── main.py                          # FastAPI 入口
│   ├── agents/dev_pipeline/
│   │   ├── orchestrator.py              # 核心编排：正向 5 步 + 逆向审查
│   │   └── step_agents.py               # 各步骤 Agent 配置与执行
│   ├── config/
│   │   ├── context_budget.py            # Token 预算控制
│   │   └── step_model_routing.py        # 步骤级模型路由
│   ├── schemas/
│   │   ├── workflows.py                 # 5 个流水线 Pydantic 模型 + Prompt 生成
│   │   ├── protocols.py                 # TaskIntent
│   │   └── trace.py                     # TraceStep
│   ├── memory/
│   │   ├── session_cache.py             # Redis 会话缓存
│   │   ├── project_cache.py             # 项目记忆
│   │   └── spec_store.py                # SQLite FTS5 规格检索
│   └── prompts/
│       └── dev_pipeline_profiles.py     # 5 种项目画像检测
├── frontend/                            # Next.js 16 + Tailwind v4
│   ├── app/
│   │   ├── page.tsx                     # 聊天主页面（SSE + Trace 面板）
│   │   └── api/                         # API 反向代理到 FastAPI
│   └── lib/backend.ts
├── tests/                               # pytest（20 tests）
├── scripts/
│   ├── dev_stack.ps1                    # 开发环境管理
│   └── locustfile.py                    # 压测入口
├── start_dev.bat                        # 一键启动
├── docker-compose.yml
└── requirements.txt
```

## API

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/v1/health` | GET | 健康探活 |
| `/api/v1/chat` | POST | 非流式对话 |
| `/api/v1/chat/stream` | POST | SSE 流式输出（推荐） |
| `/api/v1/chat/history` | GET | 会话历史（需 `x-session-id`） |
| `/api/v1/chat/export` | POST | 导出会话为 JSONL |

```json
{
  "text": "做一个个人记账 App，支持多账户、分类预算、月度报表...",
  "mode": "spec"
}
```

`mode` 取值：`"spec"`（正向工程，默认）或 `"review"`（逆向审查）。

## 开发约定

- 遵循 [CONTRIBUTING.md](CONTRIBUTING.md) 中的工程规范
- 后端：`python -m compileall backend -q && pytest`
- 前端：`cd frontend && npx tsc --noEmit && npm run build`
- 架构细节见 [docs/项目结构与技术要点.md](docs/项目结构与技术要点.md)
