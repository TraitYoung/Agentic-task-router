"""
内阁后端热插拔：通过环境变量切换实现，无需改 main 分支逻辑。

- `AX_CABINET_BACKEND` 未设置或 `legacy`：使用本包内 `run_cabinet_turn`（当前 LangGraph 内阁）。
- `AX_CABINET_BACKEND=my_pkg.my_module:my_callable`：动态导入可调用对象；
  必须与本包 `run_cabinet_turn` **相同签名**：
  `(text: str, session_id: str, session_cache: SessionCache) -> tuple[str, TaskIntent, list[dict], str]`

修改 `AX_CABINET_BACKEND` 后需重启 uvicorn。
"""

from __future__ import annotations

import importlib
import os
from typing import TYPE_CHECKING, Any, Callable, List, Tuple

if TYPE_CHECKING:
    from memory.session_cache import SessionCache
    from schemas.protocols import TaskIntent

CabinetRunFn = Callable[
    [str, str, "SessionCache"],
    Tuple[str, "TaskIntent", List[dict], str],
]

_cached: CabinetRunFn | None = None


def get_cabinet_runner() -> CabinetRunFn:
    global _cached
    if _cached is not None:
        return _cached

    spec = (os.getenv("AX_CABINET_BACKEND") or "legacy").strip()
    if not spec or spec.lower() in ("legacy", "default", "graph"):
        from agents.cabinet.runner import run_cabinet_turn

        _cached = run_cabinet_turn
        return _cached

    if ":" not in spec:
        raise ValueError(
            f"AX_CABINET_BACKEND={spec!r} 无效。使用 legacy，或设为 "
            f"'package.module:callable_name'（callable 签名须与 agents.cabinet.runner.run_cabinet_turn 一致）。"
        )

    mod_name, _, attr = spec.partition(":")
    mod_name, attr = mod_name.strip(), attr.strip()
    if not mod_name or not attr:
        raise ValueError(f"AX_CABINET_BACKEND 格式应为 package.module:callable，当前为 {spec!r}")

    mod = importlib.import_module(mod_name)
    fn = getattr(mod, attr)
    if not callable(fn):
        raise TypeError(f"{spec} 不是可调用对象")
    _cached = fn  # type: ignore[assignment]
    return _cached


def reset_cabinet_runner_cache_for_tests() -> None:
    """仅测试用：清空缓存以便切换 mock。"""
    global _cached
    _cached = None
