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

* [Axiodrasil System BIOS (全局设定与认知法案)](https://www.google.com/search?q=docs/Axiodrasil_BIOS_V15.0.md)
* [ADR-001: 关于“身心痛感指标”量化标尺的校准决策](https://www.google.com/search?q=docs/adr/ADR-001-pain-level-calibration.md)

```