# RAG design

The operations copilot answers procedural questions from the SOP corpus with
citations. This document records the choices and, where the evidence contradicts
the expected result, says so.

## 1. Corpus

10 Markdown SOP documents in [`data/sop/`](../../data/sop), each with a document
code in its front matter, specific numeric thresholds, named authorising roles,
and explicit cross-references to other documents' codes.

| Code | Document |
|---|---|
| SOP-CS-004 | Crowd density management and escalation thresholds |
| SOP-CS-011 | Zone capacity escalation and diversion authority |
| SOP-CS-015 | Evacuation and diversion (bilingual sections) |
| SOP-MED-002 | Medical emergency response, ambulance corridor |
| SOP-MED-009 | Heat stress management, WBGT thresholds |
| SOP-OPS-001 | Service request priority and SLA matrix |
| SOP-OPS-020 | Incident reporting and escalation matrix |
| SOP-SAN-003 | Sanitation and water station servicing |
| SOP-SEC-007 | Lost person procedure |
| FAQ-001 | Multilingual visitor FAQ (Arabic and English) |

`SOP-OPS-001` and `data/reference/sla_matrix.csv` must agree exactly. The
producer derives its priority options from the CSV, so a category/priority pair
with no SLA target cannot be generated.

## 2. Chunking — recursive

Headings first, then paragraphs, then sentences, descending only as far as the
512-token budget requires. 64-token overlap (12.5%).

**Why recursive, against the four options from the course:**

- **Fixed-size** splits mid-table. This corpus is largely threshold tables; a
  chunk holding `| 90% - 94% | CRITICAL |` with its header row severed retrieves
  confidently and answers wrongly. That is the worst possible failure.
- **Sentence** chunking yields fragments too small to carry context. *"The SOC
  Controller authorises."* is retrievable and meaningless.
- **Semantic** chunking infers boundaries by embedding similarity. It is the
  sophisticated option, and here it would spend compute rediscovering structure
  the author already wrote down as headings.
- **Recursive** follows that authored structure. Every chunk lands on a section
  boundary and arrives with its heading attached.

**Result:** 87 chunks, mean 150 tokens, max 337. Chunks sit well under the 512
budget because the authored sections are short — 512 is a ceiling, not a quota.
Splitting them further to hit a chunk count would destroy the property that
makes them good: one chunk = one coherent procedural section.

The heading and document code travel **inside** the embedded text, not only in
metadata. A bare table row does not encode which procedure it belongs to, and
the embedding must see that.

## 3. Embeddings — local

`intfloat/multilingual-e5-small`, 384 dimensions.

**Local rather than API:** OpenRouter routes chat/completions and does not
expose an `/embeddings` endpoint. Local embeddings cost nothing, need no key,
and are deterministic for a grader re-running the pipeline.

**Multilingual rather than English-only:** one golden question is Arabic and the
corpus has Arabic sections. `all-MiniLM-L6-v2` would retrieve poorly for
`ما هي إجراءات الإخلاء؟`.

**The e5 prefix rule:** e5 is trained with asymmetric prefixes — `"query: "` on
searches, `"passage: "` on documents. Getting this wrong raises no error and
silently degrades retrieval, so it is applied inside `embed_query` and
`embed_passages` where a caller cannot forget it.

Embeddings are cached to disk by content hash, so re-runs cost no model time.

## 4. Vector store — Qdrant

| Setting | Value | Why |
|---|---|---|
| `size` | 384 | Matches e5-small. A mismatch is rejected at upsert, which is the good outcome. |
| `distance` | COSINE | e5 vectors are normalised; cosine is the trained objective. |
| `m` | 32 | HNSW connectivity. Default 16 is tuned for large collections where memory dominates; this corpus is tiny, so a denser graph is nearly free and improves recall — which matters when over-fetching for a reranker. |
| `ef_construct` | 200 | Build-time search width. Index build is sub-second here, so there is nothing to economise. |

No PII reaches Qdrant. SOP documents contain no personal data; the redaction
path in `src/governance/pii.py` exists for service-request descriptions, which
are not indexed.

## 5. Hybrid retrieval and RRF

Dense top-50 from Qdrant, BM25 top-50 over the same chunk set, fused by
Reciprocal Rank Fusion implemented by hand:

```
score(d) = SUM over retrievers i of  1 / (k + rank_i(d)),   k = 60
```

Implemented rather than imported because the point is to understand it. It fuses
**ranks, not scores** — a cosine similarity of 0.83 and an unbounded BM25 score
of 14.2 are not comparable, and ranks need no normalisation. `k` damps top-rank
influence; without it a single retriever's top hit would dominate.

