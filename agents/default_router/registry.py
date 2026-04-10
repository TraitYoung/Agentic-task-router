"""
默认路由后端热插拔（中性命名）：

- `AX_DEFAULT_ROUTER_BACKEND` 优先；
- 若未设置，回退到 `AX_CABINET_BACKEND`（兼容历史配置）；
- `legacy/default/graph` 使用内置执行器。
"""

from __future__ import annotations

import importlib
import os
from typing import TYPE_CHECKING, Callable, List, Tuple

if TYPE_CHECKING:
    from memory.session_cache import SessionCache
    from schemas.protocols import TaskIntent

DefaultRouterRunFn = Callable[
    [str, str, "SessionCache"],
    Tuple[str, "TaskIntent", List[dict], str],
]

_cached: DefaultRouterRunFn | None = None


def _backend_spec() -> str:
    preferred = (os.getenv("AX_DEFAULT_ROUTER_BACKEND") or "").strip()
    if preferred:
        return preferred
    return (os.getenv("AX_CABINET_BACKEND") or "legacy").strip()


def get_default_router_runner() -> DefaultRouterRunFn:
    global _cached
    if _cached is not None:
        return _cached

    spec = _backend_spec()
    if not spec or spec.lower() in ("legacy", "default", "graph"):
        from agents.default_router.runner import run_default_router_turn

        _cached = run_default_router_turn
        return _cached

    if ":" not in spec:
        raise ValueError(
            f"后端配置 {spec!r} 无效。使用 legacy/default/graph，或设为 "
            f"'package.module:callable_name'。"
        )

    mod_name, _, attr = spec.partition(":")
    mod_name, attr = mod_name.strip(), attr.strip()
    if not mod_name or not attr:
        raise ValueError(f"后端配置格式应为 package.module:callable，当前为 {spec!r}")

    mod = importlib.import_module(mod_name)
    fn = getattr(mod, attr)
    if not callable(fn):
        raise TypeError(f"{spec} 不是可调用对象")
    _cached = fn  # type: ignore[assignment]
    return _cached


def reset_default_router_runner_cache_for_tests() -> None:
    global _cached
    _cached = None
