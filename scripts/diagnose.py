"""Find out exactly where retrieval is returning nothing.

Checks each layer in isolation, from the bottom up, and stops at the first one
that fails. Run this whenever a question that should match returns no evidence.

Usage:
    python scripts/diagnose.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.auth.roles import authenticate, access_filter  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.core.logging import configure_logging  # noqa: E402

QUERY = "connection pool exhaustion incident"
OK, BAD = "  [ok]  ", "  [FAIL]"


async def main() -> None:
    configure_logging()
    print("\n" + "=" * 72)
    print("RETRIEVAL DIAGNOSIS")
    print("=" * 72)

    # --- 1. corpus on disk -------------------------------------------
    print("\n1. Documents on disk")
    docs = sorted(Path("data/documents").glob("*.md"))
    print(f"{OK if docs else BAD} {len(docs)} markdown files")
    if not docs:
        print("     -> run: python scripts/generate_documents.py")
        return

    # --- 2. chunking --------------------------------------------------
    print("\n2. Chunking")
    from app.retrieval.chunking import chunk_document

    chunks = []
    for path in docs:
        chunks.extend(chunk_document(path.read_text(encoding="utf-8")))
    matching = [c for c in chunks if "connection pool" in c.text.lower()]
    print(f"{OK} {len(chunks)} chunks")
    print(f"{OK if matching else BAD} {len(matching)} chunks mention 'connection pool'")
    if matching:
        c = matching[0]
        print(f"     e.g. {c.chunk_id}  access_level={c.meta.access_level}  dept={c.meta.department}")

    # --- 3. BM25 index -------------------------------------------------
    print("\n3. BM25 sparse index")
    from app.retrieval.sparse import SparseIndex

    try:
        sparse = SparseIndex.load()
        print(f"{OK} index loaded")
    except Exception as exc:
        print(f"{BAD} could not load: {type(exc).__name__}: {exc}")
        print("     -> run: python scripts/ingest.py")
        sparse = None

    if sparse:
        raw = sparse.search(QUERY, top_k=5)
        print(f"{OK if raw else BAD} {len(raw)} hits with NO filters")
        for h in raw[:3]:
            print(f"     {h.chunk_id:<22} score={h.score:.2f}  access={h.metadata.get('access_level')}")

        for user_id in ("vihanga", "amara"):
            user = authenticate(user_id)
            hits = sparse.search(QUERY, top_k=5, allowed_access_levels=user.allowed_access_values())
            flag = OK if hits else BAD
            print(f"{flag} {len(hits)} hits as {user_id} ({user.role.value})")

    # --- 4. embeddings --------------------------------------------------
    print("\n4. Embedding model")
    try:
        from app.retrieval.embeddings import embed_query

        vector = await embed_query(QUERY)
        good = len(vector) == settings.embedding_dimension
        print(f"{OK if good else BAD} query vector length {len(vector)} "
              f"(config expects {settings.embedding_dimension})")
    except Exception as exc:
        print(f"{BAD} {type(exc).__name__}: {exc}")
        return

    # --- 5. Pinecone ------------------------------------------------------
    print("\n5. Pinecone index")
    from app.retrieval.vector_store import VectorStore

    try:
        store = VectorStore()
        await store.ensure_index()
        stats = await store.describe()
    except Exception as exc:
        print(f"{BAD} {type(exc).__name__}: {exc}")
        return

    total = stats.get("total_vector_count", 0)
    dim = stats.get("dimension")
    print(f"{OK if total else BAD} total vectors: {total}")
    print(f"{OK if dim == settings.embedding_dimension else BAD} index dimension: {dim} "
          f"(config expects {settings.embedding_dimension})")

    namespaces = stats.get("namespaces", {}) or {}
    if namespaces:
        for name, info in sorted(namespaces.items()):
            label = repr(name) if name == "" else name
            print(f"     namespace {label:<20} {info.get('vector_count', 0)} vectors")
    else:
        print(f"{BAD} no namespaces reported -- nothing was upserted")
        print("     -> run: python scripts/ingest.py")
        return

    # --- 6. dense query, filters off then on -------------------------------
    print("\n6. Dense search")
    raw_hits = await store.query_many(vector, top_k=5, namespaces=list(namespaces.keys()))
    print(f"{OK if raw_hits else BAD} {len(raw_hits)} hits with NO filter")
    for h in raw_hits[:3]:
        print(f"     {h.chunk_id:<22} score={h.score:.3f}  access={h.access_level}")

    for user_id in ("vihanga", "amara"):
        user = authenticate(user_id)
        f = access_filter(user)
        hits = await store.query_many(vector, top_k=5, namespaces=list(namespaces.keys()),
                                      metadata_filter=f)
        print(f"{OK if hits else BAD} {len(hits)} hits as {user_id} with filter {f}")

    # --- 7. the full hybrid path --------------------------------------------
    print("\n7. Full hybrid retriever")
    from app.retrieval.hybrid import HybridRetriever, RetrievalQuery

    retriever = await HybridRetriever.create()
    for user_id in ("vihanga", "amara"):
        user = authenticate(user_id)
        try:
            hits = await retriever.search(RetrievalQuery(text=QUERY, user=user, top_k=5))
            print(f"{OK} {len(hits)} fused hits as {user_id}")
            for h in hits[:3]:
                print(f"     {h.doc_id:<16} [{h.found_by:<6}] rrf={h.score:.5f}")
        except Exception as exc:
            print(f"{BAD} as {user_id}: {type(exc).__name__}: {exc}")

    print("\n" + "=" * 72)
    print("Read from the top: the FIRST [FAIL] is the real problem.")
    print("=" * 72 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
