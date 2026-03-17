import os

from langchain_core.tools import tool
from langchain_experimental.utilities import PythonREPL


@tool
def web_search(query: str) -> str:
    """当遇到未知的技术问题、报错信息或需要最新文档时，使用此工具进行联网搜索。"""
    # 工业实战中通常接 Tavily 或 DuckDuckGo
    # 这里先给个简单的模拟，后续可以替换为真实的 API 实现
    return f"[模拟联网搜索结果] 针对 '{query}' 的最优解是：使用标准库或查阅官方文档。"


@tool
def execute_python(code: str) -> str:
    """在沙盒中执行一段 Python 代码并返回终端输出结果。用于验证代码是否能跑通。"""
    repl = PythonREPL()
    try:
        result = repl.run(code)
        return f"执行成功，输出结果:\n{result}"
    except Exception as e:
        return f"执行失败，报错信息:\n{e}"


@tool
def write_local_file(file_path: str, content: str) -> str:
    """将代码或文本写入本地绝对路径或相对路径。调用前必须确保陛下已授权。"""
    try:
        # 安全限制：只能在当前工作区目录下写入文件
        base_dir = os.path.abspath(".")
        target_path = os.path.abspath(file_path)

        if not target_path.startswith(base_dir):
            return "写入失败：安全策略限制，只能在当前工作区目录下写入文件。"

        os.makedirs(os.path.dirname(target_path), exist_ok=True)

        with open(target_path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"成功：内容已物理写入文件 {target_path}"
    except Exception as e:
        return f"写入失败: {e}"


# 导出一个工具列表，方便后续绑定给 Taki
TAKI_TOOLS = [web_search, execute_python, write_local_file]

