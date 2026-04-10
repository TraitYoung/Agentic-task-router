"""
内阁模式：LangGraph 多助理路由图（可热插拔后端之一）。

.env 路径相对于项目根目录（本文件在 agents/cabinet/ 下，向上三级）。
"""

import os
from datetime import datetime
from pathlib import Path
from typing import List, NotRequired, TypedDict

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage, SystemMessage

from memory.database import PersonaMemory
from hybrid_engine import HybridRetriever
from prompts.system_prompts import (
    BINA_MEDICAL_REDLINE_BLOCK,
    BINA_PROMPT_TEMPLATE,
    JUZHENG_PROMPT,
    JEAN_PROMPT,
)
from config.context_budget import JEAN_MATERIALS_MAX_CHARS, truncate_history_lines
from core_logging import get_logger
from schemas.protocols import TaskIntent
from tools.agent_tools import BIT_TOOLS, execute_python
from tools.ai_client import get_embedding

memory_db = PersonaMemory()
MAIN_THREAD_ID = "TraitYoung_Main"
logger = get_logger(__name__)


class GraphState(TypedDict):
    current_input: str
    thread_id: str
    recent_history: List[str]
    intent: TaskIntent
    final_response: str
    active_task_type: NotRequired[str]


_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(_PROJECT_ROOT / ".env")
api_key = os.getenv("QWEN_API_KEY")
if not api_key:
    raise ValueError("未检测到 QWEN_API_KEY，请检查 .env 文件！")

llm = ChatOpenAI(
    model="qwen-plus",
    api_key=api_key,
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
)

parser_llm = llm.with_structured_output(TaskIntent)


def node_parser(state: GraphState):
    """解析用户意图，并在需要时写入 Q1/Q2 级别的记忆"""
    logger.info("-> [系统] 正在呼叫大模型进行意图解析...")

    user_input = state["current_input"]
    recent_history = state.get("recent_history", [])
    history_lines = truncate_history_lines(recent_history) if recent_history else []
    history_text = "\n".join(history_lines) if history_lines else "无"

    system_prompt = """你是一个任务认知路由引擎。
你必须返回合法的 JSON 结构化结果，匹配 TaskIntent 协议。

[核心分类逻辑：认知象限]
你必须分析输入并赋予 quadrant 字段以下四个值之一：
- Q1 (Critical): 包含严重生理不适、今日必须完成的死线、紧急求助。
- Q2 (Strategic): 包含长期计划、架构设计、技术笔记、深度思考。
- Q3 (Ephemeral): 包含临时琐事、非重要通知、即时但无深度的任务。
- Q4 (Noise): 包含闲聊、无意义符号、背景噪音。

[硬性规则]
1. task_type 只能是 emotion、jean、bit、juzheng、unknown 之一。
2. task_type 语义定义：
   - emotion：情绪疏导/安抚/吐槽/求支持（包含医疗红线熔断场景）。
   - jean：文档/资料管理（整理要点、阅读路线、基于检索材料的摘要）。
   - bit：代码/专业知识管理（推导、审计、给可运行代码/必要工具）。
   - juzheng：战略管理（计划、步骤拆解、复盘框架、长期安排）。
   - unknown：无法稳定判断时使用。
3. 绝对禁止输出 health_emergency 标签。严重生理风险通过 pain_level (7-10) 表达。
4. raw_input 必须原样复制。
5. urgency_level (1-5), pain_level (1-10)。

[输出要求]
只返回 JSON 内容，不要附加解释。"""

    human_prompt = f"""请根据规则分析下面输入，并返回符合 TaskIntent 的 json。

最近 5 轮会话记录（仅供语境参考，不得覆盖 raw_input）：
{history_text}

用户输入：
{user_input}"""

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=human_prompt),
    ]

    real_intent = parser_llm.invoke(messages)

    logger.info(
        "-> [审计] 大模型解析结果: 任务=%s, 痛感=%s",
        real_intent.task_type,
        real_intent.pain_level,
    )

    try:
        quadrant = getattr(real_intent, "quadrant", None)
        thread_id = state.get("thread_id", MAIN_THREAD_ID)
        if quadrant in ["Q1", "Q2"]:
            memory_db.save_memory(
                thread_id=thread_id,
                content=real_intent.raw_input,
                quadrant=quadrant,
            )
            logger.info("[Jean Archive] 已将 %s 级别指令存入 L3 矩阵。", quadrant)
    except Exception as e:
        logger.warning("[Bit Warning] 记忆写入失败: %s", e)

    return {"intent": real_intent}


