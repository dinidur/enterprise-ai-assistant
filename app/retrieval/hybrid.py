"""Hybrid retrieval: dense + sparse, fused, access-filtered.

Why hybrid at all: dense search understands paraphrase but is weak on rare
literal tokens, while BM25 is the opposite. A user asking "what caused the
gateway timeouts?" needs the former; a user asking for `INC-PAY-0007` or
"SEV1" needs the latter. Running both and fusing costs one extra concurrent
call and covers both query shapes.

**Fusion method: Reciprocal Rank Fusion.** Dense cosine similarity and BM25
scores live on incompatible scales, so a weighted sum of raw scores needs
per-corpus tuning that will not survive a change of embedding model. RRF uses
only *rank*, so it needs no tuning, cannot be destabilised by an outlier score,
and is the standard choice for exactly this reason. The trade-off is that it
discards score magnitude, so a single overwhelmingly good dense hit is not
allowed to dominate - acceptable here, because the answer layer reads several
chunks anyway.

Security note: the access filter is applied to *both* routes. Filtering only
the dense path would leave the keyword route as an open door to confidential
documents.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from app.auth.roles import User, access_filter
from app.core.config import settings
from app.core.exceptions import RetrievalError
from app.core.logging import get_logger
from app.retrieval.embeddings import embed_query
from app.retrieval.sparse import SparseIndex
from app.retrieval.vector_store import SearchHit, VectorStore

log = get_logger(__name__)

# RRF smoothing constant. 60 is the value from the original paper and the
# common default; it damps the influence of the very top ranks just enough that
# one route cannot dictate the whole fused list.
RRF_K = 60

DEPARTMENTS = ["payments", "platform", "security", "data", "customer-support"]


@dataclass
class RetrievedChunk:
    """A fused search result, carrying enough provenance to cite it."""

    chunk_id: str
    text: str
    doc_id: str
    title: str
    department: str
    document_type: str
    access_level: str
    created_date: str
    section: str
    score: float
    dense_rank: int | None = None
    sparse_rank: int | None = None

    @property
    def found_by(self) -> str:
        """Which route surfaced this chunk - shown in the activity panel."""
        if self.dense_rank is not None and self.sparse_rank is not None:
            return "both"
        return "dense" if self.dense_rank is not None else "sparse"

    def citation(self) -> str:
        return f"[{self.doc_id}] {self.title} - {self.section}"


@dataclass
class RetrievalQuery:
    """Everything that shapes one search."""

    text: str
    user: User
    department: str | None = None
    document_type: str | None = None
    within_days: int | None = None
    top_k: int | None = None


class HybridRetriever:
    """Runs dense and sparse search concurrently and fuses the ranks."""

    def __init__(self, store: VectorStore, sparse: SparseIndex | None) -> None:
        self._store = store
        self._sparse = sparse

    @classmethod
    async def create(cls) -> "HybridRetriever":
        """Open the vector index and load the BM25 index.

        A missing BM25 index degrades to dense-only rather than failing: partial
        retrieval beats no retrieval.
        """
        store = VectorStore()
        await store.ensure_index()
        try:
            sparse = await asyncio.to_thread(SparseIndex.load)
        except RetrievalError as exc:
            log.warning("sparse_index_unavailable", error=str(exc))
            sparse = None
        return cls(store, sparse)

    # --- filter construction --------------------------------------------

    def _build_filter(self, query: RetrievalQuery) -> dict[str, Any]:
        """Compose the metadata filter.

        The access clause comes from the role and is merged last, so a caller
        supplied filter can only ever narrow the result set, never widen it.
        """
        clauses: dict[str, Any] = {}
        if query.document_type:
            clauses["document_type"] = {"$eq": query.document_type}
        if query.within_days:
            cutoff = (date.today() - timedelta(days=query.within_days)).toordinal()
            clauses["created_ts"] = {"$gte": cutoff}
        clauses.update(access_filter(query.user))
        return clauses

    # --- the two routes --------------------------------------------------

    async def _dense(self, query: RetrievalQuery, candidate_k: int) -> list[SearchHit]:
        vector = await embed_query(query.text)
        namespaces = [query.department] if query.department else DEPARTMENTS
        metadata_filter = self._build_filter(query)
        if len(namespaces) == 1:
            return await self._store.query(
                vector, top_k=candidate_k, namespace=namespaces[0], metadata_filter=metadata_filter
            )
        return await self._store.query_many(
            vector, top_k=candidate_k, namespaces=namespaces, metadata_filter=metadata_filter
        )

    async def _sparse_search(self, query: RetrievalQuery, candidate_k: int) -> list[Any]:
        if self._sparse is None:
            return []
        return await asyncio.to_thread(
            self._sparse.search,
            query.text,
            top_k=candidate_k,
            allowed_access_levels=query.user.allowed_access_values(),
            department=query.department,
        )

    # --- fusion ----------------------------------------------------------

    @staticmethod
    def _fuse(
        dense: list[SearchHit], sparse: list[Any], top_k: int
    ) -> list[RetrievedChunk]:
        """Reciprocal Rank Fusion over the two ranked lists."""
        scores: dict[str, float] = {}
        dense_rank: dict[str, int] = {}
        sparse_rank: dict[str, int] = {}
        payload: dict[str, dict[str, Any]] = {}

        for rank, hit in enumerate(dense, start=1):
            scores[hit.chunk_id] = scores.get(hit.chunk_id, 0.0) + 1.0 / (RRF_K + rank)
            dense_rank[hit.chunk_id] = rank
            payload.setdefault(hit.chunk_id, {
                "text": hit.text, "doc_id": hit.doc_id, "title": hit.title,
                "department": hit.department, "document_type": hit.document_type,
                "access_level": hit.access_level, "created_date": hit.created_date,
                "section": hit.section,
            })

        for rank, hit in enumerate(sparse, start=1):
            meta = hit.metadata
            scores[hit.chunk_id] = scores.get(hit.chunk_id, 0.0) + 1.0 / (RRF_K + rank)
            sparse_rank[hit.chunk_id] = rank
            payload.setdefault(hit.chunk_id, {
                "text": str(meta.get("text", "")), "doc_id": str(meta.get("doc_id", "")),
                "title": str(meta.get("title", "")), "department": str(meta.get("department", "")),
                "document_type": str(meta.get("document_type", "")),
                "access_level": str(meta.get("access_level", "")),
                "created_date": str(meta.get("created_date", "")),
                "section": str(meta.get("section", "")),
            })

        ordered = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)[:top_k]
        return [
            RetrievedChunk(
                chunk_id=chunk_id,
                score=round(score, 6),
                dense_rank=dense_rank.get(chunk_id),
                sparse_rank=sparse_rank.get(chunk_id),
                **payload[chunk_id],
            )
            for chunk_id, score in ordered
        ]

    # --- public API ------------------------------------------------------

    async def search(self, query: RetrievalQuery) -> list[RetrievedChunk]:
        """Run both routes concurrently, fuse, and return the top chunks.

        ``return_exceptions`` means one failing route degrades the result rather
        than failing the request - if Pinecone is down, BM25 still answers.
        """
        top_k = query.top_k or settings.retrieval_top_k
        candidate_k = max(settings.retrieval_candidate_k, top_k * 2)

        dense_result, sparse_result = await asyncio.gather(
            self._dense(query, candidate_k),
            self._sparse_search(query, candidate_k),
            return_exceptions=True,
        )

        if isinstance(dense_result, Exception):
            log.warning("dense_route_failed", error=str(dense_result))
            dense_result = []
        if isinstance(sparse_result, Exception):
            log.warning("sparse_route_failed", error=str(sparse_result))
            sparse_result = []

        if not dense_result and not sparse_result:
            raise RetrievalError("both retrieval routes failed or returned nothing")

        fused = self._fuse(dense_result, sparse_result, top_k)
        log.info(
            "hybrid_search_complete",
            query_chars=len(query.text),
            dense=len(dense_result),
            sparse=len(sparse_result),
            fused=len(fused),
            role=query.user.role.value,
        )
        return fused
