"""Hybrid retrieval: dense (Qdrant) + sparse (BM25), fused with Reciprocal Rank Fusion.

Why hybrid
----------
Dense retrieval matches meaning and blurs exact tokens. Ask for the document
code `SOP-CS-011` and a pure vector search happily returns SOP-CS-004 and
SOP-CS-015 as well - they are semantically adjacent procedures, and to an
embedding model the codes look nearly identical. BM25 has the opposite
behaviour: it treats `SOP-CS-011` as a rare term and locks onto it, while
missing a paraphrased question that shares no vocabulary with the source.

Neither is sufficient alone. RRF combines their rankings.

Reciprocal Rank Fusion
----------------------
    score(d) = SUM over retrievers i of  1 / (k + rank_i(d)),   k = 60

Implemented here by hand rather than called from a library, because the point is
to understand it:

- It fuses **ranks, not scores**. A cosine similarity of 0.83 and a BM25 score of
  14.2 are not comparable - different scales, different distributions, and BM25
  scores are unbounded. Ranks are directly comparable, so no normalisation step
  is needed and none can go wrong.
- `k` damps the influence of top ranks. With k=60, rank 1 contributes 1/61 and
  rank 2 contributes 1/62 - a small gap. Without k (or with k=0) rank 1 would
  contribute 1.0 and rank 2 only 0.5, letting a single retriever's top hit
  dominate the fusion. k=60 is the value from the original Cormack et al. paper
  and the course material.
- A document found by **both** retrievers accumulates two reciprocal terms, so
  agreement is rewarded structurally rather than by a tuned weight.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache

from rank_bm25 import BM25Okapi

from config.settings import settings
from src.rag.chunker import Chunk, chunk_corpus
from src.rag import embedder, vector_store

# Split on non-alphanumerics but keep intra-token hyphens and underscores, so
# "SOP-CS-011" and "JAM_BRIDGE_L3" survive as single terms. Splitting those
# apart is exactly what destroys BM25's advantage on exact codes.
_TOKEN_RE = re.compile(r"[A-Za-z0-9_\-]+|[؀-ۿ]+")


def tokenize(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN_RE.findall(text)]


@dataclass
class RetrievedChunk:
    chunk_id: str
    payload: dict
    dense_rank: int | None = None
    dense_score: float | None = None
    bm25_rank: int | None = None
    bm25_score: float | None = None
    fused_score: float = 0.0
    rerank_score: float | None = None
    final_rank: int | None = None

    @property
    def text(self) -> str:
        return self.payload["text"]

    @property
    def doc_code(self) -> str:
        return self.payload["doc_code"]

    @property
    def section(self) -> str:
        return self.payload.get("section_heading", "")


@lru_cache(maxsize=1)
def _corpus() -> tuple[list[Chunk], BM25Okapi]:
    """BM25 is built over the SAME chunk set that was embedded.

    If the two indexes ever drift apart, RRF fuses rankings over different
    document sets and the result is quietly meaningless.
    """
    chunks = chunk_corpus()
    bm25 = BM25Okapi([tokenize(c.text) for c in chunks])
    return chunks, bm25


def dense_search(query: str, top_k: int) -> list[dict]:
    vector = embedder.embed_query(query)
    return vector_store.search(vector, top_k)


def bm25_search(query: str, top_k: int) -> list[dict]:
    chunks, bm25 = _corpus()
    scores = bm25.get_scores(tokenize(query))
    ranked = sorted(enumerate(scores), key=lambda p: p[1], reverse=True)[:top_k]
    return [
        {"chunk_id": chunks[i].chunk_id, "score": float(score),
         "payload": chunks[i].to_payload()}
        for i, score in ranked
    ]


def reciprocal_rank_fusion(
    ranked_lists: list[list[dict]],
    k: int = 60,
) -> dict[str, float]:
    """RRF over any number of ranked lists.

    score(d) = SUM_i 1 / (k + rank_i(d)), with rank starting at 1.

    Documents absent from a list simply contribute nothing from that list -
    there is no penalty term and no imputation, which is part of why RRF is
    robust to retrievers that return different numbers of results.
    """
    fused: dict[str, float] = {}
    for ranked in ranked_lists:
        for zero_based, hit in enumerate(ranked):
            rank = zero_based + 1
            fused[hit["chunk_id"]] = fused.get(hit["chunk_id"], 0.0) + 1.0 / (k + rank)
    return fused


@dataclass
class RetrievalTrace:
    query: str
    dense: list[dict] = field(default_factory=list)
    bm25: list[dict] = field(default_factory=list)
    fused: list[RetrievedChunk] = field(default_factory=list)


def hybrid_search(query: str, top_k: int | None = None) -> tuple[list[RetrievedChunk], RetrievalTrace]:
    """Dense top-k + BM25 top-k, fused by RRF. Returns fused results and a trace."""
    top_k = top_k or settings.retrieve_top_k

    dense = dense_search(query, top_k)
    sparse = bm25_search(query, top_k)
    fused_scores = reciprocal_rank_fusion([dense, sparse], k=settings.rrf_k)

    dense_rank = {h["chunk_id"]: i + 1 for i, h in enumerate(dense)}
    dense_score = {h["chunk_id"]: h["score"] for h in dense}
    bm25_rank = {h["chunk_id"]: i + 1 for i, h in enumerate(sparse)}
    bm25_score = {h["chunk_id"]: h["score"] for h in sparse}
    payloads = {h["chunk_id"]: h["payload"] for h in [*dense, *sparse]}

    results = [
        RetrievedChunk(
            chunk_id=chunk_id,
            payload=payloads[chunk_id],
            dense_rank=dense_rank.get(chunk_id),
            dense_score=dense_score.get(chunk_id),
            bm25_rank=bm25_rank.get(chunk_id),
            bm25_score=bm25_score.get(chunk_id),
            fused_score=score,
        )
        for chunk_id, score in sorted(fused_scores.items(), key=lambda p: p[1], reverse=True)
    ]
    for i, result in enumerate(results):
        result.final_rank = i + 1

    return results, RetrievalTrace(query=query, dense=dense, bm25=sparse, fused=results)
