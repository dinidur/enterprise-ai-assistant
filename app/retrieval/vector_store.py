"""Pinecone vector store.

Design decisions worth defending in review:

* **Namespaces per department.** Every query already knows the caller's role,
  and most questions are department-scoped, so searching one namespace instead
  of the whole index cuts both latency and cross-department leakage risk. A
  cross-department query fans out over namespaces concurrently.
* **Access level enforced as a metadata filter**, built server-side from the
  caller's role. The filter is never taken from user input or from the model,
  so the agent cannot widen its own permissions by writing a different filter.
* **The Pinecone SDK is synchronous**, so every call is pushed to a worker
  thread. The public surface here is async, which keeps the FastAPI request
  path non-blocking.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Iterable

from pinecone import Pinecone, ServerlessSpec

from app.core.config import settings
from app.core.exceptions import RetrievalError
from app.core.logging import get_logger

log = get_logger(__name__)

UPSERT_BATCH_SIZE = 100


@dataclass
class SearchHit:
    """One retrieved chunk with its provenance."""

    chunk_id: str
    score: float
    text: str
    doc_id: str
    title: str
    department: str
    document_type: str
    access_level: str
    created_date: str
    section: str

    @classmethod
    def from_match(cls, match: Any) -> "SearchHit":
        meta = match.get("metadata", {}) if isinstance(match, dict) else match.metadata
        ident = match.get("id") if isinstance(match, dict) else match.id
        score = match.get("score") if isinstance(match, dict) else match.score
        return cls(
            chunk_id=str(ident),
            score=float(score or 0.0),
            text=str(meta.get("text", "")),
            doc_id=str(meta.get("doc_id", "")),
            title=str(meta.get("title", "")),
            department=str(meta.get("department", "")),
            document_type=str(meta.get("document_type", "")),
            access_level=str(meta.get("access_level", "")),
            created_date=str(meta.get("created_date", "")),
            section=str(meta.get("section", "")),
        )


class VectorStore:
    """Thin async wrapper over the Pinecone index."""

    def __init__(self) -> None:
        if not settings.pinecone_api_key:
            raise RetrievalError("PINECONE_API_KEY is not set")
        self._client = Pinecone(api_key=settings.pinecone_api_key)
        self._index_name = settings.pinecone_index
        self._index: Any | None = None

    # --- lifecycle -------------------------------------------------------

    def _ensure_index_sync(self) -> None:
        existing = {i["name"] for i in self._client.list_indexes()}
        if self._index_name not in existing:
            log.info(
                "creating_index",
                index=self._index_name,
                dimension=settings.embedding_dimension,
            )
            self._client.create_index(
                name=self._index_name,
                dimension=settings.embedding_dimension,
                metric="cosine",
                spec=ServerlessSpec(
                    cloud=settings.pinecone_cloud,
                    region=settings.pinecone_region,
                ),
            )
        self._index = self._client.Index(self._index_name)

    async def ensure_index(self) -> None:
        """Create the index if it does not exist, then open a handle."""
        await asyncio.to_thread(self._ensure_index_sync)

    @property
    def index(self) -> Any:
        if self._index is None:
            raise RetrievalError("index handle not opened; call ensure_index() first")
        return self._index

    async def describe(self) -> dict[str, Any]:
        """Index statistics, used by the /ready probe and the ingest report."""
        return await asyncio.to_thread(lambda: self.index.describe_index_stats().to_dict())

    # --- writes ----------------------------------------------------------

    async def upsert(self, vectors: list[dict[str, Any]], namespace: str) -> int:
        """Upsert vectors in batches. Returns the number written."""
        written = 0
        for start in range(0, len(vectors), UPSERT_BATCH_SIZE):
            batch = vectors[start : start + UPSERT_BATCH_SIZE]
            try:
                await asyncio.to_thread(self.index.upsert, vectors=batch, namespace=namespace)
            except Exception as exc:  # noqa: BLE001 - surfaced as a domain error
                raise RetrievalError(f"upsert failed for namespace {namespace}: {exc}") from exc
            written += len(batch)
            log.info("upserted_batch", namespace=namespace, count=len(batch))
        return written

    # --- reads -----------------------------------------------------------

    async def query(
        self,
        vector: list[float],
        *,
        top_k: int,
        namespace: str | None = None,
        metadata_filter: dict[str, Any] | None = None,
    ) -> list[SearchHit]:
        """Dense similarity search within one namespace."""

        def _run() -> Any:
            return self.index.query(
                vector=vector,
                top_k=top_k,
                namespace=namespace,
                filter=metadata_filter,
                include_metadata=True,
            )

        try:
            response = await asyncio.to_thread(_run)
        except Exception as exc:  # noqa: BLE001
            raise RetrievalError(f"vector search failed: {exc}") from exc

        matches = response.get("matches", []) if isinstance(response, dict) else response.matches
        return [SearchHit.from_match(m) for m in matches]

    async def query_many(
        self,
        vector: list[float],
        *,
        top_k: int,
        namespaces: Iterable[str],
        metadata_filter: dict[str, Any] | None = None,
    ) -> list[SearchHit]:
        """Search several namespaces concurrently and merge by score.

        One slow or failing namespace must not sink the whole query, so results
        are gathered with ``return_exceptions`` and partial failures are logged
        rather than raised - this is the graceful-degradation requirement.
        """
        tasks = [
            self.query(vector, top_k=top_k, namespace=ns, metadata_filter=metadata_filter)
            for ns in namespaces
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        hits: list[SearchHit] = []
        for namespace, result in zip(namespaces, results):
            if isinstance(result, Exception):
                log.warning("namespace_query_failed", namespace=namespace, error=str(result))
                continue
            hits.extend(result)

        hits.sort(key=lambda h: h.score, reverse=True)
        return hits[:top_k]
