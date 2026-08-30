"""The LangGraph orchestration graph.

    guard  (input injection scan)
        |
        +-- blocked -------------> respond
        |
    supervisor
        |
        +-- greeting / refuse ----> respond
        +-- simple_lookup --------> retrieve --> respond
        +-- deep_research --------> research --> respond
        +-- tool_task ------------> tools ----> respond
                                                  |
                                                validate
                                                  |
                                                 END

Design notes:

* **The supervisor is the only branching point.** Specialists do not decide who
  runs next, so adding an agent means adding a node and one edge, not editing
  the existing agents.
* **Validation is a separate node after generation**, not a flag inside the
  response agent. It runs on every answered path, so no future route can
  accidentally skip the guardrails.
* **A checkpointer supplies conversational memory.** Threading turns by
  ``thread_id`` means multi-turn context is handled by the graph runtime rather
  than by manually re-stuffing history into each prompt, and the same mechanism
  supports resuming an interrupted run.
"""

from __future__ import annotations

from functools import lru_cache

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from app.agents.guard import guard_node, route_from_guard
from app.agents.research_agent import research_node
from app.agents.response_agent import response_node
from app.agents.retrieval_agent import retrieval_node
from app.agents.state import AgentState
from app.agents.supervisor import route_from_supervisor, supervisor_node
from app.agents.tools_node import tools_node
from app.agents.validation import validation_node
from app.core.logging import get_logger

log = get_logger(__name__)


def build_graph() -> StateGraph:
    """Wire the nodes and edges."""
    graph = StateGraph(AgentState)

    graph.add_node("guard", guard_node)
    graph.add_node("supervisor", supervisor_node)
    graph.add_node("retrieve", retrieval_node)
    graph.add_node("research", research_node)
    graph.add_node("tools", tools_node)
    graph.add_node("respond", response_node)
    graph.add_node("validate", validation_node)

    graph.add_edge(START, "guard")
    graph.add_conditional_edges(
        "guard", route_from_guard, {"supervisor": "supervisor", "respond": "respond"}
    )
    graph.add_conditional_edges(
        "supervisor",
        route_from_supervisor,
        {"retrieve": "retrieve", "research": "research", "tools": "tools", "respond": "respond"},
    )
    graph.add_edge("retrieve", "respond")
    graph.add_edge("research", "respond")
    graph.add_edge("tools", "respond")
    graph.add_edge("respond", "validate")
    graph.add_edge("validate", END)

    return graph


@lru_cache(maxsize=1)
def get_compiled_graph():
    """Compile the graph once per process, with in-memory checkpointing.

    ``InMemorySaver`` keeps conversation state for the lifetime of the process,
    which satisfies "memory should survive multiple turns during a session".
    Swapping in a Postgres or Redis saver is a one-line change and is the
    documented path to durable memory - deliberately not taken here, because a
    POC does not need the operational cost of another datastore.
    """
    compiled = build_graph().compile(checkpointer=InMemorySaver())
    log.info("graph_compiled", nodes=["guard", "supervisor", "retrieve", "research", "tools", "respond", "validate"])
    return compiled


def export_mermaid() -> str:
    """Return the graph as a Mermaid diagram, for the README."""
    return build_graph().compile().get_graph().draw_mermaid()
