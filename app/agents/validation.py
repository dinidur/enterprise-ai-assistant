"""Validation node: guardrails applied to the generated answer.

Three checks run after generation, before the answer reaches the user. All
three are mechanical - none asks the model whether it behaved, because a model
that hallucinated a citation will also happily confirm that it did not.

1. **Citation verification.** Every ``[DOC-ID]`` in the answer is matched
   against the ids that were actually retrieved. An id that was never retrieved
   is a hallucinated citation: it is stripped from the answer and reported.
2. **Evidence check.** A substantive answer with no citations at all is flagged,
   because an uncited claim is exactly the failure mode citations exist to catch.
3. **Leak check.** No answer may contain content from an access level the
   caller is not entitled to. Retrieval already filters this; the check exists
   because defence in depth is the point - a future change to the retrieval
   path should fail loudly here rather than silently leak.
"""

from __future__ import annotations

import re

from app.agents.state import AgentState, Intent, trace
from app.auth.roles import authenticate
from app.core.logging import get_logger

log = get_logger(__name__)

NODE = "validation"

# Document ids follow the generator's scheme: INC-PAY-0001, RB-0004, POL-0002.
CITATION_RE = re.compile(r"\[([A-Z]{2,5}(?:-[A-Z]{2,4})?-\d{3,4})\]")

MIN_SUBSTANTIVE_CHARS = 240


async def validation_node(state: AgentState) -> dict:
    """Verify citations and access before the answer is returned."""
    answer = state.get("answer", "")
    intent = state.get("intent", "")

    # Greetings and refusals carry no evidence, so nothing to verify.
    if intent in {Intent.GREETING.value, Intent.REFUSE.value}:
        return {
            "validation": {"skipped": True, "reason": intent},
            "trace": [trace(NODE, "Validation skipped", detail=f"intent: {intent}")],
        }

    retrieved = state.get("retrieved") or []
    available_ids = {c["doc_id"] for c in retrieved}
    for finding in state.get("sub_findings") or []:
        available_ids.update(finding.get("doc_ids", []))

    cited = set(CITATION_RE.findall(answer))
    hallucinated = sorted(cited - available_ids)
    verified = sorted(cited & available_ids)

    issues: list[str] = []
    cleaned = answer

    # --- 1. hallucinated citations ---
    if hallucinated:
        for bad in hallucinated:
            cleaned = cleaned.replace(f"[{bad}]", "[unverified citation removed]")
        issues.append(f"removed {len(hallucinated)} hallucinated citation(s): {', '.join(hallucinated)}")
        log.warning("hallucinated_citations", ids=hallucinated)

    # --- 2. uncited substantive answer ---
    if not verified and len(answer) > MIN_SUBSTANTIVE_CHARS and retrieved:
        issues.append("answer is substantive but cites no source document")
        cleaned += (
            "\n\n_Note: this answer could not be linked to specific source documents. "
            "Please verify before relying on it._"
        )
        log.warning("uncited_answer", chars=len(answer))

    # --- 3. access-level leak ---
    user = authenticate(state["user_id"])
    allowed = user.allowed_access_values()
    leaked = sorted({
        c["doc_id"] for c in retrieved
        if c.get("access_level") not in allowed and c["doc_id"] in cited
    })
    if leaked:
        # Defence in depth: retrieval should have made this unreachable.
        for bad in leaked:
            cleaned = cleaned.replace(f"[{bad}]", "[redacted]")
        issues.append(f"redacted {len(leaked)} citation(s) above the caller's access level")
        log.error("access_leak_blocked", ids=leaked, role=user.role.value)

    passed = not issues
    result = {
        "passed": passed,
        "cited": sorted(cited),
        "verified": verified,
        "hallucinated": hallucinated,
        "leaked": leaked,
        "issues": issues,
        "documents_available": len(available_ids),
    }

    log.info("validation_complete", passed=passed, verified=len(verified), issues=len(issues))

    return {
        "answer": cleaned,
        "citations": verified,
        "validation": result,
        "errors": issues,
        "trace": [trace(
            NODE,
            "Validation passed" if passed else f"Validation found {len(issues)} issue(s)",
            status="ok" if passed else "warning",
            detail="; ".join(issues) if issues else f"{len(verified)} citation(s) verified",
            **result,
        )],
    }
