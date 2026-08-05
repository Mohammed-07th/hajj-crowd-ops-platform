"""Build the RAG index: chunk -> embed -> Qdrant.

Idempotent by construction: the collection is recreated and every chunk is
re-upserted, so running this twice produces the same index rather than a
duplicated one. Embeddings come from the content-hash cache, so the second run
costs no model time.
"""

from __future__ import annotations

import json
import sys

from src.lineage.emitter import lineage_run
from src.rag import embedder, vector_store
from src.rag.chunker import chunk_corpus


def build_index() -> dict:
    with lineage_run(
        "refresh_rag_index",
        inputs=["data/sop"],
        outputs=["qdrant://hajj_sop_v1"],
    ) as run:
        chunks = chunk_corpus()
        vectors = embedder.embed_passages([c.text for c in chunks])

        vector_store.recreate_collection()
        n = vector_store.upsert_chunks(chunks, vectors)
        run.record_output_rows("qdrant://hajj_sop_v1", n)

        info = vector_store.collection_info()

    tokens = [c.token_count for c in chunks]
    return {
        "documents": len({c.doc_code for c in chunks}),
        "chunks": len(chunks),
        "token_min": min(tokens),
        "token_max": max(tokens),
        "token_mean": round(sum(tokens) / len(tokens), 1),
        **info,
        **embedder.cache_stats(),
    }


def main() -> int:
    result = build_index()
    print(json.dumps(result, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
