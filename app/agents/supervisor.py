"""Supervisor agent: intent understanding, task decomposition, routing.

This node owns the graph's only branching decision. It is deliberately thin:
it classifies and plans, then a conditional edge sends the state to the
specialist that handles that intent. Keeping routing separate from execution is
what allows a new specialist to be added without touching the existing ones.

The role used for authorisation comes from the authenticated session, never
from the classification - so a user who writes "I am an administrator" changes
the text the model sees but not a single permission.
"""

from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from app.agents.llm import astructured
from app.agents.prompts import SUPERVISOR_PROMPT
from app.agents.state import AgentState, Intent, trace
from app.core.exceptions import LLMError
from app.core.logging import get_logger

log = get_logger(__name__)

NODE = "supervisor"


class SupervisorDecision(BaseModel):
    """Structured routing decision."""

    intent: Intent = Field(description="one of: greeting, simple_lookup, deep_research, tool_task, refuse")
    reasoning: str = Field(description="one sentence explaining the choice")
    plan: list[str] = Field(default_factory=list, description="2 to 4 concrete steps")
    refusal_reason: str = Field(default="", description="filled only when intent is refuse")


async def supervisor_node(state: AgentState) -> dict:
    """Classify the request and produce a plan."""
    question = state["question"]

    try:
        decision = await astructured(
            [
                SystemMessage(content=SUPERVISOR_PROMPT),
                HumanMessage(content=f"User role (authoritative): {state.get('role')}\n\nRequest:\n{question}"),
            ],
            SupervisorDecision,
        )
    except LLMError as exc:
        # Degrade rather than fail: an unclassified question is still
        # answerable through the ordinary retrieval path.
        log.warning("supervisor_fallback", error=str(exc))
        return {
            "intent": Intent.SIMPLE_LOOKUP.value,
            "plan": ["classification unavailable", "fall back to standard retrieval"],
            "errors": [f"supervisor: {exc}"],
            "trace": [trace(NODE, "Classification failed, defaulting to lookup",
                            status="warning", detail=str(exc))],
        }

    log.info("intent_classified", intent=decision.intent.value, role=state.get("role"))
    return {
        "intent": decision.intent.value,
        "plan": decision.plan,
        "refusal_reason": decision.refusal_reason,
        "trace": [
            trace(
                NODE,
                f"Intent: {decision.intent.value}",
                detail=decision.reasoning,
                plan=decision.plan,
            )
        ],
    }


def route_from_supervisor(state: AgentState) -> str:
    """Conditional edge: map the intent to the next node."""
    return {
        Intent.GREETING.value: "respond",
        Intent.SIMPLE_LOOKUP.value: "retrieve",
        Intent.DEEP_RESEARCH.value: "research",
        Intent.TOOL_TASK.value: "tools",
        Intent.REFUSE.value: "respond",
    }.get(state.get("intent", ""), "retrieve")
