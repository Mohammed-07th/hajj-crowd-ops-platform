"""Qdrant vector store.

Collection configuration and why
--------------------------------
- `size=384` - matches multilingual-e5-small. A mismatch here is rejected by
  Qdrant at upsert, which is the good outcome; the bad outcome is a silently
  truncated vector.
- `distance=COSINE` - e5 vectors are normalised, so cosine is the trained
  objective. Using Euclidean on normalised vectors gives a monotonically related
  but differently-scaled ranking, which corrupts RRF's rank inputs less than it
  corrupts score thresholds - but there is no reason to accept either.
- `m=32` - HNSW graph connectivity. The default 16 is tuned for large
  collections where memory dominates. This corpus is small (under 100 vectors),
  so a denser graph costs almost nothing and improves recall on the neighbour
  search, which matters because retrieval feeding a reranker should over-fetch.
- `ef_construct=200` - build-time search width. Higher gives a better-quality
  graph at index time. For a corpus this size the build takes under a second, so
  there is no reason to economise.

PII never reaches this store. Chunk text comes from SOP documents, which contain
no personal data; the redaction path in src/governance/pii.py exists for the
service-request descriptions, which are not indexed here.
"""

from __future__ import annotations

import numpy as np
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, HnswConfigDiff, PointStruct, VectorParams

from config.settings import settings
from src.rag.chunker import Chunk

HNSW_M = 32
HNSW_EF_CONSTRUCT = 200


def get_client() -> QdrantClient:
    return QdrantClient(url=settings.qdrant_url)


def recreate_collection(client: QdrantClient | None = None) -> None:
    client = client or get_client()
    name = settings.qdrant_collection
    if client.collection_exists(name):
        client.delete_collection(name)
    client.create_collection(
        collection_name=name,
        vectors_config=VectorParams(
            size=settings.embedding_dim,
            distance=Distance.COSINE,
        ),
        hnsw_config=HnswConfigDiff(m=HNSW_M, ef_construct=HNSW_EF_CONSTRUCT),
    )


def upsert_chunks(chunks: list[Chunk], vectors: np.ndarray,
                  client: QdrantClient | None = None) -> int:
    client = client or get_client()
    points = [
        PointStruct(
            id=i,
            vector=vector.tolist(),
            payload=chunk.to_payload(),
        )
        for i, (chunk, vector) in enumerate(zip(chunks, vectors))
    ]
    client.upsert(collection_name=settings.qdrant_collection, points=points, wait=True)
    return len(points)


def search(query_vector: np.ndarray, top_k: int,
           client: QdrantClient | None = None) -> list[dict]:
    client = client or get_client()
    hits = client.query_points(
        collection_name=settings.qdrant_collection,
        query=query_vector.tolist(),
        limit=top_k,
        with_payload=True,
    ).points
    return [{"chunk_id": h.payload["chunk_id"], "score": h.score, "payload": h.payload}
            for h in hits]


def collection_info(client: QdrantClient | None = None) -> dict:
    client = client or get_client()
    info = client.get_collection(settings.qdrant_collection)
    params = info.config.params.vectors
    return {
        "collection": settings.qdrant_collection,
        "points": info.points_count,
        "vector_size": params.size,
        "distance": str(params.distance),
        "hnsw_m": info.config.hnsw_config.m,
        "hnsw_ef_construct": info.config.hnsw_config.ef_construct,
    }
