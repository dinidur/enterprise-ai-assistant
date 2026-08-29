"""Manual verification of hybrid retrieval and RBAC.

Run this after ingestion to prove three things without needing the LLM,
the API or the UI:

1. Hybrid search returns relevant chunks and shows which route found each one.
2. A metadata filter narrows results as expected.
3. The same query returns *less* for a Viewer than for an Analyst, because the
   access filter is derived from the role.

Usage:
    python scripts/test_search.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.auth.roles import authenticate  # noqa: E402
from app.core.logging import configure_logging  # noqa: E402
from app.retrieval.hybrid import HybridRetriever, RetrievalQuery  # noqa: E402


def show(title: str, chunks: list) -> None:
    print(f"\n{title}")
    print("-" * len(title))
    if not chunks:
        print("  (no results)")
        return
    for i, c in enumerate(chunks, start=1):
        print(f"  {i}. [{c.found_by:<6}] {c.doc_id:<14} {c.access_level:<13} rrf={c.score:.5f}")
        print(f"     {c.title[:78]}")
        print(f"     section: {c.section}")


async def main() -> None:
    configure_logging()
    print("Loading indexes...")
    retriever = await HybridRetriever.create()

    analyst = authenticate("amara")
    viewer = authenticate("vihanga")

    # 1. Semantic question - dense search should carry this one.
    show(
        "1. Semantic query (analyst): 'why did card payments start failing?'",
        await retriever.search(RetrievalQuery(
            text="why did card payments start failing?", user=analyst, top_k=5
        )),
    )

    # 2. Exact identifier - BM25 should carry this one.
    show(
        "2. Literal identifier (analyst): 'INC-PAY-0003'",
        await retriever.search(RetrievalQuery(
            text="INC-PAY-0003", user=analyst, top_k=5
        )),
    )

    # 3. Metadata filter: payment incidents from the last year only.
    show(
        "3. Filtered (analyst): payment incidents, last 365 days",
        await retriever.search(RetrievalQuery(
            text="recurring root causes of payment outages",
            user=analyst,
            department="payments",
            document_type="incident",
            within_days=365,
            top_k=6,
        )),
    )

    # 4. The RBAC proof: identical query, two roles.
    question = "confidential access control policy and incident details"
    analyst_hits = await retriever.search(RetrievalQuery(text=question, user=analyst, top_k=8))
    viewer_hits = await retriever.search(RetrievalQuery(text=question, user=viewer, top_k=8))

    show("4a. Same query as ANALYST (may see confidential)", analyst_hits)
    show("4b. Same query as VIEWER (must not see confidential)", viewer_hits)

    analyst_conf = sum(1 for c in analyst_hits if c.access_level == "confidential")
    viewer_conf = sum(1 for c in viewer_hits if c.access_level == "confidential")
    print("\n" + "=" * 60)
    print(f"confidential chunks returned to analyst: {analyst_conf}")
    print(f"confidential chunks returned to viewer : {viewer_conf}")
    print("RBAC CHECK:", "PASS" if viewer_conf == 0 else "FAIL - viewer saw confidential data")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
