"""Research agent: the Recursive Language Model (RLM) path.

The assessment asks for an agent that explores a document collection rather
than loading it into context. This node implements that in five observable
stages:

1. **Plan.** The LLM writes a structured *search plan* - metadata filters plus
   several sub-queries - instead of one vague search. The plan is a Pydantic
   model, so the filters it produces are validated fields rather than parsed
   prose.
2. **Explore.** Sub-queries run concurrently against hybrid retrieval. Only
   headers and chunk text that survive the filters come back; nothing is bulk
   loaded.
3. **Decompose.** Matching documents are grouped into small batches.
4. **Recurse.** One sub-agent per batch runs concurrently, each summarising
   only its own batch. This is the recursive step: the same read-and-summarise
   operation is applied to a subproblem, and its output is small.
5. **Aggregate.** The batch findings - not the documents - are what the
   response agent finally reads.

Why this beats stuffing the context: a year of incident reports is roughly
50,000 tokens, and the useful signal is a handful of repeated root causes.
Batching turns one enormous serial call into several small parallel ones, which
is cheaper, faster and produces a more reliable answer, because each sub-agent
attends to five documents instead of eighty.

``MAX_RECURSION_DEPTH`` bounds the recursion. An agent that can spawn
sub-agents without a bound is a cost incident waiting to happen.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from app.agents.llm import ainvoke, astructured
from app.agents.prompts import BATCH_ANALYSIS_PROMPT
from app.agents.retrieval_agent import chunk_to_dict, get_retriever
from app.agents.state import AgentState, trace
from app.auth.roles import authenticate
from app.core.exceptions import AppError
from app.core.logging import get_logger
from app.retrieval.hybrid import RetrievalQuery

log = get_logger(__name__)

NODE = "research_agent"

MAX_RECURSION_DEPTH = 2
DOCUMENTS_PER_BATCH = 5
MAX_SUB_QUERIES = 4
CHUNKS_PER_SUB_QUERY = 12
MAX_BATCHES = 8


class SearchPlan(BaseModel):
    """A structured plan for exploring the collection."""

    sub_queries: list[str] = Field(
        default_factory=list,
        description="2 to 4 distinct search queries covering different facets of the question",
    )
    department: str | None = Field(
        default=None,
        description="one of: payments, platform, security, data, customer-support - or null for all",
    )
    document_type: str | None = Field(
        default=None,
        description="one of: incident, runbook, architecture, product_spec, meeting_notes, policy - or null",
    )
    within_days: int | None = Field(
        default=None,
        description="only documents newer than this many days; 365 for 'last year', null for no limit",
    )
    rationale: str = Field(default="", description="one sentence on why this plan fits the question")


PLAN_PROMPT = """You are planning a search over an internal document collection.

Collection metadata you may filter on:
- department: payments, platform, security, data, customer-support
- document_type: incident, runbook, architecture, product_spec, meeting_notes, policy
- within_days: recency window in days

Write a plan with 2 to 4 sub-queries that cover different facets of the question,
plus any filters that clearly apply. Set a filter to null when the question does
not imply it - an unnecessary filter loses relevant documents.

