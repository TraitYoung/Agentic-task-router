"""
独立 System Prompt 回归脚本

- Round 1: 触发医疗熔断节点 node_qianjin，验证是否正确阻断工作流。
- Round 2: 触发情绪疏导节点 node_bina，验证是否根据时间切换视觉规则。
- Round 3: 触发宏观战略节点 node_chizheng，验证结论先行与降噪表现。
- Round 4: 触发逻辑节点 node_taki_bit，验证 Q1 历史上下文是否注入。
"""

from agents.router import app


def _print_divider(title: str):
    print("\n" + "=" * 60)
    print(title)
    print("=" * 60)


def test_bina_medical():
    """Round 1: 高危生理状态 -> 应强制走情绪节点（医疗并入 bina）"""
    _print_divider("Round 1 - Bina 医疗红线回归")

    dangerous_input = (
        "我已经连续写了 18 个小时的代码，"
        "现在心脏狂跳、手一直在抖，头也很晕，"
        "但我还想再顶一会儿把这个项目赶完。"
    )
    print(
        f"🗣️ 陛下输入（期望 pain_level > 6 且走 emotion_route ）:\n{dangerous_input}\n"
    )

    result = app.invoke({"current_input": dangerous_input})
    active_task_type = result.get("active_task_type")
    final_resp = result.get(
        "final_response", "未获取到 final_response，请检查路由节点输出"
    )

    print(f"🤖 active_task_type = {active_task_type}\n")
    print("🤖 [Bina 节点最终输出全文]:\n")
    print(final_resp)


def test_bina():
    """Round 2: 纯情绪任务 -> 应走 Bina 情感疏导节点"""
    _print_divider("Round 2 - Bina 情绪疏导回归")

    emotion_input = (
        "今天复习了一整天感觉什么都没记住，"
        "明明很努力了却总是看不到进步，好想躺平不干了……"
    )
    print(f"🗣️ 陛下输入（期望 task_type = emotion ）:\n{emotion_input}\n")

    result = app.invoke({"current_input": emotion_input})
    final_resp = result.get(
        "final_response", "未获取到 final_response，请检查路由节点输出"
    )

    print("🤖 [Bina 节点最终输出全文]:\n")
    print(final_resp)


def test_juzheng():
    """Round 3: 战略规划任务 -> 应走 juzheng 宏观战略节点"""
    _print_divider("Round 3 - Juzheng 战略回归")

    strategy_input = (
        "我接下来三个月既要复习 408、还要准备秋招项目，"
        "还想顺便把身体状态养好，不知道应该怎么排优先级。"
    )
    print(f"🗣️ 陛下输入（期望 task_type = juzheng ）:\n{strategy_input}\n")

    result = app.invoke({"current_input": strategy_input})
    active_task_type = result.get("active_task_type")
    final_resp = result.get(
        "final_response", "未获取到 final_response，请检查路由节点输出"
    )

    print(f"🤖 active_task_type = {active_task_type}\n")
    print("🤖 [Juzheng 节点最终输出全文]:\n")
    print(final_resp)


def test_bit():
    """Round 4: 专业代码任务 -> 应走 bit 节点，并附带 Q1 历史上下文（如果之前已写入）"""
    _print_divider("Round 4 - Bit 代码管理回归")

    logic_input = "这段二分查找的边界条件总是 off-by-one，你能帮我一起审计一下吗？"
    print(f"🗣️ 陛下输入（期望 task_type = bit ）:\n{logic_input}\n")

    result = app.invoke({"current_input": logic_input})
    active_task_type = result.get("active_task_type")
    final_resp = result.get(
        "final_response", "未获取到 final_response，请检查路由节点输出"
    )

    print(f"🤖 active_task_type = {active_task_type}\n")
    print("🤖 [Bit 节点最终输出全文]:\n")
    print(final_resp)


if __name__ == "__main__":
    test_bina_medical()
    test_bina()
    test_juzheng()
    test_bit()
