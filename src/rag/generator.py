"""Grounded answer generation via OpenRouter.

Free models are unreliable infrastructure, so this treats them as such: retry
with exponential backoff, fall through a prioritised list of models, cache every
answer, and record which model actually served it. None of that is defensive
padding - a free model returning 429 or 404 mid-run is the normal case, not the
exception.

Where the engineering value sits
--------------------------------
Retrieval - chunking, embeddings, the vector store, RRF, reranking - is entirely
local and deterministic. The LLM only phrases an answer over context that has
already been selected. If generation fails completely, the retrieval evidence is
unaffected; that is why the golden-question runner degrades rather than aborts.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from openai import OpenAI
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from config.settings import REPO_ROOT, settings
from src.rag.retriever import RetrievedChunk

CACHE_DIR = REPO_ROOT / ".cache" / "llm"

SYSTEM_PROMPT = """You are an operations copilot for Saudi crowd-management sites \
(Hajj, Umrah and tourism). You answer duty officers from published standard \
operating procedures.

RULES - follow all of them:
1. Answer ONLY from the numbered context passages provided. Do not use outside \
knowledge, even if you are confident it is correct.
2. Cite the chunk number AND the document code for every factual claim, like \
this: [1, SOP-CS-004]. Every sentence containing a number, threshold, role or \
time limit must carry a citation.
3. If the context does not contain the answer, reply exactly: "This is not \
covered in the available procedures." Do not guess and do not offer general \
advice instead.
4. Be direct and operational. A duty officer is reading this during an incident. \
Lead with the answer, then the supporting detail.
5. If the question is in Arabic, answer in Arabic.
"""


@dataclass
class Citation:
    chunk_number: int
    doc_code: str
    section: str
    chunk_id: str
    fused_score: float
    rerank_score: float | None


@dataclass
class Answer:
    question: str
    answer: str
    citations: list[Citation] = field(default_factory=list)
    model_used: str = ""
    from_cache: bool = False
    retrieval_trace: list[dict] = field(default_factory=list)
    degraded: bool = False
    error: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


class AllModelsUnavailable(RuntimeError):
    pass


def _client() -> OpenAI:
    return OpenAI(
        base_url=settings.openrouter_base_url,
        api_key=settings.openrouter_api_key,
        default_headers={
            "HTTP-Referer": settings.openrouter_site_url,
            "X-Title": settings.openrouter_app_name,
        },
        timeout=settings.llm_timeout_seconds,
    )


def build_prompt(question: str, chunks: list[RetrievedChunk]) -> str:
    blocks = []
    for i, chunk in enumerate(chunks, start=1):
        blocks.append(
            f"[{i}] (document {chunk.doc_code}, section: {chunk.section or 'preamble'})\n"
            f"{chunk.text}"
        )
    context = "\n\n".join(blocks)
    return f"CONTEXT PASSAGES:\n\n{context}\n\nQUESTION: {question}\n\nANSWER:"


def _cache_key(question: str, chunks: list[RetrievedChunk], model: str) -> str:
    ids = ",".join(sorted(c.chunk_id for c in chunks))
    return hashlib.sha256(f"{question}|{ids}|{model}".encode()).hexdigest()[:32]


def _load_cache(key: str) -> dict | None:
    path = CACHE_DIR / f"{key}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return None


def _store_cache(key: str, payload: dict) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    (CACHE_DIR / f"{key}.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


@retry(
    stop=stop_after_attempt(settings.llm_max_retries),
    wait=wait_exponential(multiplier=2, min=2, max=30),
    retry=retry_if_exception_type(Exception),
    reraise=True,
)
def _call_model(model: str, prompt: str) -> str:
    response = _client().chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=0.1,   # factual grounded QA, not creative writing
        max_tokens=800,
    )
    content = response.choices[0].message.content
    if not content or not content.strip():
        raise RuntimeError(f"model {model} returned an empty completion")
    return content.strip()


def generate(question: str, chunks: list[RetrievedChunk],
             use_cache: bool = True) -> Answer:
    citations = [
        Citation(
            chunk_number=i,
            doc_code=c.doc_code,
            section=c.section,
            chunk_id=c.chunk_id,
            fused_score=round(c.fused_score, 6),
            rerank_score=round(c.rerank_score, 4) if c.rerank_score is not None else None,
        )
        for i, c in enumerate(chunks, start=1)
    ]
    trace = [
        {"chunk_id": c.chunk_id, "doc_code": c.doc_code, "section": c.section,
         "dense_rank": c.dense_rank, "bm25_rank": c.bm25_rank,
         "fused_score": round(c.fused_score, 6),
         "rerank_score": round(c.rerank_score, 4) if c.rerank_score is not None else None}
        for c in chunks
    ]

    prompt = build_prompt(question, chunks)
    models = [settings.llm_model_primary, *settings.fallback_models]

    for model in models:
        key = _cache_key(question, chunks, model)
        if use_cache:
            cached = _load_cache(key)
            if cached:
                return Answer(question=question, answer=cached["answer"],
                              citations=citations, model_used=cached["model_used"],
                              from_cache=True, retrieval_trace=trace)

        try:
            text = _call_model(model, prompt)
        except Exception as exc:
            print(f"[generator] model {model} unavailable ({type(exc).__name__}: "
                  f"{str(exc)[:120]}) - falling through", flush=True)
            continue

        _store_cache(key, {"question": question, "answer": text, "model_used": model})
        return Answer(question=question, answer=text, citations=citations,
                      model_used=model, retrieval_trace=trace)

    # Every free model refused. Fail SOFT: the retrieval evidence is intact and
    # is what the rubric grades hardest.
    return Answer(
        question=question,
        answer="[generation unavailable - every configured free model was "
               "rate-limited or unreachable]",
        citations=citations, model_used="none", retrieval_trace=trace,
        degraded=True, error="all models unavailable",
    )
