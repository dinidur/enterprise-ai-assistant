"""BM25 keyword index.

Dense search alone misses exact identifiers: a user asking for `INC-PAY-0007`
or "SEV1" wants a literal match, and an embedding of a rare token is a poor
signal. BM25 covers that lexical half of hybrid retrieval.

The index is built once during ingestion and persisted, so the API process
loads it rather than rebuilding on every start. For a corpus of this size an
in-process index is the right trade-off; a production system would move this
to OpenSearch or Pinecone's own sparse vectors.
"""

from __future__ import annotations

import pickle
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rank_bm25 import BM25Okapi

from app.core.exceptions import RetrievalError
from app.core.logging import get_logger

log = get_logger(__name__)

INDEX_PATH = Path("data/index/bm25.pkl")
_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9_-]*")


def tokenize(text: str) -> list[str]:
    """Lowercase word tokenizer that preserves identifiers.

    Hyphens and underscores are kept inside tokens so `inc-pay-0007` and
    `payment-authorisation-api` survive as single searchable terms.
    """
    return _TOKEN_RE.findall(text.lower())


@dataclass
class SparseHit:
    """One BM25 result."""

    chunk_id: str
    score: float
    metadata: dict[str, Any]


class SparseIndex:
    """In-process BM25 index over chunk text."""

    def __init__(self, chunk_ids: list[str], metadata: list[dict[str, Any]], corpus: list[list[str]]) -> None:
        self._chunk_ids = chunk_ids
        self._metadata = metadata
        self._bm25 = BM25Okapi(corpus)

    @classmethod
    def build(cls, chunk_ids: list[str], texts: list[str], metadata: list[dict[str, Any]]) -> "SparseIndex":
        """Build the index from chunk text."""
        log.info("building_bm25_index", chunks=len(texts))
        return cls(chunk_ids, metadata, [tokenize(t) for t in texts])

    def search(
        self,
        query: str,
        *,
        top_k: int,
        allowed_access_levels: set[str] | None = None,
        department: str | None = None,
    ) -> list[SparseHit]:
        """Score the query against the corpus and return the best matches.

        Access filtering is applied here as well as in the dense path, so a
        role can never reach a document through the keyword route that the
        vector route would have denied.
        """
        scores = self._bm25.get_scores(tokenize(query))
        ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)

        hits: list[SparseHit] = []
        for i in ranked:
            if scores[i] <= 0:
                break
            meta = self._metadata[i]
            if allowed_access_levels and meta.get("access_level") not in allowed_access_levels:
                continue
            if department and meta.get("department") != department:
                continue
            hits.append(SparseHit(chunk_id=self._chunk_ids[i], score=float(scores[i]), metadata=meta))
            if len(hits) >= top_k:
                break
        return hits

    # --- persistence -----------------------------------------------------

    def save(self, path: Path = INDEX_PATH) -> None:
        """Persist the index to disk."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("wb") as fh:
            pickle.dump(self, fh)
        log.info("bm25_index_saved", path=str(path))

    @staticmethod
    def load(path: Path = INDEX_PATH) -> "SparseIndex":
        """Load a previously built index.

        Raises:
            RetrievalError: if ingestion has not been run yet.
        """
        if not path.exists():
            raise RetrievalError(
                f"BM25 index not found at {path}. Run: python scripts/ingest.py"
            )
        with path.open("rb") as fh:
            return pickle.load(fh)
