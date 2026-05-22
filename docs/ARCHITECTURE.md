# SpecForge Architecture

SpecForge is a FastAPI + Next.js application that turns rough product ideas or pasted code into structured software engineering artifacts. The backend owns LLM orchestration, structured validation, trace generation, memory retrieval, and artifact persistence. The frontend provides the chat UI and proxies browser requests to FastAPI through Next.js route handlers.

## Core Workflows

| Mode | Input | Output | Main backend path |
| --- | --- | --- | --- |
| Spec | Product idea or requirement | `SPEC.md` implementation pack, summary, trace | `services/chat_turns.py` -> `agents/dev_pipeline/orchestrator.py` |
| Review | Code snippet | `REVIEW.md` review pack, issues, improvement plan | `services/chat_turns.py` -> `agents/dev_pipeline/orchestrator.py` |

## Backend Boundaries

- `main.py`: thin FastAPI layer for HTTP models, routes, response headers, health checks, and exception mapping.
- `services/retrieval_context.py`: builds RAG-style context from previous specs or frequent review issues.
- `services/pipeline_memory.py`: persists useful pipeline outputs back into SQLite memory.
- `services/chat_turns.py`: coordinates one chat turn across retrieval, LLM selection, pipeline execution, memory writes, Redis session history, and stream finalization.
- `agents/dev_pipeline/orchestrator.py`: runs the step-by-step engineering workflow and emits trace/status data.
- `schemas/`: Pydantic contracts for pipeline outputs, artifacts, traces, and API-facing data.

## Data Flow

1. The browser calls a Next.js API route under `frontend/app/api`.
2. Next.js forwards the request to FastAPI, preserving `x-session-id`, optional `x-api-key`, and trace headers.
3. FastAPI validates the request and delegates the turn to `ChatTurnRunner`.
4. The service layer builds retrieval context, resolves the step LLM, runs the selected pipeline, and saves memory.
5. The route returns either JSON (`/api/v1/chat`) or SSE events (`/api/v1/chat/stream`) with artifact, reply, meta, and done messages.

## Persistence And Observability

- Redis stores recent chat turns for session history and export.
- SQLite FTS5 stores generated specs and recurring review issues for lightweight retrieval.
- Each pipeline step writes trace data with step name, duration, summary, estimated token count, and memory usage.
- Prometheus metrics are exposed at `/metrics`; health details are exposed at `/api/v1/health`.
