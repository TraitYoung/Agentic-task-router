"""
默认路由执行器：兼容别名层。
"""

from typing import TYPE_CHECKING, List, Tuple

from agents.cabinet.runner import run_cabinet_turn

if TYPE_CHECKING:
    from memory.session_cache import SessionCache
    from schemas.protocols import TaskIntent


def run_default_router_turn(
    text: str,
    session_id: str,
    session_cache: "SessionCache",
) -> Tuple[str, "TaskIntent", List[dict], str]:
    return run_cabinet_turn(text=text, session_id=session_id, session_cache=session_cache)