Example: for "summarise outage reports about payment failures in the last year and
find recurring root causes", a good plan is department=payments,
document_type=incident, within_days=365, with sub-queries covering root causes,
customer impact, and remediation."""


async def _analyse_batch(question: str, batch_index: int, documents: dict[str, list[dict]]) -> dict:
    """One sub-agent: read a small batch and return a terse finding."""
    doc_ids = sorted(documents.keys())
    body = "\n\n".join(
        f"<document id=\"{doc_id}\">\n"
        + "\n".join(c["text"] for c in chunks)
        + "\n</document>"
        for doc_id, chunks in documents.items()
    )

    try:
        summary = await ainvoke([
            SystemMessage(content=BATCH_ANALYSIS_PROMPT),
            HumanMessage(content=f"Research question:\n{question}\n\nBatch {batch_index}:\n{body}"),
        ])
    except AppError as exc:
        log.warning("batch_analysis_failed", batch=batch_index, error=str(exc))
        return {"batch": batch_index, "doc_ids": doc_ids, "summary": "", "failed": True, "error": str(exc)}

    return {"batch": batch_index, "doc_ids": doc_ids, "summary": summary.strip(), "failed": False}


async def research_node(state: AgentState) -> dict:
    """Explore, decompose, recurse, aggregate."""
    question = state["question"]
    user = authenticate(state["user_id"])
    depth = state.get("recursion_depth", 0)
    events = []

    if depth >= MAX_RECURSION_DEPTH:
        log.warning("recursion_limit_reached", depth=depth)
        return {
            "trace": [trace(NODE, "Recursion limit reached", status="warning",
                            detail=f"depth {depth} of {MAX_RECURSION_DEPTH}")],
        }

    # --- 1. plan -------------------------------------------------------
    try:
        plan = await astructured([
            SystemMessage(content=PLAN_PROMPT),
            HumanMessage(content=question),
        ], SearchPlan)
    except AppError as exc:
        log.warning("planning_failed", error=str(exc))
        plan = SearchPlan(sub_queries=[question], rationale="planning unavailable; using the raw question")
        events.append(trace(NODE, "Planning failed, using raw question", status="warning", detail=str(exc)))

    sub_queries = (plan.sub_queries or [question])[:MAX_SUB_QUERIES]
    events.append(trace(
        NODE, f"Search plan: {len(sub_queries)} sub-queries",
        detail=plan.rationale,
        sub_queries=sub_queries,
        filters={"department": plan.department, "document_type": plan.document_type,
                 "within_days": plan.within_days},
    ))

    # --- 2. explore ----------------------------------------------------
    retriever = await get_retriever()
    searches = [
        retriever.search(RetrievalQuery(
            text=q,
            user=user,
            department=plan.department,
            document_type=plan.document_type,
            within_days=plan.within_days,
            top_k=CHUNKS_PER_SUB_QUERY,
        ))
        for q in sub_queries
    ]
    results = await asyncio.gather(*searches, return_exceptions=True)

    by_document: dict[str, list[dict]] = defaultdict(list)
    seen_chunks: set[str] = set()
    for query_text, result in zip(sub_queries, results):
        if isinstance(result, Exception):
            log.warning("sub_query_failed", query=query_text, error=str(result))
            continue
        for chunk in result:
            if chunk.chunk_id in seen_chunks:
                continue
            seen_chunks.add(chunk.chunk_id)
            by_document[chunk.doc_id].append(chunk_to_dict(chunk))

    if not by_document:
        return {
            "sub_findings": [],
            "trace": events + [trace(NODE, "Exploration found nothing", status="warning")],
        }

    events.append(trace(
        NODE, f"Explored {len(by_document)} documents",
        detail=f"{len(seen_chunks)} unique chunks across {len(sub_queries)} sub-queries",
        documents=sorted(by_document.keys()),
    ))

    # --- 3. decompose --------------------------------------------------
    doc_ids = sorted(by_document.keys())
    batches = [
        {d: by_document[d] for d in doc_ids[i : i + DOCUMENTS_PER_BATCH]}
        for i in range(0, len(doc_ids), DOCUMENTS_PER_BATCH)
    ][:MAX_BATCHES]

    events.append(trace(
        NODE, f"Decomposed into {len(batches)} batches",
        detail=f"{DOCUMENTS_PER_BATCH} documents per sub-agent, running concurrently",
    ))

    # --- 4. recurse ----------------------------------------------------
    findings = await asyncio.gather(
        *(_analyse_batch(question, i, batch) for i, batch in enumerate(batches, start=1))
    )
    successful = [f for f in findings if not f["failed"] and f["summary"]]
    failed = len(findings) - len(successful)

    for finding in successful:
        events.append(trace(
            NODE, f"Sub-agent {finding['batch']} finished",
            detail=finding["summary"][:180],
            documents=finding["doc_ids"],
        ))
    if failed:
        events.append(trace(NODE, f"{failed} sub-agent(s) failed", status="warning",
                            detail="continuing with partial findings"))

    log.info("research_complete", documents=len(by_document), batches=len(batches),
             successful=len(successful), depth=depth + 1)

    # --- 5. aggregate happens in the response agent ---------------------
    return {
        "sub_findings": successful,
        "recursion_depth": depth + 1,
        "retrieved": [c for chunks in by_document.values() for c in chunks],
        "trace": events + [trace(
            NODE, f"Aggregating {len(successful)} batch findings",
            detail="passing findings, not raw documents, to the response agent",
        )],
    }
