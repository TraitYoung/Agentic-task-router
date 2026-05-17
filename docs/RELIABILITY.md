# SpecForge 容错设计

## 目标

SpecForge 的 demo 不只展示 happy path。上线后需要能回答三个问题：服务是否活着、失败发生在哪一步、失败后用户还能不能继续使用核心能力。

## 边界情况处理

| 场景 | 当前处理 | 用户/运维可见信号 |
| --- | --- | --- |
| LLM 输出格式错误 | 各阶段输出进入 Pydantic v2 模型校验, 字段数量和文本长度会被限制; 校验失败会中断该轮并返回错误事件. | API 返回 `turn failed`, 后端日志带 `trace_id`, mode, input_len. |
| API 限流 | `RateLimitMiddleware` 对 chat 接口限制为 10 req/min, 其他接口 30 req/min, health 60 req/min. | 返回 HTTP 429 和 `Retry-After`. |
| Redis 不可用 | 会话缓存写入失败只记录 warning, 不阻断本轮生成; health 中 `redis.ok=false`. | 前端顶部黄色提示, `/api/v1/health` 显示 Redis 错误. |
| SQLite 写入失败 | 规格/issue 保存包在 try/except 中, 检索增强失败不会影响最终回复. | 后端 warning: `save to spec_store failed`. |
| SQLite FTS 查询语法错误 | FTS5 `MATCH` 遇到特殊字符会抛 `OperationalError`; 当前实现记录 warning 并回退到 `LIKE` 检索. | 后端 warning: `spec FTS search failed, falling back to LIKE`; 用户请求继续进入 LLM 流水线. |
| 单任务 token 超预算 | `context_budget.clip_text()` 对用户输入和阶段 JSON 摘要做最大长度裁剪. | Trace summary 保留 `_metrics.estimated_tokens`, README 截图展示总量. |
| SSE 中断 | 后端 stream 捕获异常并发送 `{type:"error"}` 事件; 前端保留已收到内容并显示错误. | 浏览器错误气泡和后端 exception 日志. |
| 缺少 API key | 启动时 warning; health 中 `env.has_qwen_key=false`; 真正调用 LLM 时失败. | Hugging Face Space logs 可见 `QWEN_API_KEY not set`, health 可提前发现. |

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
  "env": { "has_qwen_key": true, "has_redis_url": true }
}
```

## 日志策略

- 请求级日志: `trace_id`, method, path, status, duration_ms, client_ip.
- 流水线日志: profile, input length, retrieval hit, step duration, estimated tokens, memory snapshot.
- 存储日志: spec/issue 保存成功记录 profile 和 count; 保存失败只降级为 warning.

## 生产建议

- Hugging Face 免费 Space 可能冷启动, 第一次访问需要等待构建或唤醒.
- 当前后端健康检查地址: `https://ishowrelx5-specforge-api.hf.space/api/v1/health`.
- SQLite 在免费容器中不是强持久化方案; 正式生产应挂载磁盘或迁移 PostgreSQL.
- Redis 是增强项而不是硬依赖; Upstash Redis 可作为免费 demo 缓存层.
- 如果 LLM 调用超过 Vercel 函数时间, 前端只代理请求, 长耗时主要由 Hugging Face Space 后端承接.
