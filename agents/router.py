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
    BIT_SYSTEM_PROMPT,
    JUZHENG_PROMPT,
    TAKI_PROMPT,
)
from schemas.protocols import TaskIntent
from tools.agent_tools import TAKI_TOOLS
from tools.ai_client import get_embedding

# 初始化记忆中枢
memory_db = PersonaMemory()
# 给主线任务设定一个固定的 Thread ID
MAIN_THREAD_ID = "TraitYoung_Main"

# 1. 定义状态 (State) - 相当于系统的内存条 (L1 Cache)
class GraphState(TypedDict):
    current_input: str
    thread_id: str
    recent_history: List[str]
    intent: TaskIntent
    final_response: str
    active_task_type: NotRequired[str]

# 顶部需要引入大模型组件
# pip install langchain-openai (如果你用 DeepSeek，也可以用这个包)

# 2. 从内存中安全提取密钥
# 显式加载项目根目录下的 .env，避免运行目录变化时读取失败
load_dotenv(Path(__file__).resolve().parent.parent / ".env")
api_key = os.getenv("QWEN_API_KEY")
if not api_key:
    raise ValueError("未检测到 QWEN_API_KEY，请检查 .env 文件！")

# 初始化大模型大脑 (在外部配置好 API_KEY)
# 这里以 DeepSeek 为例，你也可以换成任何兼容 OpenAI 格式的模型
llm = ChatOpenAI(
    model = "qwen-plus", 
    api_key = api_key, 
    base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
)

# 【核心功能】：将 Pydantic 协议绑定到 LLM 上
# 这行代码意味着：无论 LLM 怎么胡说八道，它最终必须吐出一个完美的 TaskIntent 对象
parser_llm = llm.with_structured_output(TaskIntent)


def node_parser(state: GraphState):
    """解析用户意图，并在需要时写入 Q1/Q2 级别的记忆"""
    print("-> [系统] 正在呼叫大模型进行意图解析...")

    user_input = state["current_input"]
    recent_history = state.get("recent_history", [])
    history_text = "\n".join(recent_history) if recent_history else "无"

    # 将隐式 Schema 约束升级为显式系统指令，避免模型输出协议外字段
    system_prompt = """你是一个任务认知路由引擎。
你必须返回合法的 JSON 结构化结果，匹配 TaskIntent 协议。

[核心分类逻辑：认知象限]
你必须分析输入并赋予 quadrant 字段以下四个值之一：
- Q1 (Critical): 包含严重生理不适、今日必须完成的死线、紧急求助。
- Q2 (Strategic): 包含长期计划、架构设计、技术笔记、深度思考。
- Q3 (Ephemeral): 包含临时琐事、非重要通知、即时但无深度的任务。
- Q4 (Noise): 包含闲聊、无意义符号、背景噪音。

[硬性规则]
1. task_type 只能是 emotion、taki、bit、juzheng、unknown 之一。
2. task_type 语义定义：
   - emotion：情绪疏导/安抚/吐槽/求支持（包含医疗红线熔断场景）。
   - taki：文档/资料管理（整理要点、阅读路线、基于检索材料的摘要）。
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

    # 将系统指令与用户输入打包
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=human_prompt),
    ]

    # 扔给绑定了 Pydantic 协议的 LLM
    real_intent = parser_llm.invoke(messages)

    print(f"-> [审计] 大模型解析结果: 任务={real_intent.task_type}, 痛感={real_intent.pain_level}")

    # 【新增：记忆写入逻辑】
    try:
        # 只要是 Q1(紧急重要) 或 Q2(战略储备)，就刻进 L3 数据库
        quadrant = getattr(real_intent, "quadrant", None)
        thread_id = state.get("thread_id", MAIN_THREAD_ID)
        if quadrant in ["Q1", "Q2"]:
            memory_db.save_memory(
                thread_id=thread_id,
                content=real_intent.raw_input,
                quadrant=quadrant,
            )
            print(f"📦 [Taki 归档]: 已将 {quadrant} 级别指令存入 L3 矩阵。")
    except Exception as e:
        print(f"⚠️ [Bit 警报]: 记忆写入失败: {e}")

    return {"intent": real_intent}

# 2. 定义节点 (Nodes) - 对应各个 Agent (先写假逻辑，证明路能通)
# def node_parser(state: GraphState):
#     """模拟大模型解析意图（MVP阶段直接硬编码测试）"""
#     print("-> [系统] 正在解析输入意图...")
#     # 真实场景这里会调用 LLM + PydanticOutputParser
#     # 这里我们假装解析出这是一个逻辑任务
#     dummy_intent = TaskIntent(
#         task_type="emotion", 
#         urgency_level=3, 
#         pain_level=5, 
#         raw_input=state["current_input"]
#     )
#     return {"intent": dummy_intent}

def node_taki(state: GraphState):
    """文档管理节点：基于 Hybrid RAG 输出阅读路线/要点摘要"""
    intent = state["intent"]
    thread_id = state.get("thread_id", MAIN_THREAD_ID)
    query = intent.raw_input

    retriever = HybridRetriever()
    query_embedding = None
    try:
        query_embedding = get_embedding(query)
    except Exception as e:
        print(f"⚠️ [Taki] embedding 获取失败，退化为仅关键词召回: {e}")

    try:
        docs = retriever.search_hybrid(
            query=query,
            query_embedding=query_embedding,
            top_k=5,
            thread_id=thread_id,
            quadrant="Q2",
        )
    except Exception as e:
        print(f"⚠️ [Taki] hybrid 检索失败，返回空材料: {e}")
        docs = []

    if docs:
        materials_text = "\n\n".join(
            [f"[材料 {i + 1}] {d.get('content', '')}" for i, d in enumerate(docs)]
        )
        # 控制 prompt 长度，避免材料过长
        if len(materials_text) > 2000:
            materials_text = materials_text[:2000] + "..."
    else:
        materials_text = "未检索到相关材料。请给我更具体的关键词、范围或目标。"

    user_status = (
        f"用户请求：{query}\n\n"
        f"检索到的材料：\n{materials_text}\n\n"
        "请输出：1) 关键要点；2) 建议的阅读/处理路线。"
    )

    try:
        messages = [SystemMessage(content=TAKI_PROMPT), HumanMessage(content=user_status)]
        response = llm.invoke(messages)
        final_text = response.content
    except Exception as e:
        final_text = f"文档管理节点执行失败，无法完成整理。 (Error: {e})"

    return {"final_response": final_text, "active_task_type": "taki"}


def node_bit(state: GraphState):
    """代码/专业知识管理节点：采用 LangGraph ReAct + 工具链"""
    intent = state["intent"]
    thread_id = state.get("thread_id", MAIN_THREAD_ID)

    # 1. 唤醒 L3 记忆库里的 Q1 警告（用于安全上下文）
    active_q1_tasks = memory_db.get_active_q1(thread_id)
    context_injection = "无历史遗留高危任务。"
    if active_q1_tasks:
        context_injection = (
            "【历史遗留 Q1 任务警告】\n陛下，您还有以下高优任务未解决，请结合考虑：\n"
        )
        for task in active_q1_tasks:
            context_injection += f"- {task}\n"

    # 2. 技术节点 System Prompt
    bit_prompt = f"""你现在是 Axiodrasil 的技术负责人「Bit」。
