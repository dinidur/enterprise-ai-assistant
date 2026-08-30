"""Guard node: the first node in the graph.

Scanning runs before the supervisor, for two reasons. It saves an LLM call on
an obvious attack, and - more importantly - it means the classification model
never reads the hostile text at all, so an injection cannot influence routing.

A blocked message is short-circuited to a refusal: the graph sets the intent to
``refuse`` and the response agent answers from a template. No retrieval runs,
no document is read, and the refusal appears in the trace where the evaluator
can see it.
"""

from __future__ import annotations

from app.agents.state import AgentState, Intent, trace
from app.core.logging import get_logger
from app.security.injection import scan_user_input

log = get_logger(__name__)

NODE = "guard"

REFUSAL = (
    "That request looks like an attempt to change my instructions or reach data "
    "outside your access level, so I have not acted on it."
)


async def guard_node(state: AgentState) -> dict:
    """Scan the incoming message before anything else runs."""
    verdict = scan_user_input(state["question"])

    if verdict.blocked:
        log.warning("request_blocked_by_guard", score=verdict.score, rules=verdict.matched)
        return {
            "intent": Intent.REFUSE.value,
            "refusal_reason": REFUSAL,
            "trace": [trace(
                NODE,
                "Blocked: prompt injection detected",
                status="error",
                detail=f"score {verdict.score} - {verdict.summary}",
                rules=verdict.matched,
                score=verdict.score,
            )],
        }

    if verdict.suspicious:
        return {
            "trace": [trace(
                NODE,
                "Input flagged but allowed",
                status="warning",
                detail=f"score {verdict.score} - {verdict.summary}",
                rules=verdict.matched,
            )],
        }

    return {"trace": [trace(NODE, "Input scan clean", detail="no injection signals")]}


def route_from_guard(state: AgentState) -> str:
    """Blocked requests skip straight to the refusal response."""
    return "respond" if state.get("intent") == Intent.REFUSE.value else "supervisor"
