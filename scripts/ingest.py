"""Ingest the knowledge base into Pinecone and build the BM25 index.

Pipeline:

1. Load and chunk every markdown document in ``data/documents``.
2. Embed all chunks locally (fastembed - no API quota consumed).
3. Upsert into Pinecone, one namespace per department.
4. Build and persist the BM25 index used by the sparse half of hybrid search.

Both indexes are built from exactly the same chunk list, so a chunk id returned
by either route resolves to the same text. That property is what lets the
guardrail layer verify a citation later.

Usage:
    python scripts/ingest.py                 # full ingestion
    python scripts/ingest.py --dry-run       # chunk and report, no network
    python scripts/ingest.py --limit 10      # ingest only 10 documents
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
from collections import defaultdict
from pathlib import Path

# Allow running as `python scripts/ingest.py` from the project root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.exceptions import RetrievalError  # noqa: E402
from app.core.logging import configure_logging, get_logger  # noqa: E402
from app.retrieval.chunking import Chunk, chunk_document  # noqa: E402
from app.retrieval.embeddings import embed_documents  # noqa: E402
from app.retrieval.sparse import SparseIndex  # noqa: E402
from app.retrieval.vector_store import VectorStore  # noqa: E402

log = get_logger("ingest")

DOCUMENTS_DIR = Path("data/documents")
EMBED_BATCH_SIZE = 64


def load_chunks(directory: Path, limit: int | None) -> list[Chunk]:
    """Load documents from disk and chunk them."""
    paths = sorted(directory.glob("*.md"))
    if not paths:
        raise SystemExit(
            f"No documents found in {directory}. Run: python scripts/generate_documents.py"
        )
    if limit:
        paths = paths[:limit]

    chunks: list[Chunk] = []
    for path in paths:
        try:
            chunks.extend(chunk_document(path.read_text(encoding="utf-8")))
        except ValueError as exc:
            log.warning("skipping_document", file=path.name, error=str(exc))
    log.info("documents_chunked", documents=len(paths), chunks=len(chunks))
    return chunks


async def embed_all(chunks: list[Chunk]) -> list[list[float]]:
    """Embed every chunk, in batches, reporting progress."""
    vectors: list[list[float]] = []
    started = time.perf_counter()
    for start in range(0, len(chunks), EMBED_BATCH_SIZE):
        batch = chunks[start : start + EMBED_BATCH_SIZE]
        vectors.extend(await embed_documents([c.text for c in batch]))
        print(f"  embedded {len(vectors)}/{len(chunks)} chunks", end="\r", flush=True)
    elapsed = time.perf_counter() - started
    print(f"  embedded {len(vectors)}/{len(chunks)} chunks in {elapsed:.1f}s")
    return vectors


async def upsert_by_department(
    store: VectorStore, chunks: list[Chunk], vectors: list[list[float]]
) -> dict[str, int]:
    """Group vectors by department namespace and upsert each group."""
    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for chunk, vector in zip(chunks, vectors):
        grouped[chunk.meta.department].append(
            {"id": chunk.chunk_id, "values": vector, "metadata": chunk.to_metadata()}
        )

    written: dict[str, int] = {}
    for namespace, payload in grouped.items():
        written[namespace] = await store.upsert(payload, namespace=namespace)
        print(f"  upserted {written[namespace]:>4} vectors -> namespace '{namespace}'")
    return written


def build_sparse_index(chunks: list[Chunk]) -> None:
    """Build and persist the BM25 index."""
    index = SparseIndex.build(
        chunk_ids=[c.chunk_id for c in chunks],
        texts=[c.text for c in chunks],
        metadata=[c.to_metadata() for c in chunks],
    )
    index.save()


async def main_async(args: argparse.Namespace) -> int:
    configure_logging()

    print("\n[1/4] Loading and chunking documents")
    chunks = load_chunks(args.documents, args.limit)

    by_department: dict[str, int] = defaultdict(int)
    for chunk in chunks:
        by_department[chunk.meta.department] += 1
    for department, count in sorted(by_department.items()):
        print(f"  {department:<18} {count} chunks")

    if args.dry_run:
        print("\nDry run: stopping before embedding. No network calls made.")
        return 0

    print("\n[2/4] Embedding chunks locally (first run downloads the model)")
    vectors = await embed_all(chunks)

    print("\n[3/4] Upserting to Pinecone")
    try:
        store = VectorStore()
        await store.ensure_index()
        await upsert_by_department(store, chunks, vectors)
        stats = await store.describe()
        print(f"  index now holds {stats.get('total_vector_count', '?')} vectors")
    except RetrievalError as exc:
        print(f"\nPinecone step failed: {exc}")
        print("The BM25 index will still be built, so keyword search keeps working.")
        build_sparse_index(chunks)
        return 1

    print("\n[4/4] Building BM25 keyword index")
    build_sparse_index(chunks)

    print("\nIngestion complete.")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest documents into Pinecone and BM25.")
    parser.add_argument("--documents", type=Path, default=DOCUMENTS_DIR)
    parser.add_argument("--limit", type=int, default=None, help="ingest only the first N documents")
    parser.add_argument("--dry-run", action="store_true", help="chunk and report only")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(main_async(args)))


if __name__ == "__main__":
    main()