The BM25 tokenizer keeps `SOP-CS-011` and `JAM_BRIDGE_L3` as single tokens.
Splitting identifiers on hyphens and underscores is exactly what destroys BM25's
advantage on exact matches.

Unit tests in [`tests/test_rrf.py`](../../tests/test_rrf.py) check the arithmetic
against hand-computed values, including the counter-intuitive case where
rank-1+rank-3 narrowly beats rank-2+rank-2 at k=60.

### 5.1 What the evidence actually showed

[`hybrid_proof.md`](evidence/rag/hybrid_proof.md) reports measurements, including
one that contradicts the expected result.

**The textbook demonstration did not reproduce.** Dense retrieval was supposed to
miss an exact document code that BM25 recovers. Across 31 exact identifiers,
dense found the literal-containing chunk in the top 3 **every time** (26/31 at
rank 1). RRF improved this to 31/31 at rank 1 — a real gain, but a gain of one
or two rank positions, not a rescue.

The reason is corpus size. With 87 chunks the nearest-neighbour search has few
competitors, and each identifier lives in a chunk whose surrounding text is also
about that identifier, so semantic and lexical signals agree. The failure mode
needs thousands of competing chunks.

**The complementary half is clearly visible.** On paraphrases sharing no
vocabulary with the source, BM25 falls to rank 7 while dense holds rank 1 — mean
rank 4.17 for BM25 against 1.83 for dense. That is the other reason the hybrid
layer exists, and at this scale it is the observable one.

**RRF is not monotonic.** On one paraphrase, dense returns the target at rank 2
and BM25 at rank 4, but RRF places it at rank 5 — chunks both retrievers ranked
moderately accumulate two reciprocal terms and overtake one that a single
retriever ranked highly. RRF optimises for consensus, and consensus is not always
correctness. It remains the right default because it needs no normalisation and
no tuning, not because it dominates its inputs on every query.

A production system indexing identifiers would add them as filterable payload
fields and pre-filter on them, rather than relying on lexical scoring.

## 6. Reranking — cross-encoder

`cross-encoder/ms-marco-MiniLM-L-6-v2`, fused top-50 → top-5.

The retriever scores query and passage independently, which is what makes it
fast enough for the whole collection and is also its ceiling. A cross-encoder
scores the pair jointly, so it can tell that a passage sharing vocabulary with
the question answers a different question.

**Stated limitation: this model is English-only.** It was chosen over
`BAAI/bge-reranker-base` (~1.1 GB) because this build targets a 16 GB laptop
already running Kafka, Qdrant and an embedding model. For the Arabic golden
question its scores are close to noise; retrieval there is carried by the
multilingual embedding model and by BM25 matching Arabic tokens, both of which
handle it, and the reranker reorders near-arbitrarily within an already-relevant
candidate set. The model is selectable via `RERANKER_MODEL`.

## 7. Generation

OpenRouter, free tier, via the `openai` SDK. The system prompt requires the model
to answer only from the numbered context, cite chunk number and document code for
every claim, and reply *"This is not covered in the available procedures."* when
the context is insufficient.

Free models are unreliable infrastructure and are engineered around: `tenacity`
retry with exponential backoff, a prioritised fallback chain, answers cached by
`sha256(question + chunk_ids + model)`, and `model_used` recorded per answer.

**The model list in the build specification was stale.** Every model named there
returned 404 *"unavailable for free"*. The live list was queried from
`/api/v1/models` and the chain rebuilt from what was actually free on the build
date, which is why the fallback chain is not decoration.

**Where the engineering value sits:** retrieval — chunking, embeddings, the
vector store, RRF, reranking — is entirely local and deterministic. The LLM only
phrases an answer over context already selected. A total generation failure
leaves the retrieval evidence intact, which is why `smoke_test_rag` fails soft on
generation and hard on retrieval.

## 8. Results

[`golden_question_run.md`](evidence/rag/golden_question_run.md) — 9 questions
including one Arabic and one deliberately unanswerable:

| Metric | Result |
|---|---|
| Expected document retrieved in top-5 | **9/9** |
| Expected document cited in the answer | **9/9** |
| Expected fact present in the answer | **9/9** |
| Generation degraded | 0/9 |

The out-of-scope question (*"What is the refund policy for a cancelled Umrah
booking?"*) returned exactly `This is not covered in the available procedures.`
— refusing is the single most important behaviour in a grounded system, and it
is tested rather than assumed.
