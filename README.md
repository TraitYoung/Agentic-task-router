# SpecForge — AI 软件工程规格锻造

[![Python 3.13](https://img.shields.io/badge/Python-3.13-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/API-FastAPI-green.svg)](https://fastapi.tiangolo.com/)
[![Pydantic](https://img.shields.io/badge/Protocol-Pydantic_V2-red.svg)](https://docs.pydantic.dev/)
[![Next.js](https://img.shields.io/badge/Frontend-Next.js_16-black.svg)](https://nextjs.org/)

**你用 AI 写出了能跑的 demo，但它能上线吗？**

Vibe coding 让每个人都能把想法变成软件，但非科班背景的用户往往止步于「toy project」——没有需求文档、没有测试、架构混乱、不可维护。SpecForge 填补这个缺口：**将你的想法（或现有代码）锻造成生产级软件工程规格**。

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

## 工程亮点

- **结构化输出**：Pydantic 强类型契约，每步可验证，不会产生协议漂移
- **Token 成本内建**：步骤间只传 JSON 摘要，上下文预算统一管理
- **全链路追踪**：每轮返回 trace_id + trace[]，支持步骤级复盘与性能分析
- **项目画像自动匹配**：识别 Web/Mobile/API/数据/游戏工具等 5 种项目类型，注入对应工程关注点
- **步骤级模型路由**：可为发现/设计/实现/交付/合并各步骤配置不同 LLM 模型

## 快速开始

### 1. 环境配置

```bash
# 安装后端依赖
pip install -r requirements.txt

# 配置 .env（复制 .env.example 并填入密钥）
cp .env.example .env
```

`.env` 中至少需要配置：
```bash
QWEN_API_KEY=你的千问API密钥
QWEN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
```

### 2. 启动服务

**终端 1 — Redis（可选，会话缓存）**
```powershell
redis-server --port 6379
```

**终端 2 — 后端 FastAPI**
```powershell
python -m uvicorn main:app --app-dir backend --host 127.0.0.1 --port 8000 --reload
```

**终端 3 — 前端 Next.js**
```powershell
cd frontend
npm install
npm run dev
```

浏览器打开 `http://localhost:3000`。

### 3. 关闭

各终端按 `Ctrl + C` 即可。

## 项目结构

```
├── backend/
│   ├── main.py                          # FastAPI 入口
│   ├── agents/
│   │   ├── dev_pipeline/
│   │   │   ├── orchestrator.py          # 核心编排：正向工程 + 逆向审查
│   │   │   └── step_agents.py           # 各步骤 Agent 配置与执行
│   │   └── workflow_pipelines.py        # 对外导出
│   ├── config/
│   │   ├── context_budget.py            # Token 预算控制
│   │   └── step_model_routing.py        # 步骤级模型路由
│   ├── schemas/
│   │   ├── workflows.py                 # DevTaskSpec / DevOutline / DevCodeSketch / DevTestsChangelog / ReverseEngineerSpec
│   │   ├── protocols.py                 # TaskIntent
│   │   └── trace.py                     # TraceStep
│   ├── memory/
│   │   ├── session_cache.py             # Redis 会话缓存
│   │   └── project_cache.py             # 项目记忆
│   ├── prompts/
│   │   └── dev_pipeline_profiles.py     # 5 种项目画像检测
│   ├── core_logging.py
│   └── repo_paths.py
├── frontend/                            # Next.js 16
│   └── app/
│       ├── page.tsx                     # 主页面
│       ├── layout.tsx
│       └── api/                         # API 代理
├── tests/                               # 测试（待重建）
├── scripts/
│   ├── dev_stack.ps1                    # 开发环境管理
│   └── locustfile.py                    # 压测入口
├── docs/                                # 文档与历史 ADR
└── README.md
```

## API

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/v1/health` | GET | 健康探活 |
| `/api/v1/chat` | POST | 非流式对话 |
| `/api/v1/chat/stream` | POST | SSE 流式输出（推荐） |
| `/api/v1/chat/history` | GET | 会话历史 |
| `/api/v1/chat/export` | POST | 导出会话 |

请求体 `ChatRequest`：
```json
{
  "text": "做一个个人记账 App，支持多账户、分类预算、月度报表...",
  "mode": "spec"
}
```

`mode` 取值：`"spec"`（正向工程，默认）或 `"review"`（逆向审查）。

## 开发约定

- 遵循 [CONTRIBUTING.md](CONTRIBUTING.md) 中的工程规范
- 提交前确保 `python -c "import backend.main"` 通过
- 前端修改后验证 `npm run dev` 无报错
- 参考 [docs/项目结构与技术要点.md](docs/项目结构与技术要点.md) 了解技术细节
