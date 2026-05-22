"""Chat turn orchestration independent of HTTP route handling."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

from schemas.protocols import TaskIntent
from schemas.trace import TraceStep
from services.pipeline_memory import save_pipeline_memory
from services.retrieval_context import build_retrieval_context

Mode = Literal["spec", "review"]

logger = logging.getLogger("specforge.chat_turns")


@dataclass(frozen=True)
class ChatTurnResult:
    reply: str
    intent: TaskIntent
    trace_raw: list[dict[str, Any]]
    mode: Mode
    artifact_md: str
    artifact_path: str
    artifact_filename: str


class ChatTurnRunner:
    def __init__(
        self,
        *,
        store_factory: Callable[[], Any],
        session_cache: Any,
        resolve_llm: Callable[[str, Any], Any],
        run_spec: Callable[..., Any],
        run_review: Callable[..., Any],
        run_spec_stream: Callable[..., Any],
        run_review_stream: Callable[..., Any],
    ) -> None:
        self._store_factory = store_factory
        self._session_cache = session_cache
        self._resolve_llm = resolve_llm
        self._run_spec = run_spec
        self._run_review = run_review
        self._run_spec_stream = run_spec_stream
        self._run_review_stream = run_review_stream

    def _step_id(self, mode: Mode) -> str:
        return "reverse_engineer" if mode == "review" else "discovery"

    def _append_turn(self, *, session_id: str, user_text: str, assistant_text: str) -> None:
        try:
            self._session_cache.append_turn(
                session_id=session_id,
                user_text=user_text,
                assistant_text=assistant_text,
            )
        except Exception as exc:
            logger.warning("Redis append_turn failed: %s", exc)

    def execute(self, mode: Mode, text: str, session_id: str) -> ChatTurnResult:
        store = self._store_factory()
        retrieval_context = build_retrieval_context(store, mode=mode, text=text)
        llm = self._resolve_llm(self._step_id(mode), None)
        pipeline = (
            self._run_review(text, llm, retrieval_context=retrieval_context)
            if mode == "review"
            else self._run_spec(text, llm, retrieval_context=retrieval_context)
        )

        trace_raw = pipeline.steps
        save_pipeline_memory(store, mode=mode, trace_raw=trace_raw, user_text=text)
        self._append_turn(session_id=session_id, user_text=text, assistant_text=pipeline.summary)

        return ChatTurnResult(
            reply=pipeline.summary,
            intent=TaskIntent(task_type="dev_pipeline", urgency_level=2, pain_level=1, raw_input=text.strip()[:200] or ".", quadrant="Q4"),
            trace_raw=trace_raw,
            mode=mode,
            artifact_md=pipeline.artifact_md,
            artifact_path=pipeline.artifact_path,
            artifact_filename=pipeline.artifact_filename,
        )

    async def execute_stream(self, mode: Mode, text: str, session_id: str):
        store = self._store_factory()
        retrieval_context = build_retrieval_context(store, mode=mode, text=text)
        event_queue: asyncio.Queue = asyncio.Queue(maxsize=256)
        loop = asyncio.get_running_loop()

        def _run_sync():
            llm = self._resolve_llm(self._step_id(mode), None)
            if mode == "review":
                return self._run_review_stream(
                    text, llm, retrieval_context=retrieval_context, event_queue=event_queue
                )
            return self._run_spec_stream(
                text, llm, retrieval_context=retrieval_context, event_queue=event_queue
            )

        future = loop.run_in_executor(None, _run_sync)

        while True:
            try:
                event = await asyncio.wait_for(event_queue.get(), timeout=0.1)
                yield event
            except asyncio.TimeoutError:
                if future.done():
                    while not event_queue.empty():
                        try:
                            yield event_queue.get_nowait()
                        except asyncio.QueueEmpty:
                            break
                    break

        pipeline = future.result()
        trace_raw = pipeline.steps
        save_pipeline_memory(store, mode=mode, trace_raw=trace_raw, user_text=text)
        self._append_turn(session_id=session_id, user_text=text, assistant_text=pipeline.summary)

        trace_payload = [TraceStep.model_validate(step).model_dump() for step in trace_raw]
        intent = TaskIntent(task_type="dev_pipeline", urgency_level=2, pain_level=1, raw_input=text.strip()[:200] or ".", quadrant="Q4")

        yield {
            "type": "artifact",
            "format": "markdown",
            "filename": pipeline.artifact_filename,
            "file_path": pipeline.artifact_path,
            "content": pipeline.artifact_md,
        }
        yield {"type": "reply", "content": pipeline.summary}
        yield {
            "type": "meta",
            "session_id": session_id,
            "intent": intent.model_dump(),
            "trace_id": "",
            "trace": trace_payload,
            "mode": mode,
        }
        yield {"type": "done"}
