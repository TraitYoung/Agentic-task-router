# Axiodrasil: Multi-Agent Task Router

[![Python 3.13](https://img.shields.io/badge/Python-3.13-blue.svg)](https://www.python.org/)
[![LangGraph](https://img.shields.io/badge/Orchestration-LangGraph-orange.svg)](https://github.com/langchain-ai/langgraph)
[![Pydantic](https://img.shields.io/badge/Protocol-Pydantic_V2-red.svg)](https://docs.pydantic.dev/)

> "War is over, life continues. We are family in the digital realm."

Axiodrasil 是一个基于 LangGraph 的多智能体任务路由与个人管理引擎。项目致力于在复杂任务场景中，通过状态机管理和结构化数据流，实现逻辑审计、策略规划与情绪支持的动态路由分发。

## 🛠️ 核心架构特性

* **多智能体动态路由 (Dynamic Routing)**: 基于 LangGraph 构建有向无环图 (DAG) 工作流，根据输入意图实现流量在 4 个核心 Agent 节点的精准分发。
* **Pydantic 协议强校验**: 引入 Pydantic 数据模型，强制大模型将自然语言输出为强类型格式（如 Task_Type, Pain_Level），以此作为路由流转的唯一依据，降低幻觉率。
* **状态机熔断机制 (Meltdown Protection)**: 内置量化状态监测引擎。当识别到高压阈值 (Pain Level > 6) 时，无视常规任务类型，自动阻断并触发医疗干预节点。
* **Prompt 漂移治理**: 通过系统级消息 (System Message) 显式注入评分量尺，有效修正大模型在意图解析时原生的“同理心泛滥”与打分漂移问题。

## 🚀 快速启动

1. 环境依赖配置:
   ```bash
   pip install langchain-openai langgraph pydantic python-dotenv

```

2. 环境变量挂载: 在根目录创建 `.env` 文件并填入 LLM API 密钥。
```env
QWEN_API_KEY="sk-xxxxxx"

```


3. 运行流转测试:
```bash
python test.py

```



## 📚 架构设计与设定文档 (Docs)

本系统的底层逻辑、Persona 设定机制与核心执行法案，已作为蓝图归档：

* [Axiodrasil System BIOS (架构蓝图与协议设定)](https://github.com/TraitYoung/Agentic-task-router/blob/main/docs/Axiodrasil_BIOS_V15.0.md)

## 🏗️ 路线图 (Roadmap)

* [x] 基于 LangGraph 的多智能体路由引擎 MVP
* [x] Pydantic 结构化输出与漂移治理
* [ ] 接入 ChromaDB 实现 L3 长期记忆的 RAG 挂载
* [ ] 自动化错误归因与 SOP 动态迭代闭环