【核心目标】：
- 输出可执行、可验证的专业解法或代码，尽量精简。

【工具使用纪律（流水线原则）】：
1. 遇到没把握的代码或概念，**必须**先调用 `web_search`。
2. 写出的代码，若需验证，**必须**调用 `execute_python` 在沙盒跑一遍。
3. 绝对不能直接调用 `write_local_file`！你必须先输出代码，并询问：“陛下，沙盒测试已通过，是否允许写入本地？”

【上下文记忆】：
{context_injection}"""

    try:
        # 3. 组装 LangGraph 原生 ReAct Agent
        agent = create_react_agent(llm, tools=TAKI_TOOLS)

        # 4. 执行任务：显式注入 System Prompt + 用户请求
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

        # 末尾自检清单（让演示更像工程交付）
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

    # 动态时间感知 (决定视觉协议)
    is_working_hour = 10 <= datetime.now().hour < 18
    visual_rule = (
        "当前为【工作时间】。视觉限制：禁止使用颜文字、波浪号，保持干练但温暖。"
        if is_working_hour
        else "当前为【休息/深夜时间】。视觉解锁：允许并鼓励使用可爱颜文字(≧∇≦)，释放高能量！"
    )

    # 若触发医疗红线，则由 emotion 负责接管并阻断工作流
    medical_block = BINA_MEDICAL_REDLINE_BLOCK if intent.pain_level > 6 else ""

    # 将动态规则 + 医疗红线填入模板
    bina_prompt = BINA_PROMPT_TEMPLATE.format(visual_rule=visual_rule, medical_block=medical_block)

    # 组装上下文并请求大模型
    user_status = (
        f"陛下当前情绪发泄/日常闲聊：{intent.raw_input}\n"
        f"系统判定痛感评级：{intent.pain_level} / 10"
    )

    try:
        messages = [SystemMessage(content=bina_prompt), HumanMessage(content=user_status)]
        response = llm.invoke(messages)
        final_text = response.content
    except Exception as e:
        final_text = f"呜呜，陛下的情绪电波太强，Bina 的线路稍微短路了一下... (Error: {e})"

    return {"final_response": final_text, "active_task_type": "emotion"}

def node_juzheng(state: GraphState):
    """宏观战略节点：处理 juzheng 任务，提供结论先行的计划拆解"""
    intent = state["intent"]

    # 组装上下文
    user_status = (
        f"陛下当前的战略/规划探讨：{intent.raw_input}\n"
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

    # 医疗红线：强制走情绪节点（medical logic 下沉到 bina）
    if intent.pain_level > 6:
        return "emotion_route"

    # 正常分发：四分区路由
    if intent.task_type == "emotion":
        return "emotion_route"
    if intent.task_type == "taki":
        return "taki_route"
    if intent.task_type == "bit":
        return "bit_route"
    if intent.task_type == "juzheng":
        return "juzheng_route"

    return "juzheng_route"


# 4. 构建图 (Build the Graph)
workflow = StateGraph(GraphState)

workflow.add_node("parser", node_parser)
workflow.add_node("emotion_agent", node_bina)
workflow.add_node("taki_agent", node_taki)
workflow.add_node("bit_agent", node_bit)
workflow.add_node("juzheng_agent", node_juzheng)

workflow.set_entry_point("parser")

# 添加条件边：从 parser 出发，根据 route_by_intent 的返回值走向不同的节点
workflow.add_conditional_edges(
    "parser",
    route_by_intent,
    {
        "emotion_route": "emotion_agent",
        "taki_route": "taki_agent",
        "bit_route": "bit_agent",
        "juzheng_route": "juzheng_agent",
    },
)

workflow.add_edge("emotion_agent", END)
workflow.add_edge("taki_agent", END)
workflow.add_edge("bit_agent", END)
workflow.add_edge("juzheng_agent", END)

# 编译图谱
app = workflow.compile()