"""Retrieval agent: turns a question into evidence.

Two steps, both observable:

1. **Query rewriting.** The user's conversational phrasing is rewritten into a
   search query. This measurably helps the sparse route, which matches literal
   tokens and is hurt by filler words. If rewriting fails the original question
   is used, so the node never blocks retrieval.
2. **Hybrid search** through the shared retriever, with the access filter built
   from the caller's role.

The retriever is created once and cached: opening a Pinecone client and loading
the BM25 index on every turn would dominate response latency.
"""

from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.llm import ainvoke
from app.agents.prompts import RETRIEVAL_QUERY_PROMPT
from app.agents.state import AgentState, trace
from app.auth.roles import authenticate
from app.core.exceptions import AppError, RetrievalError
from app.core.logging import get_logger
from app.retrieval.hybrid import HybridRetriever, RetrievalQuery, RetrievedChunk
from app.security.injection import scan_retrieved

log = get_logger(__name__)

NODE = "retrieval_agent"

_retriever: HybridRetriever | None = None


async def get_retriever() -> HybridRetriever:
    """Return the process-wide retriever, creating it on first use."""
    global _retriever
    if _retriever is None:
        _retriever = await HybridRetriever.create()
    return _retriever


def chunk_to_dict(chunk: RetrievedChunk) -> dict:
    """Serialise a chunk for the graph state and the UI."""
    return {
        "chunk_id": chunk.chunk_id,
        "doc_id": chunk.doc_id,
        "title": chunk.title,
        "section": chunk.section,
        "department": chunk.department,
        "document_type": chunk.document_type,
        "access_level": chunk.access_level,
        "created_date": chunk.created_date,
        "score": chunk.score,
        "found_by": chunk.found_by,
        "text": chunk.text,
    }


async def rewrite_query(question: str) -> str:
    """Rewrite a conversational question into a search query."""
    try:
        rewritten = await ainvoke([
            SystemMessage(content=RETRIEVAL_QUERY_PROMPT),
            HumanMessage(content=question),
        ])
        cleaned = rewritten.strip().strip('"')
        return cleaned if cleaned else question
    except AppError as exc:
        log.warning("query_rewrite_failed", error=str(exc))
        return question


async def retrieval_node(state: AgentState) -> dict:
    """Retrieve evidence for a focused question."""
    question = state["question"]
    user = authenticate(state["user_id"])

    search_text = await rewrite_query(question)
    events = [trace(NODE, "Query rewritten", detail=search_text, original=question)]

    try:
        retriever = await get_retriever()
        chunks = await retriever.search(RetrievalQuery(text=search_text, user=user))
    except RetrievalError as exc:
        log.warning("retrieval_failed", error=str(exc))
        return {
            "retrieved": [],
            "errors": [f"retrieval: {exc}"],
            "trace": events + [trace(NODE, "Retrieval failed", status="error", detail=str(exc))],
        }

    routes = {"dense": 0, "sparse": 0, "both": 0}
    for chunk in chunks:
        routes[chunk.found_by] += 1

    summary = (
        f"{len(chunks)} chunks "
        f"(dense {routes['dense']}, sparse {routes['sparse']}, both {routes['both']})"
    )
    events.append(
        trace(
            NODE,
            f"Retrieved {len(chunks)} chunks",
            detail=summary,
            documents=sorted({c.doc_id for c in chunks}),
            routes=routes,
        )
    )
    # Retrieved text is untrusted input: a document can carry instructions.
    cleaned, flagged = scan_retrieved([chunk_to_dict(c) for c in chunks])
    if flagged:
        events.append(trace(
            NODE, f"Neutralised suspicious content in {len(flagged)} document(s)",
            status="warning", detail=", ".join(flagged), documents=flagged,
        ))

    log.info("retrieval_complete", chunks=len(chunks), role=user.role.value)

    return {
        "retrieved": cleaned,
        "retrieval_summary": summary,
        "trace": events,
    }
