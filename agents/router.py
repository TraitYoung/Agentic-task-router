import os
from pathlib import Path
from typing import TypedDict
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph
from schemas.protocols import TaskIntent
from langchain_core.messages import SystemMessage, HumanMessage

# 1. 定义状态 (State) - 相当于系统的内存条 (L1 Cache)
class GraphState(TypedDict):
    current_input: str
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

# 初始化你的大模型大脑 (在外部配置好 API_KEY)
# 这里以 DeepSeek 为例，你也可以换成任何兼容 OpenAI 格式的模型
llm = ChatOpenAI(
    model = "qwen-plus", 
    api_key = api_key, 
    base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
)

# 【核心魔法】：将 Pydantic 协议绑定到 LLM 上
# 这行代码意味着：无论 LLM 怎么胡说八道，它最终必须吐出一个完美的 TaskIntent 对象
parser_llm = llm.with_structured_output(TaskIntent)

def node_parser(state: GraphState):
    print("-> [系统] 正在呼叫大模型进行意图解析...")
    
    user_input = state["current_input"]
    
    # 将隐式 Schema 约束升级为显式系统指令，避免模型输出协议外字段
    system_prompt = """你是一个系统路由引擎。
你必须返回合法的 json 结构化结果，并且只能匹配 TaskIntent。

硬性规则：
1. task_type 只能是 logic、emotion、strategy、unknown 四个值之一。
2. 绝对禁止输出 health_emergency 或任何其他新标签。
3. 如果用户出现严重生理危险信号，仍然不要新建 task_type；只需要把 pain_level 提高到 7-10，由后续路由触发 medical_route。
4. 必须包含这四个字段：task_type、urgency_level、pain_level、raw_input。
5. raw_input 必须原样复制用户输入，不允许省略。
6. urgency_level 只能是 1 到 5 的整数。
7. pain_level 只能是 1 到 10 的整数。

痛感打分规则：
- 1-3：正常状态，或轻微脑力疲劳。
- 4-6：中度疲劳、情绪见底、抱怨、想哭、受挫，但没有严重躯体化症状。
- 7-10：只有明确提到严重生理反应，例如心脏狂跳、手抖、极度疼痛、呼吸困难、濒临昏厥等，才能打到这个区间。

输出要求：
- 只返回 json 对应的结构化内容，不要附加解释。"""

    human_prompt = f"""请根据规则分析下面输入，并返回符合 TaskIntent 的 json。

用户输入：
{user_input}"""

    # 将系统指令与用户输入打包
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=human_prompt)
    ]
    
    # 扔给绑定了 Pydantic 协议的 LLM
    real_intent = parser_llm.invoke(messages)
    
    print(f"-> [审计] 大模型解析结果: 任务={real_intent.task_type}, 痛感={real_intent.pain_level}")
    
    return {"intent": real_intent}

# 2. 定义节点 (Nodes) - 对应你的各个 Agent (先写假逻辑，证明路能通)
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
    """逻辑审计 Agent"""
    return {"final_response": "[Taki/Bit]: Logic initialized. 正在进行代码/代数推演。"}

def node_bina(state: GraphState):
    """情绪支持 Agent"""
    return {"final_response": "[Bina]: 正在提供情绪价值与能量补给。"}

def node_chizheng(state: GraphState):
    """策略规划 Agent"""
    return {"final_response": "[Chizheng]: 正在进行宏观战略拆解。"}

def node_qianjin(state: GraphState):
    """医疗熔断 Agent"""
    return {"final_response": "[Qianjin]: 监测到痛感超标，强制执行休息指令。"}

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