"""Tool node: executes tools under role enforcement.

Tools are registered in ``app.tools`` and are looked up by name here. The
important property is the order of operations: the permission check happens
*before* the tool is called, in Python, using the authenticated role - so the
model choosing to call a tool is a request, not an authorisation.

The tool set is filled out in the tools step; this node is the enforcement
point they all pass through.
"""

from __future__ import annotations

import asyncio

from app.agents.state import AgentState, trace
from app.auth.roles import Permission, authenticate, require_permission
from app.core.exceptions import AuthorizationError, ToolTimeout
from app.core.logging import get_logger

log = get_logger(__name__)

NODE = "tools"

TOOL_TIMEOUT_SECONDS = 20


async def tools_node(state: AgentState) -> dict:
    """Run the requested tools, enforcing permissions and timeouts.

    Currently routes tool tasks through retrieval; concrete tools are added in
    the tool-calling step and registered here.
    """
    user = authenticate(state["user_id"])

    try:
        require_permission(user, Permission.ANALYTICS_TOOLS)
    except AuthorizationError as exc:
        log.warning("tool_access_denied", role=user.role.value, error=str(exc))
        return {
            "tool_results": [],
            "errors": [str(exc)],
            "trace": [trace(NODE, "Tool access denied", status="warning", detail=str(exc))],
        }

    events = [trace(NODE, "Tool permissions granted", detail=f"role: {user.role.value}")]

    # Placeholder until concrete tools are registered: fall through to
    # retrieval so a tool_task still produces a grounded answer.
    from app.agents.retrieval_agent import retrieval_node

    try:
        result = await asyncio.wait_for(retrieval_node(state), timeout=TOOL_TIMEOUT_SECONDS)
    except asyncio.TimeoutError as exc:
        raise ToolTimeout(f"tool execution exceeded {TOOL_TIMEOUT_SECONDS}s") from exc

    result["trace"] = events + result.get("trace", [])
    return result
