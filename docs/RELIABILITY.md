# SpecForge 容错设计

## 目标

SpecForge 的 demo 不只展示 happy path。上线后需要能回答三个问题：服务是否活着、失败发生在哪一步、失败后用户还能不能继续使用核心能力。

## 边界情况处理

| 场景 | 当前处理 | 用户/运维可见信号 |
| --- | --- | --- |
| LLM JSON 截断（Moonshot/Kimi） | `json_prompt` 模式检测 `finish_reason=length`，自动重试并提示缩短输出；`_extract_json_text` 括号平衡兜底 | SSE `{type:"error", step:"sprint_design", detail:"步骤…"}` |
| LLM 列表写成嵌套对象 | `schemas/coerce.py` 将 `{name,responsibility}` 压平为字符串；schema `extra=ignore` | 一般不再报错；日志 `structured_invoke: validation failed` |
| Pydantic 字段超长 | 各字段 `mode="before"` 截断后再校验 `max_length` | 极少 `string_too_long` |
| 结构化步骤思考占 token | `LLM_STRUCTURED_THINKING=disabled` 仅作用于 discovery/sprint/implementation/delivery/reverse | health `llm_structured_thinking` |
| API 限流 | `RateLimitMiddleware` 对 chat 接口限制为 10 req/min, 其他接口 30 req/min, health 60 req/min. | 返回 HTTP 429 和 `Retry-After`. |
| Redis 不可用 | 会话缓存写入失败只记录 warning, 不阻断本轮生成; health 中 `redis.ok=false`. | 前端顶部黄色提示, `/api/v1/health` 显示 Redis 错误. |
| SQLite 写入失败 | 规格/issue 保存包在 try/except 中, 检索增强失败不会影响最终回复. | 后端 warning: `save to spec_store failed`. |
| SQLite FTS 查询语法错误 | FTS5 `MATCH` 遇到特殊字符会抛 `OperationalError`; 当前实现记录 warning 并回退到 `LIKE` 检索. | 后端 warning: `spec FTS search failed, falling back to LIKE`; 用户请求继续进入 LLM 流水线. |
| 单任务 token 超预算 | `context_budget.clip_text()` 对用户输入和阶段 JSON 摘要做最大长度裁剪（默认 2500 字/步）. | Trace summary 保留 `_metrics.estimated_tokens` |
| SSE 中断 | 后端 stream 捕获异常并发送 `{type:"error", step, detail}`; 前端保留已收到内容并显示错误. | 气泡含步骤名，如「步骤 sprint_design 失败」 |
| 缺少 API key | 启动时 warning; health 中 `env.has_llm_key=false`; 真正调用 LLM 时失败. | Space logs 可见 `LLM_API_KEY not set`, health 可提前发现. |

## 结构化流水线失败类型

| 类型 | 含义 | 典型修复 |
| --- | --- | --- |
| A. JSONDecodeError | 输出被截断或含非 JSON 前缀 | 提高 `max_tokens`、设 `LLM_STRUCTURED_THINKING=disabled`、减少 modules 条数 |
| B. 结构跑偏 | 列表项为对象 | 已由 coerce 吸收；提示词要求字符串列表 |
| C. ValidationError | 缺必填字段或类型错误 | 重试时附带字段错误摘要 |

## 观测接口

`GET /api/v1/health` 不调用 LLM, 可安全作为 Hugging Face Space/Vercel 探针。响应包含:

```json
{
  "ok": true,
  "version": "2.0.0",
  "uptime_seconds": 12.3,
  "redis": { "ok": false, "error": "connection refused" },
  "sqlite": { "ok": true, "error": "" },
  "memory_mb": 96.4,
  "env": {
    "has_llm_key": true,
    "llm_model": "kimi-k2.6",
    "llm_thinking": "default",
    "llm_structured_thinking": "disabled",
    "llm_request_timeout": 300
  }
}
```

## 日志策略

- 请求级日志: `trace_id`, method, path, status, duration_ms, client_ip.
- 结构化步骤: `structured_invoke: response model=… chars=… finish_reason=…`；失败时记录 preview 800 字。
- 流水线日志: profile, input length, retrieval hit, step duration, estimated tokens, memory snapshot.
- 存储日志: spec/issue 保存成功记录 profile 和 count; 保存失败只降级为 warning.

## 生产建议

- Hugging Face 免费 Space 可能冷启动, 第一次访问需要等待构建或唤醒.
- 当前后端健康检查地址: `https://ishowrelx5-specforge-api.hf.space/api/v1/health`.
- SQLite 在免费容器中不是强持久化方案; 正式生产应挂载磁盘或迁移 PostgreSQL.
- Redis 是增强项而不是硬依赖; Upstash Redis 可作为免费 demo 缓存层.
- 如果 LLM 调用超过 Vercel 函数时间, 前端只代理请求, 长耗时主要由 Hugging Face Space 后端承接.
- 本地/Space 部署后建议用「记账 App + React + Dexie」类需求跑通 Spec 五步；失败时查 `step` 字段与后端 `structured_invoke` 日志.
