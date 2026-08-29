"""Local embedding model.

Embeddings run on-device through fastembed (ONNX runtime). Rationale, for the
README's model-selection section:

* No API quota is consumed during ingestion or at query time, so a recorded
  demo cannot fail on a rate limit.
* ONNX means no torch dependency: ~150 MB rather than ~2.5 GB, which keeps the
  Docker image small.
* bge-small-en-v1.5 scores well on retrieval benchmarks for its size and emits
  384-dimension vectors, so the Pinecone index stays cheap.

The model is loaded once and reused. ``fastembed`` is synchronous, so calls are
pushed to a worker thread to keep the async event loop free.
"""

from __future__ import annotations

import asyncio
from functools import lru_cache

from fastembed import TextEmbedding

from app.core.config import settings
from app.core.logging import get_logger

log = get_logger(__name__)


@lru_cache(maxsize=1)
def get_embedding_model() -> TextEmbedding:
    """Load the embedding model once per process.

    The first call downloads the model (~130 MB) into the fastembed cache.
    """
    log.info("loading_embedding_model", model=settings.embedding_model)
    return TextEmbedding(model_name=settings.embedding_model)


def embed_documents_sync(texts: list[str]) -> list[list[float]]:
    """Embed passages for indexing (blocking)."""
    model = get_embedding_model()
    return [vector.tolist() for vector in model.embed(texts)]


def embed_query_sync(text: str) -> list[float]:
    """Embed a search query (blocking).

    bge models are trained asymmetrically: queries need an instruction prefix
    that passages must not have. ``query_embed`` applies it, so using the right
    method here measurably improves recall.
    """
    model = get_embedding_model()
    return next(iter(model.query_embed(text))).tolist()


async def embed_documents(texts: list[str]) -> list[list[float]]:
    """Embed passages without blocking the event loop."""
    return await asyncio.to_thread(embed_documents_sync, texts)


async def embed_query(text: str) -> list[float]:
    """Embed a query without blocking the event loop."""
    return await asyncio.to_thread(embed_query_sync, text)
