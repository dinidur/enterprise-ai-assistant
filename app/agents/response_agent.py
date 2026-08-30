"""Response agent: writes the final answer from the evidence.

The evidence is wrapped in ``<document>`` tags with its metadata, for three
reasons: the model can attribute each claim to a specific id, the delimiters
mark clearly where untrusted content begins and ends, and the citations the
model produces can be checked mechanically afterwards by the validation node.

Greetings and refusals never reach the LLM with documents attached - they are
answered directly, which saves a call and removes any chance of leaking
evidence into a response that should not contain any.
"""

from __future__ import annotations

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.agents.llm import ainvoke
from app.agents.prompts import ORGANISATION, RESPONSE_PROMPT
from app.agents.state import AgentState, Intent, trace
from app.core.exceptions import AppError
from app.core.logging import get_logger

log = get_logger(__name__)

NODE = "response_agent"

# How much evidence to put in the prompt. Bounded so a broad question cannot
# push the context window - and cost - without limit.
MAX_EVIDENCE_CHUNKS = 12

GREETING_REPLY = (
    f"Hello. I am {ORGANISATION}'s internal knowledge assistant. "
    "I can search internal policies, architecture documents, runbooks, incident "
    "reports, product specifications and meeting notes, and answer questions with "
    "citations to the source documents. What would you like to know?"
)


def format_evidence(chunks: list[dict]) -> str:
    """Render retrieved chunks as delimited, attributed blocks."""
    blocks = []
    for chunk in chunks[:MAX_EVIDENCE_CHUNKS]:
        blocks.append(
            f"<document id=\"{chunk['doc_id']}\" "
            f"type=\"{chunk['document_type']}\" "
            f"department=\"{chunk['department']}\" "
            f"date=\"{chunk['created_date']}\">\n"
            f"{chunk['text']}\n"
            f"</document>"
        )
    return "\n\n".join(blocks)


async def response_node(state: AgentState) -> dict:
    """Produce the final answer."""
    intent = state.get("intent", "")
    question = state["question"]

    if intent == Intent.GREETING.value:
        return {
            "answer": GREETING_REPLY,
            "citations": [],
            "messages": [AIMessage(content=GREETING_REPLY)],
            "trace": [trace(NODE, "Answered directly", detail="greeting, no retrieval")],
        }

    if intent == Intent.REFUSE.value:
        reason = state.get("refusal_reason") or "That request is outside what I can help with."
        reply = (
            f"{reason}\n\nI can help with questions about internal policies, "
            "architecture, runbooks, incidents, product specifications and meeting notes."
        )
        log.info("request_refused", reason=reason[:120])
        return {
            "answer": reply,
            "citations": [],
            "messages": [AIMessage(content=reply)],
            "trace": [trace(NODE, "Request refused", status="warning", detail=reason)],
        }

    # Deep research supplies aggregated findings; lookup supplies raw chunks.
    findings = state.get("sub_findings") or []
    chunks = state.get("retrieved") or []

    if findings:
        evidence = "\n\n".join(
            f"<finding batch=\"{f['batch']}\" documents=\"{', '.join(f['doc_ids'])}\">\n"
            f"{f['summary']}\n</finding>"
            for f in findings
        )
        source = f"{len(findings)} aggregated batch findings"
    elif chunks:
        evidence = format_evidence(chunks)
        source = f"{min(len(chunks), MAX_EVIDENCE_CHUNKS)} retrieved chunks"
    else:
        reply = (
            "I could not find any internal documents that answer that question. "
            "It may be outside the indexed knowledge base, or outside what your "
            "role is permitted to access."
        )
        return {
            "answer": reply,
            "citations": [],
            "messages": [AIMessage(content=reply)],
            "trace": [trace(NODE, "No evidence available", status="warning")],
        }

    tool_results = state.get("tool_results") or []
    if tool_results:
        evidence += "\n\n<tool_results>\n" + "\n".join(
            f"{r['tool']}: {r['output']}" for r in tool_results
        ) + "\n</tool_results>"

    try:
        answer = await ainvoke([
            SystemMessage(content=RESPONSE_PROMPT),
            HumanMessage(content=f"Question:\n{question}\n\nEvidence:\n{evidence}"),
        ])
    except AppError as exc:
        log.warning("response_generation_failed", error=str(exc))
        fallback = (
            "I retrieved relevant documents but could not generate an answer because "
            f"the language model is unavailable ({exc}). The most relevant documents were: "
            + ", ".join(sorted({c["doc_id"] for c in chunks})[:5])
        )
        return {
            "answer": fallback,
            "citations": [],
            "errors": [f"response: {exc}"],
            "messages": [AIMessage(content=fallback)],
            "trace": [trace(NODE, "Generation failed", status="error", detail=str(exc))],
        }

    log.info("answer_generated", chars=len(answer))
    return {
        "answer": answer,
        "messages": [AIMessage(content=answer)],
        "trace": [trace(NODE, "Answer generated", detail=f"from {source}", chars=len(answer))],
    }
