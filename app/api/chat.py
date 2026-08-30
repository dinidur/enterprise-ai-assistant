"""Chat routes, including the streamed agent run.

The UI needs two things at once: answer tokens as they are produced, and a live
view of what the agent is doing internally. Both are delivered over a single
newline-delimited JSON stream, one JSON object per line:

    {"type": "trace",      "payload": {...}}   node activity
    {"type": "token",      "payload": {"text": "..."}}
    {"type": "citations",  "payload": {...}}
    {"type": "validation", "payload": {...}}
    {"type": "done",       "payload": {...}}

NDJSON rather than Server-Sent Events: the client here is Streamlit reading a
byte stream with httpx, so SSE's field framing would be parsing work for no
benefit. The multiplexing matters more than the wire format - one connection
means the activity panel can never drift out of order with the answer.

LangGraph's ``stream_mode=["updates", "messages"]`` supplies both channels:
``updates`` yields each node's returned state, ``messages`` yields LLM token
chunks. Token chunks are filtered to the response node, so the model's internal
routing and planning calls do not leak into the visible answer.
"""

from __future__ import annotations

import json
from typing import Any, AsyncIterator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.agents.graph import get_compiled_graph
from app.agents.llm import content_to_text
from app.agents.state import new_state
from app.api.schemas import ChatRequest, UserInfo
from app.auth.roles import USERS, Permission, User, authenticate, require_permission
from app.core.exceptions import AppError
from app.core.logging import bind_request_context, get_logger
from app.security.rate_limit import limiter

log = get_logger(__name__)

router = APIRouter(tags=["chat"])


async def current_user(user_id: str) -> User:
    """Resolve and authorise the caller.

    Used as a dependency so an unknown user or a role without chat permission
    fails before any agent work starts.
    """
    user = authenticate(user_id)
    require_permission(user, Permission.CHAT)
    return user


def _line(event_type: str, payload: dict[str, Any]) -> bytes:
    """Encode one NDJSON event."""
    return (json.dumps({"type": event_type, "payload": payload}, default=str) + "\n").encode()


@router.get("/users", response_model=list[UserInfo])
async def list_users() -> list[UserInfo]:
    """The user directory, so the UI can offer a role switcher."""
    return [
        UserInfo(
            user_id=u.user_id,
            display_name=u.display_name,
            role=u.role.value,
            department=u.department,
            permissions=sorted(p.value for p in u.permissions),
            access_levels=sorted(u.allowed_access_values()),
        )
        for u in USERS.values()
    ]


@router.post("/chat/stream")
async def chat_stream(request: ChatRequest) -> StreamingResponse:
    """Run one turn of the agent, streaming activity and tokens."""

    async def generate() -> AsyncIterator[bytes]:
        try:
            user = await current_user(request.user_id)
            await limiter.check(user.user_id)
        except AppError as exc:
            yield _line("error", {"code": exc.code, "message": exc.message})
            yield _line("done", {"ok": False})
            return

        bind_request_context(
            user_id=user.user_id, role=user.role.value, session_id=request.session_id
        )
        log.info("chat_turn_started", chars=len(request.message))

        graph = get_compiled_graph()
        state = new_state(
            question=request.message,
            user_id=user.user_id,
            role=user.role.value,
            session_id=request.session_id,
        )
        # thread_id is what gives the checkpointer its conversational memory:
        # the same session id resumes the same thread across turns.
        config = {
            "configurable": {"thread_id": f"{user.user_id}:{request.session_id}"},
            "run_name": "enterprise_assistant_turn",
            "metadata": {"user_id": user.user_id, "role": user.role.value},
        }

        emitted_traces = 0
        final_state: dict[str, Any] = {}
        # A node's update carries its trace list, and a state channel with an
        # `add` reducer can replay earlier entries. De-duplicate on the wire so
        # the activity panel shows each step exactly once.
        seen_traces: set[tuple] = set()

        try:
            async for mode, chunk in graph.astream(
                state, config=config, stream_mode=["updates", "messages"]
            ):
                if mode == "updates":
                    for node_name, update in chunk.items():
                        if not isinstance(update, dict):
                            continue
                        final_state.update(update)
                        for event in update.get("trace", []) or []:
                            key = (
                                event.get("ts"),
                                event.get("node"),
                                event.get("label"),
                            )
                            if key in seen_traces:
                                continue
                            seen_traces.add(key)
                            emitted_traces += 1
                            yield _line("trace", dict(event))
                        for message in update.get("errors", []) or []:
                            yield _line("trace", {
                                "node": node_name, "status": "warning",
                                "label": "Recoverable error", "detail": str(message),
                            })

                elif mode == "messages":
                    message_chunk, metadata = chunk
                    # Only the response agent's tokens are the visible answer.
                    if metadata.get("langgraph_node") != "respond":
                        continue
                    text = content_to_text(getattr(message_chunk, "content", ""))
                    if text:
                        yield _line("token", {"text": text})

        except AppError as exc:
            log.warning("chat_turn_failed", code=exc.code, error=exc.message)
            yield _line("error", {"code": exc.code, "message": exc.message})
            yield _line("done", {"ok": False})
            return
        except Exception as exc:  # noqa: BLE001 - never leak a stack trace to a client
            log.error("chat_turn_crashed", error=str(exc))
            yield _line("error", {
                "code": "internal_error",
                "message": "The assistant hit an unexpected error. Please try again.",
            })
            yield _line("done", {"ok": False})
            return

        # Citations, resolved back to full metadata for the UI's source list.
        verified = final_state.get("citations", []) or []
        by_doc: dict[str, dict[str, Any]] = {}
        for chunk_meta in final_state.get("retrieved", []) or []:
            by_doc.setdefault(chunk_meta["doc_id"], chunk_meta)
        yield _line("citations", {
            "citations": [by_doc[d] for d in verified if d in by_doc],
            "count": len(verified),
        })

        yield _line("validation", final_state.get("validation", {}) or {})

        remaining = await limiter.remaining(user.user_id)
        log.info("chat_turn_complete", traces=emitted_traces, citations=len(verified))
        yield _line("done", {
            "ok": True,
            "answer": final_state.get("answer", ""),
            "intent": final_state.get("intent", ""),
            "rate_limit_remaining": remaining,
        })

    return StreamingResponse(generate(), media_type="application/x-ndjson")
