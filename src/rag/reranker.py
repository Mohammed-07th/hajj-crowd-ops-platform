"""Cross-encoder reranking, fused top-50 -> top-5.

Why a second stage at all
-------------------------
The retrieval stage scores the query and each chunk *independently* - the
embedding of the question never sees the embedding of the passage. That is what
makes it fast enough to run over the whole collection, and it is also its
ceiling: a bi-encoder cannot notice that a passage answers a different question
that happens to use the same vocabulary.

A cross-encoder scores the (query, passage) pair jointly in one forward pass, so
it can. It is far too slow to run over a whole corpus, which is exactly why it
runs last, over 50 candidates rather than 86 chunks - and would still be the
right shape at 86,000.

Model choice
------------
`cross-encoder/ms-marco-MiniLM-L-6-v2` (~90 MB) rather than
`BAAI/bge-reranker-base` (~1.1 GB), because this build targets a 16 GB fanless
laptop already running Kafka, Qdrant and an embedding model.

**Known limitation, stated plainly: ms-marco-MiniLM-L-6-v2 is English-only.**
It was trained on English MS MARCO and has no meaningful Arabic capability, so
for the Arabic golden question (`ما هي إجراءات الإخلاء؟`) its scores are close
to noise. Retrieval for that question is carried by the multilingual embedding
model and by BM25 matching the Arabic tokens - both of which handle it - and the
reranker neither helps nor actively harms, it simply reorders near-arbitrarily
within an already-relevant candidate set. The model is selectable by env var
(`RERANKER_MODEL`); setting it to `BAAI/bge-reranker-base` restores multilingual
reranking on a machine with the memory to spare.
"""

from __future__ import annotations

from config.settings import settings
from src.rag.retriever import RetrievedChunk

_model = None


class Reranker:
    """Single interface so the model is swappable by configuration."""

    def __init__(self, model_name: str | None = None) -> None:
        self.model_name = model_name or settings.reranker_model

    def _get_model(self):
        global _model
        if _model is None:
            from sentence_transformers import CrossEncoder
            print(f"[reranker] loading {self.model_name} ...", flush=True)
            _model = CrossEncoder(self.model_name)
        return _model

    def rerank(self, query: str, candidates: list[RetrievedChunk],
               top_k: int | None = None) -> list[RetrievedChunk]:
        top_k = top_k or settings.rerank_top_k
        if not candidates:
            return []

        model = self._get_model()
        pairs = [(query, c.text) for c in candidates]
        scores = model.predict(pairs)

        for candidate, score in zip(candidates, scores):
            candidate.rerank_score = float(score)

        reranked = sorted(candidates, key=lambda c: c.rerank_score, reverse=True)[:top_k]
        for i, candidate in enumerate(reranked):
            candidate.final_rank = i + 1
        return reranked


def rerank(query: str, candidates: list[RetrievedChunk],
           top_k: int | None = None) -> list[RetrievedChunk]:
    return Reranker().rerank(query, candidates, top_k)
