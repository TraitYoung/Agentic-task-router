# test_memory.py
from agents.router import MAIN_THREAD_ID, app, memory_db


def _print_header():
    print("=" * 60)
    print("🧠 Axiodrasil L3 认知记忆矩阵 - 连通性回归测试")
    print("=" * 60)


def _print_divider(title: str):
    print("\n" + "-" * 60)
    print(title)
    print("-" * 60)


def run_memory_test():
    """
    手工回归脚本：
    1. Round 1 注入一条 Q1 级别的高危指令，观察是否写入 SQLite。
    2. Round 2 再发起一条普通逻辑任务，观察 Taki 是否带出历史 Q1 上下文。
    """
    _print_header()

    # ==========================================
    # Round 1: 触发 Q1 记忆写入
    # ==========================================
    _print_divider("[Round 1] 写入 Q1 记忆（预期：插入 L3 数据库）")
    input_1 = "我手腕的腱鞘炎又犯了，痛感大概有6级，但今晚12点前必须把第一阶段代码提交上去！"
    print(f"🗣️ 陛下输入（期望被判定为 Q1）:\n{input_1}\n")

    app.invoke({"current_input": input_1})

    # 验证数据库物理写入情况
    q1_tasks = memory_db.get_active_q1(MAIN_THREAD_ID)
    print("📦 L3 / memory_matrix 当前未完成的 Q1 记录：")
    if not q1_tasks:
        print("   （空）❌ 未检测到 Q1 记忆，请检查 parser 或 quadrant 判定。")
    else:
        for idx, task in enumerate(q1_tasks, start=1):
            print(f"   [{idx}] {task}")
        print(f"\n✅ 实际结果：成功写入 {len(q1_tasks)} 条 Q1 记忆。")

    # ==========================================
    # Round 2: 测试历史记忆跨会话唤醒
    # ==========================================
    _print_divider("[Round 2] 跨回合唤醒 Q1（预期：Taki 前置 Q1 警告）")
    input_2 = "帮我随便写一个 Python 的冒泡排序吧。"
    print(f"🗣️ 陛下输入（普通逻辑任务）:\n{input_2}\n")

    # 再次调用 app，模拟新的对话回合
    result_2 = app.invoke({"current_input": input_2})
    final_resp = result_2.get(
        "final_response", "未获取到 final_response，请检查路由节点输出"
    )

    print("🤖 [Taki 节点最终输出全文]:\n")
    print(final_resp)

    # 简单可视化判断：是否带出了 Q1 提醒
    print("\n🧾 回归小结：")
    if "历史遗留 Q1 任务警告" in final_resp:
        print("   ✅ 检测到『历史遗留 Q1 任务警告』前缀，跨回合记忆唤醒正常。")
    else:
        print("   ⚠️ 未检测到 Q1 警告前缀，请检查 node_taki_bit 是否正确注入上下文。")


if __name__ == "__main__":
    run_memory_test()
