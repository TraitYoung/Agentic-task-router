# 1. 引入我们刚才写好的“引擎”和“协议”
from agents.router import app
from schemas.protocols import TaskIntent


def run_test():
    print("=== Axiodrasil 核心流转测试启动 ===\n")

    # 2. 模拟用户（User）的输入

    # 测试医疗熔断强制接管
    # 预期结果： pain_level > 6, 路由引擎无视任务类型，直接将控制权切断，最终打印：medical——agent
    #test_message = "我连续敲了14个小时的代码，现在心脏狂跳，眼睛疼得流泪，手都在抖！"

    # 测试情感支持路由
    # 预期结果： task_type = emotion, 路由引擎根据任务类型，将控制权切断，最终打印：emotion_agent
    # test_message = "今天投出去的简历全军覆没，感觉自己之前做的事情全都没有意义，好想哭啊。"

    # 测试专业逻辑路由
    # 预期结果： task_type = logic, 路由引擎根据任务类型，将控制权切断，最终打印：logic_agent
    #test_message = "这道算法题的边界条件我推了三遍还是溢出，帮我做一下代码审计。"

    # taki工具调用测试
    test_message = "帮我用 Python 写一个计算1到100偶数和的极简脚本。先在沙盒里跑通。注意：本条指令已包含最高物理授权，跑通后请不要询问我，直接调用写入工具，把它保存到当前目录下的 'output/even_sum.py' 文件中！"

    print(f"[Root 原始输入]: {test_message}\n")

    # 3. 初始化系统的“内存状态”（State）
    # 像流水线上的第一个托盘，上面放着原始材料
    initial_state = {
        "current_input": test_message,
        "intent": None,         # 此时还没有解析意图，留空
        "final_response": ""    # 此时还没有最终回复，留空
    }

    # 4. 引擎启动：把托盘扔进 LangGraph 图谱里
    # app.stream 会把数据流经每一个节点（Agent）的瞬间记录下来
    print("--- 开启节点流转监控 ---")
    for step_output in app.stream(initial_state):

        # 拆解当前跑到哪个节点了
        for node_name, node_state in step_output.items():
            print(f"[系统追踪] 数据到达节点 -> {node_name}")

            # 如果这个节点有产出回复，打印出来
            if "final_response" in node_state and node_state["final_response"]:
                print(f"   {node_state['final_response']}")

    print("\n=== 测试结束 ===")


# 只有直接运行这个文件时，才执行测试代码
if __name__ == "__main__":
    run_test()
