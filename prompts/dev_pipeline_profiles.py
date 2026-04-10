"""开发流水线岗位画像（A 方向）：按关键词注入特定工程关注点。"""

from __future__ import annotations

from typing import TypedDict


class DevProfile(TypedDict):
    name: str
    trigger_keywords: list[str]
    prompt_injection: str
    output_focus: list[str]


GAME_CLIENT_TOOLS_PROFILE: DevProfile = {
    "name": "game_client_tools",
    "trigger_keywords": [
        "米哈游",
        "mihoyo",
        "游戏客户端",
        "客户端工具",
        "editor tool",
        "unity",
        "ue",
        "unreal",
        "asset pipeline",
        "资源管线",
        "热更新",
        "性能分析",
        "profiling",
        "打包工具",
    ],
    "prompt_injection": (
        "岗位偏好：游戏客户端工具开发。请优先考虑开发者体验、工具稳定性与性能。"
        "方案里要覆盖：资源导入/校验流程、批处理能力、日志与可观测性、失败回滚、CI 集成。"
        "如果涉及 Unity/UE，指出编辑器脚本与运行时代码的边界。"
    ),
    "output_focus": [
        "Tooling UX 与批处理效率",
        "资源管线稳定性与错误恢复",
        "性能开销（编辑器侧/运行时）",
        "工程集成（CI、版本管理、日志）",
    ],
}


DEFAULT_PROFILE: DevProfile = {
    "name": "general_software_engineering",
    "trigger_keywords": [],
    "prompt_injection": "岗位偏好：通用软件工程。优先给出可交付、可验证、可演进的 MVP 路径。",
    "output_focus": ["需求清晰度", "迭代可交付性", "测试与发布质量"],
}


def detect_dev_profile(text: str) -> DevProfile:
    lower = text.lower()
    for kw in GAME_CLIENT_TOOLS_PROFILE["trigger_keywords"]:
        if kw.lower() in lower:
            return GAME_CLIENT_TOOLS_PROFILE
    return DEFAULT_PROFILE

