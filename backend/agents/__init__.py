"""Multi-Agent 协作层

架构：
  step_agents  — 7 个独立 Agent，每个有独立 system prompt + 模型路由 + 结构化输出 schema
  orchestrator — 负责编排 Agent 执行顺序、传递中间结果、收集 trace

流水线（正向 spec 模式）：
  Discovery Agent → Sprint Agent → Implementation Agent
    → Delivery Agent → Test Code Agent → Merge Agent

流水线（逆向 review 模式）：
  Reverse Engineer Agent（单步，从代码反推需求与问题）

每个 Agent 可以通过环境变量 LLM_{STEP}_MODEL 指定不同模型（model routing），
实现"简单步骤用小模型省钱，复杂推理步骤用大模型"的分级策略。
"""