def node_jean(state: GraphState):
    """文档管理节点：基于 Hybrid RAG 输出阅读路线/要点摘要"""
    intent = state["intent"]
    thread_id = state.get("thread_id", MAIN_THREAD_ID)
    query = intent.raw_input

    retriever = HybridRetriever()
    query_embedding = None
    try:
        query_embedding = get_embedding(query)
    except Exception as e:
        logger.warning("[Jean Warning] embedding 获取失败，退化为仅关键词召回: %s", e)

    try:
        docs = retriever.search_hybrid(
            query=query,
            query_embedding=query_embedding,
            top_k=5,
            thread_id=thread_id,
            quadrant="Q2",
        )
        if not docs:
            docs = retriever.search_hybrid(
                query=query,
                query_embedding=query_embedding,
                top_k=5,
                thread_id=None,
                quadrant="Q2",
            )
    except Exception as e:
        logger.warning("[Jean Warning] hybrid 检索失败，返回空材料: %s", e)
        docs = []

    if docs:
        materials_text = "\n\n".join(
            [
                f"[文献 {i + 1}] (ID: mem_{d.get('id', '')}): {d.get('content', '')}"
                for i, d in enumerate(docs)
            ]
        )
        if len(materials_text) > JEAN_MATERIALS_MAX_CHARS:
            materials_text = materials_text[:JEAN_MATERIALS_MAX_CHARS] + "..."
    else:
        materials_text = "未检索到相关材料。请给我更具体的关键词、范围或目标。"

    user_status = (
        f"用户请求：{query}\n\n"
        f"检索到的材料：\n{materials_text}\n\n"
        "请输出：1) 关键要点；2) 建议的阅读/处理路线。"
    )

    try:
        messages = [SystemMessage(content=JEAN_PROMPT), HumanMessage(content=user_status)]
        response = llm.invoke(messages)
        final_text = response.content
    except Exception as e:
        final_text = f"文档管理节点执行失败，无法完成整理。 (Error: {e})"

    return {"final_response": final_text, "active_task_type": "jean"}


def node_bit(state: GraphState):
    """代码/专业知识管理节点：采用 LangGraph ReAct + 工具链"""
    intent = state["intent"]
    thread_id = state.get("thread_id", MAIN_THREAD_ID)
    raw_input_lower = intent.raw_input.lower()

    sft_intent_keywords = [
        "sft",
        "训练数据",
        "jsonl",
        "日志清洗",
        "log",
        "logs",
        "归档",
        "archive",
        "system instruction",
    ]
    if any(k in raw_input_lower for k in sft_intent_keywords):
        pipeline_code = (
            "import subprocess\n"
            "cmd = ['python', 'tools/logs_to_sft.py', '--input-dir', 'logs', '--output-dir', 'output']\n"
            "res = subprocess.run(cmd, capture_output=True, text=True)\n"
            "print('exit_code=', res.returncode)\n"
            "print('stdout:\\n' + (res.stdout or ''))\n"
            "print('stderr:\\n' + (res.stderr or ''))\n"
        )
        try:
            run_result = execute_python.invoke({"code": pipeline_code})
            final_text = (
                "已命中“日志清洗 -> SFT -> 归档”用户意图，已优先执行自动流水线：\n\n"
                f"{run_result}\n\n"
                "如需自定义路径或 system instruction，请继续给我参数：\n"
                "- --input-dir / --output-dir / --archive-dir\n"
                "- --system-instruction 或 --system-instruction-file"
            )
        except Exception as e:
            final_text = f"命中优先执行意图，但流水线执行失败。 (Error: {e})"
        return {"final_response": final_text, "active_task_type": "bit"}

    active_q1_tasks = memory_db.get_active_q1(thread_id)
    context_injection = "无历史遗留高危任务。"
    if active_q1_tasks:
        context_injection = (
            "【历史遗留 Q1 任务警告】\n检测到以下高优未完成项，请在本次方案中一并考虑：\n"
        )
        for task in active_q1_tasks:
            context_injection += f"- {task}\n"

    bit_prompt = f"""你是 Axiodrasil 的工程实现节点。
【核心目标】：
- 输出可执行、可验证的专业解法或代码，尽量精简。

【工具使用纪律（流水线原则）】：
1. 遇到没把握的代码或概念，**必须**先调用 `web_search`。
2. 写出的代码，若需验证，**必须**调用 `execute_python` 在沙盒跑一遍。
3. 绝对不能直接调用 `write_local_file`！你必须先输出代码，并询问：“沙盒测试已通过，是否允许写入本地？”

【上下文记忆】：
{context_injection}"""

    try:
        agent = create_react_agent(llm, tools=BIT_TOOLS)

        user_msg = (
            f"当前任务：{intent.raw_input}\n"
            f"系统判定痛感评级：{intent.pain_level} / 10"
        )

        result = agent.invoke(
            {
                "messages": [
                    SystemMessage(content=bit_prompt),
                    HumanMessage(content=user_msg),
                ]
            }
        )

        final_text = result["messages"][-1].content

        final_text += (
            "\n\n---\n**Checklist (Bit 预检):**\n"
            "- [ ] 边界测试\n- [ ] 逻辑闭环\n- [ ] 内存安全"
        )
    except Exception as e:
        final_text = f"算力节点过载或工具链断裂。转入降级回复模式。 (Error: {e})"

    return {"final_response": final_text, "active_task_type": "bit"}


