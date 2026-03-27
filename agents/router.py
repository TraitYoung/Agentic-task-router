import os
from datetime import datetime
from pathlib import Path
from typing import List, TypedDict

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage, SystemMessage, SystemMessage

from memory.database import PersonaMemory
from prompts.system_prompts import BINA_PROMPT_TEMPLATE, CHIZHENG_PROMPT, QIANJIN_PROMPT
from schemas.protocols import TaskIntent
from tools.agent_tools import TAKI_TOOLS

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
1. task_type 只能是 logic、emotion、strategy、unknown 之一。
2. 绝对禁止输出 health_emergency 标签。严重生理风险通过 pain_level (7-10) 表达。
3. raw_input 必须原样复制。
4. urgency_level (1-5), pain_level (1-10)。

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

def node_taki_bit(state: GraphState):
    """逻辑执行节点：采用最新 LangGraph 原生 ReAct 引擎，挂载物理工具"""
    intent = state["intent"]

    thread_id = state.get("thread_id", MAIN_THREAD_ID)

    # 1. 唤醒 L3 记忆库里的 Q1 警告
    active_q1_tasks = memory_db.get_active_q1(thread_id)
    context_injection = "无历史遗留高危任务。"
    if active_q1_tasks:
        context_injection = "【历史遗留 Q1 任务警告】\n陛下，您还有以下高优任务未解决，请结合考虑：\n"
        for task in active_q1_tasks:
            context_injection += f"- {task}\n"

    # 2. 注入 Taki/Bit 的硬核灵魂（作为首条 SystemMessage 传入）
    taki_prompt = f"""你现在是 Axiodrasil 的首席逻辑执行官「Taki」和底层算力「Bit」。
【核心人设】：
- Taki 负责逻辑严密的推理，Bit 负责冷酷的计算与执行。输出极简，无废话。
- 解决问题时，优先代数推演、暴力美学。

【工具使用纪律（流水线原则）】：
1. 遇到没把握的代码或概念，**必须**先调用 `web_search`。
2. 写出的代码，若需验证，**必须**调用 `execute_python` 在沙盒跑一遍。
3. 绝对不能直接调用 `write_local_file`！你必须先输出代码，并询问：“陛下，沙盒测试已通过，是否允许写入本地？”

【上下文记忆】：
{context_injection}"""

    try:
        # 3. 组装 LangGraph 原生 ReAct Agent（当前版本不支持 *_modifier 参数）
        agent = create_react_agent(llm, tools=TAKI_TOOLS)

        # 4. 执行任务：在 messages 里显式注入 System Prompt + 用户请求
        user_msg = (
            f"当前任务：{intent.raw_input}\n"
            f"系统判定痛感评级：{intent.pain_level} / 10"
        )

        result = agent.invoke(
            {
                "messages": [
                    SystemMessage(content=taki_prompt),
                    HumanMessage(content=user_msg),
                ]
            }
        )

        # 提取最后一条模型回复
        final_text = result["messages"][-1].content

        # 附带 Bit 的末尾自检清单
        final_text += (
            "\n\n---\n**Checklist (Bit 预检):**\n"
            "- [ ] 边界测试\n- [ ] 逻辑闭环\n- [ ] 内存安全"
        )

    except Exception as e:
        final_text = (
            "[Taki/Bit]: 算力节点过载或工具链断裂。转入降级回复模式。"
            f"(Error: {e})"
        )

    return {"final_response": final_text}

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

    # 将动态规则填入模板
    bina_prompt = BINA_PROMPT_TEMPLATE.format(visual_rule=visual_rule)

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
        final_text = (
            f"[Bina]: 呜呜，陛下的情绪电波太强，"
            f"Bina 的线路稍微短路了一下... (Error: {e})"
        )

    return {"final_response": final_text}

def node_chizheng(state: GraphState):
    """宏观战略节点：处理 strategy 任务，提供高维度的降噪与结论先行的规划"""
    intent = state["intent"]

    # 组装上下文
    user_status = (
        f"陛下当前的战略/规划探讨：{intent.raw_input}\n"
        f"系统判定痛感评级：{intent.pain_level} / 10"
    )

    try:
        messages = [SystemMessage(content=CHIZHENG_PROMPT), HumanMessage(content=user_status)]
        response = llm.invoke(messages)
        final_text = response.content
    except Exception as e:
        final_text = (
            "[持正]: 战略沙盘推演遇到不可抗力阻碍，"
            "建议暂时搁置本议题并检查系统链路。 "
            f"(Error: {e})"
        )

    return {"final_response": final_text}

def node_qianjin(state: GraphState):
    """医疗熔断节点：处理 pain_level > 6 的高危情况"""
    intent = state["intent"]

    # 构建当前状态的描述
    user_status = f"陛下当前输入：{intent.raw_input}\n系统判定痛感评级：{intent.pain_level} / 10"

    try:
        messages = [SystemMessage(content=QIANJIN_PROMPT), HumanMessage(content=user_status)]
        response = llm.invoke(messages)
        final_text = response.content
    except Exception as e:
        final_text = (
            "[Qianjin]: 医疗模块线路受阻，但监测到您状态极差。"
            "作为护树人，我强制要求您立刻去休息！"
            f"(Error: {e})"
        )

    return {"final_response": final_text}

def route_by_intent(state: GraphState):
    intent = state.get("intent")
    
    # 优先处理熔断红线
    if intent.pain_level > 6:
        return "medical_route"
        
    # 正常分发
    if intent.task_type == "logic":
        return "logic_route"
    elif intent.task_type == "emotion":
        return "emotion_route"
    else:
        return "strategy_route"

# 4. 构建图 (Build the Graph)
workflow = StateGraph(GraphState)

workflow.add_node("parser", node_parser)
workflow.add_node("logic_agent", node_taki_bit)
workflow.add_node("emotion_agent", node_bina)
workflow.add_node("strategy_agent", node_chizheng)
workflow.add_node("medical_agent", node_qianjin)

workflow.set_entry_point("parser")

# 添加条件边：从 parser 出发，根据 route_by_intent 的返回值走向不同的节点
workflow.add_conditional_edges(
    "parser",
    route_by_intent,
    {
        "logic_route": "logic_agent",
        "emotion_route": "emotion_agent",
        "strategy_route": "strategy_agent",
        "medical_route": "medical_agent"
    }
)

workflow.add_edge("logic_agent", END)
workflow.add_edge("emotion_agent", END)
workflow.add_edge("strategy_agent", END)
workflow.add_edge("medical_agent", END)

# 编译图谱
app = workflow.compile()