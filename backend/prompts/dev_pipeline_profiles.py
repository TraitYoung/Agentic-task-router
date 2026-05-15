"""开发流水线项目画像：按关键词检测项目类型，注入对应工程关注点。"""

from __future__ import annotations

from typing import TypedDict


class DevProfile(TypedDict):
    name: str
    trigger_keywords: list[str]
    prompt_injection: str
    output_focus: list[str]


WEB_APP_PROFILE: DevProfile = {
    "name": "web_app",
    "trigger_keywords": [
        "网页", "网站", "前端", "后台管理", "dashboard",
        "react", "vue", "next", "nuxt", "svelte",
        "tailwind", "bootstrap", "ant design", "mui",
        "spa", "ssr", "全栈", "fullstack", "h5",
    ],
    "prompt_injection": (
        "岗位偏好：Web 全栈应用。请优先考虑前后端分离、API 契约、组件复用、响应式布局。"
        "方案需覆盖：路由设计、状态管理策略、API 接口定义、部署方案（静态/SSR/Serverless）。"
        "注意 SEO 需求、首屏加载性能、浏览器兼容性。"
    ),
    "output_focus": [
        "前后端接口契约",
        "组件树与路由设计",
        "部署与构建方案",
        "浏览器性能与兼容性",
    ],
}

MOBILE_APP_PROFILE: DevProfile = {
    "name": "mobile_app",
    "trigger_keywords": [
        "app", "小程序", "移动端", "手机",
        "flutter", "react native", "uniapp", "taro",
        "ios", "android", "微信小程序", "支付宝小程序",
        "apk", "ipa", "应用商店",
    ],
    "prompt_injection": (
        "岗位偏好：移动应用开发。请优先考虑跨平台方案、离线可用性、推送通知、应用商店审核。"
        "方案需覆盖：导航结构（Tab/Stack/Drawer）、状态管理、本地存储、网络层设计。"
        "注意不同平台（iOS/Android/小程序）的差异与限制。"
    ),
    "output_focus": [
        "跨平台策略与平台差异",
        "导航与页面路由",
        "离线与本地数据",
        "发布与审核流程",
    ],
}

API_SERVICE_PROFILE: DevProfile = {
    "name": "api_service",
    "trigger_keywords": [
        "api", "接口", "后端服务", "微服务", "microservice",
        "rest", "graphql", "grpc", "webhook",
        "fastapi", "express", "gin", "spring", "django",
        "网关", "gateway", "中间件", "middleware",
    ],
    "prompt_injection": (
        "岗位偏好：后端 API 服务。请优先考虑接口契约、数据模型、认证鉴权、并发与扩展性。"
        "方案需覆盖：RESTful 设计/GraphQL schema、数据库选型与索引策略、缓存分层、限流与熔断。"
        "注意幂等性、向后兼容、错误码体系、结构化日志。"
    ),
    "output_focus": [
        "API 契约与数据模型",
        "认证与权限方案",
        "高并发与扩展性",
        "可观测性（日志/指标/追踪）",
    ],
}

DATA_PIPELINE_PROFILE: DevProfile = {
    "name": "data_pipeline",
    "trigger_keywords": [
        "数据", "爬虫", "etl", "分析", "报表",
        "pipeline", "数仓", "data warehouse", "spark",
        "flink", "kafka", "airflow", "dbt",
        "清洗", "聚合", "bi", "可视化", "统计",
    ],
    "prompt_injection": (
        "岗位偏好：数据处理管线。请优先考虑数据质量、幂等性、增量/全量策略、监控与告警。"
        "方案需覆盖：数据源与sink、schema 管理、错误处理与重试、调度策略。"
        "注意数据隐私、脱敏、保留策略。"
    ),
    "output_focus": [
        "数据流向与 schema",
        "增量与全量策略",
        "错误处理与数据质量",
        "调度、监控与告警",
    ],
}

GAME_CLIENT_TOOLS_PROFILE: DevProfile = {
    "name": "game_client_tools",
    "trigger_keywords": [
        "米哈游", "mihoyo", "游戏客户端", "客户端工具",
        "editor tool", "unity", "ue", "unreal",
        "asset pipeline", "资源管线", "热更新",
        "性能分析", "profiling", "打包工具",
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

GENERAL_PROFILE: DevProfile = {
    "name": "general_software_engineering",
    "trigger_keywords": [],
    "prompt_injection": "岗位偏好：通用软件工程。优先给出可交付、可验证、可演进的 MVP 路径。",
    "output_focus": ["需求清晰度", "迭代可交付性", "测试与发布质量"],
}

ALL_PROFILES: list[DevProfile] = [
    WEB_APP_PROFILE,
    MOBILE_APP_PROFILE,
    API_SERVICE_PROFILE,
    DATA_PIPELINE_PROFILE,
    GAME_CLIENT_TOOLS_PROFILE,
]


def detect_dev_profile(text: str) -> DevProfile:
    lower = text.lower()
    for profile in ALL_PROFILES:
        for kw in profile["trigger_keywords"]:
            if kw.lower() in lower:
                return profile
    return GENERAL_PROFILE