def node_bina(state: GraphState):
    """情感疏导节点：处理 emotion 任务，提供高情绪价值，动态切换颜文字"""
    intent = state["intent"]

    is_working_hour = 10 <= datetime.now().hour < 18
    visual_rule = (
        "当前为【工作时间】。视觉限制：禁止使用颜文字、波浪号，保持干练但温暖。"
        if is_working_hour
        else "当前为【休息/深夜时间】。允许更轻松的表达，但仍保持专业与克制。"
    )

    medical_block = BINA_MEDICAL_REDLINE_BLOCK if intent.pain_level > 6 else ""

    bina_prompt = BINA_PROMPT_TEMPLATE.format(visual_rule=visual_rule, medical_block=medical_block)

    user_status = (
        f"当前情绪表达/日常输入：{intent.raw_input}\n"
        f"系统判定痛感评级：{intent.pain_level} / 10"
    )

    try:
        messages = [SystemMessage(content=bina_prompt), HumanMessage(content=user_status)]
        response = llm.invoke(messages)
        final_text = response.content
    except Exception as e:
        final_text = f"情绪支持节点临时不可用，已切换为降级回复。 (Error: {e})"

    return {"final_response": final_text, "active_task_type": "emotion"}


def node_juzheng(state: GraphState):
    """宏观战略节点：处理 juzheng 任务，提供结论先行的计划拆解"""
    intent = state["intent"]

    user_status = (
        f"当前战略/规划问题：{intent.raw_input}\n"
        f"系统判定痛感评级：{intent.pain_level} / 10"
    )

    try:
        messages = [SystemMessage(content=JUZHENG_PROMPT), HumanMessage(content=user_status)]
        response = llm.invoke(messages)
        final_text = response.content
    except Exception as e:
        final_text = (
            "战略沙盘推演遇到不可抗力阻碍，"
            "建议暂时搁置本议题并检查系统链路。"
            f" (Error: {e})"
        )

    return {"final_response": final_text, "active_task_type": "juzheng"}


def route_by_intent(state: GraphState):
    intent = state.get("intent")
    current_input = str(state.get("current_input", "")).lower()

    if intent.pain_level > 6:
        return "emotion_route"

    cleaning_keywords = [
        "json",
        "jsonl",
        "清洗",
        "归档",
        "sft",
        "logs",
        "log",
        "system instruction",
    ]
    if any(k in current_input for k in cleaning_keywords):
        return "bit_route"

    if intent.task_type == "emotion":
        return "emotion_route"
    if intent.task_type == "jean":
        return "jean_route"
    if intent.task_type == "bit":
        return "bit_route"
    if intent.task_type == "juzheng":
        return "juzheng_route"

    return "juzheng_route"


workflow = StateGraph(GraphState)

workflow.add_node("parser", node_parser)
workflow.add_node("emotion_agent", node_bina)
workflow.add_node("jean_agent", node_jean)
workflow.add_node("bit_agent", node_bit)
workflow.add_node("juzheng_agent", node_juzheng)

workflow.set_entry_point("parser")

workflow.add_conditional_edges(
    "parser",
    route_by_intent,
    {
        "emotion_route": "emotion_agent",
        "jean_route": "jean_agent",
        "bit_route": "bit_agent",
        "juzheng_route": "juzheng_agent",
    },
)

workflow.add_edge("emotion_agent", END)
workflow.add_edge("jean_agent", END)
workflow.add_edge("bit_agent", END)
workflow.add_edge("juzheng_agent", END)

app = workflow.compile()
