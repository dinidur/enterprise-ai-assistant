"""Shared graph state and the trace events the UI renders.

State design decisions:

* **One typed state object** flows through every node. LangGraph merges the
  partial dict each node returns, so a node declares only what it changed -
  which keeps nodes independently testable and makes the data flow readable in
  a diff.
* **``trace`` is an append-only list** using LangGraph's ``add`` reducer. Nodes
  never overwrite each other's events even when they run concurrently, and the
  finished list is exactly what the Agent Activity Panel needs. Observability
  is therefore part of the state, not a side channel bolted on afterwards.
* **``errors`` is also additive.** A failed node records the failure and lets
  the graph continue, which is how the application degrades gracefully instead
  of returning a 500.
"""

from __future__ import annotations

import time
from enum import StrEnum
from operator import add
from typing import Annotated, Any, Literal, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class Intent(StrEnum):
    """What the supervisor decided the user wants."""

    GREETING = "greeting"          # small talk; no retrieval needed
    SIMPLE_LOOKUP = "simple_lookup"  # one focused question -> retrieval agent
    DEEP_RESEARCH = "deep_research"  # broad/aggregating question -> RLM path
    TOOL_TASK = "tool_task"        # needs analytics or an MCP tool
    REFUSE = "refuse"              # out of scope, unsafe, or blocked


class TraceEvent(TypedDict, total=False):
    """One observable step, streamed to the Agent Activity Panel."""

    ts: float
    node: str
    status: Literal["running", "ok", "warning", "error"]
    label: str
    detail: str
    data: dict[str, Any]


def trace(
    node: str,
    label: str,
    *,
    status: Literal["running", "ok", "warning", "error"] = "ok",
    detail: str = "",
    **data: Any,
) -> TraceEvent:
    """Build a trace event. Keeps node code to one readable line."""
    return TraceEvent(
        ts=time.time(), node=node, status=status, label=label, detail=detail, data=data
    )


class AgentState(TypedDict, total=False):
    """State passed between every node in the graph."""

    # --- input ---
    messages: Annotated[list[BaseMessage], add_messages]
    question: str
    user_id: str
    role: str
    session_id: str

    # --- supervisor output ---
    intent: str
    plan: list[str]
    refusal_reason: str

    # --- retrieval output ---
    retrieved: list[dict[str, Any]]
    retrieval_summary: str

    # --- research (RLM) output ---
    sub_findings: list[dict[str, Any]]
    recursion_depth: int

    # --- tool output ---
    tool_results: list[dict[str, Any]]

    # --- response and validation ---
    answer: str
    citations: list[str]
    validation: dict[str, Any]

    # --- observability, additive ---
    trace: Annotated[list[TraceEvent], add]
    errors: Annotated[list[str], add]


def new_state(question: str, user_id: str, role: str, session_id: str) -> AgentState:
    """Seed a fresh state for one turn."""
    return AgentState(
        question=question,
        user_id=user_id,
        role=role,
        session_id=session_id,
        retrieved=[],
        sub_findings=[],
        tool_results=[],
        recursion_depth=0,
        trace=[],
        errors=[],
    )
