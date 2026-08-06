# Presentation demo script

A 15-minute live demo, in order. Each step has **what to say**, **the command**,
and **what the output proves**. Run every command from the project root.

---

## Before you start (5 minutes before presenting)

```bash
cd /Users/mohammed/codes/hajj-crowd-ops-platform
colima start                 # only if you rebooted
make up                      # kafka + qdrant
make airflow                 # leave running in its own terminal tab
```

Warm the models so your first live question isn't a 20-second silence:

```bash
make ask Q="What is the response-time SLA for a P1 medical request?"
```

Open two terminal tabs and one browser tab:
- **Tab 1** — where you run demo commands
- **Tab 2** — Airflow running (`make airflow`)
- **Browser** — http://localhost:8080 (admin / admin), already logged in

---

## Step 0 — The 30-second pitch

> "Saudi crowd-management authorities run high-density sites: the Mataf, the
> Jamarat bridge, Mina, Arafat. Sensors report zone occupancy every few seconds,
> and field staff raise service requests that run through a lifecycle.
>
> When a zone hits 90% capacity at 2am, the duty officer needs to know who
> authorises diversion — from the actual standard operating procedure, with a
> citation, not from memory.
>
> This platform does both halves: a Kafka-to-Delta lakehouse that makes the
> occupancy history answerable, and a retrieval copilot that answers procedural
> questions from the SOPs with citations."

**Say this immediately after:**

> "All the operational data is synthetic — I generated it. The place names are
> real; every number attached to them came from my generators. The SOP thresholds
> are informed by published standards like Fruin's crowd density bands and ISO
> 7243, and I cite them as that, never as official Saudi policy."

Getting the honesty in first is worth more than being asked for it later.

---

## Step 1 — The infrastructure is real, not simulated

> "The rubric says a simulation earns nothing, so the first thing I built was a
> check that fails the build if I ever cheat."

```bash
make audit
```

**Proves:** a real Kafka broker answering a real admin call, real `_delta_log`
directories on disk, all six required libraries importable, no queue standing in
for Kafka, no pandas standing in for Delta, `.env` untracked and no API key in
git history.

**Point at this line:** `AUDIT PASSED`

---

## Step 2 — The data contract rejects bad records (Deliverable 1)

> "Every message is validated at the ingestion boundary against a Pydantic
> contract in strict mode. Anything that fails goes to a dead-letter topic and to
> a queryable quarantine table, with the reason recorded."

```bash
PYTHONPATH=. .venv/bin/python scripts/demo_failures/demo_bad_records.py
```

**Proves:** 100 events in, 20 deliberately malformed, **80 accepted / 20
rejected**, every rejection carrying a machine-readable rule and a human-readable
reason.

**The line to stop on** — scroll to the bottom block:

```
The JSON string "1500" was refused for an integer field:
  rule   : int_type
  reason : entries: Input should be a valid integer
```

> "This is the one that matters. Without strict mode, Pydantic silently converts
> the string `"1500"` into the number 1500. Nothing errors. That is how corrupt
> data gets into a warehouse wearing a valid disguise — a sensor starts quoting
> its numbers and you find out six months later."

---

## Step 3 — The lakehouse, and the MERGE (Deliverable 2)

> "Bronze is raw and append-only. Silver is cleaned and deduplicated. Gold is
> aggregated. All real Delta tables."

```bash
PYTHONPATH=. .venv/bin/python -c "
from src.lakehouse import delta_io
for t in ['bronze_zone_occupancy','bronze_service_requests','silver_zone_occupancy','silver_service_requests','gold_zone_hourly','quarantine']:
    print(f'{t:26s} {delta_io.read(t).num_rows:>9,} rows')
"
```

Expected:

```
bronze_zone_occupancy        185,843 rows
bronze_service_requests       11,054 rows
silver_zone_occupancy        185,843 rows
silver_service_requests        2,500 rows
gold_zone_hourly               2,688 rows
quarantine                    14,971 rows
```

**The two numbers to point at:**

**11,054 → 2,500.** > "Service requests arrive once per state change, so one
request appears four to six times. The MERGE collapses them to one row per
request holding its *current* state. That's an upsert on a business key —
`request_id` — not an append."

**185,843 → 2,688.** > "Gold groups 185,000 sensor readings into one row per
zone per hour. 69 to 1. And it produces columns that don't exist upstream —
`minutes_above_90pct` is the number a duty officer acts on, and you can't read it
off any single sensor reading."

Show the gold table itself:

```bash
PYTHONPATH=. .venv/bin/python -c "
import polars as pl
from src.lakehouse import delta_io
g = pl.from_arrow(delta_io.read('gold_zone_hourly'))
print(g.group_by('zone_id').agg([
    pl.col('minutes_above_80pct').sum().round(1).alias('min_above_80'),
    pl.col('minutes_above_90pct').sum().round(1).alias('min_above_90'),
    pl.col('peak_utilization_pct').max().alias('peak_util_pct'),
]).sort('min_above_90', descending=True))
"
```

> "The Haram zones sustain high utilisation all week. Jamarat, Arafat and
> Muzdalifah spike only on their ritual days. The tourism sites never get close.
> That shape is deliberate — if the generator produced a flat line, every one of
> these numbers would be zero and the gold layer would look pointless."

---

## Step 4 — A bad write is actually refused (Deliverable 2)

> "The rubric asks for schema enforcement to be *demonstrated*, not claimed."

```bash
make schema-demo
```

**Proves two things in one run:**

1. A **breaking** change is refused — appending a text column where the table has
   integers raises `ValueError: Schema of data does not match table schema`.
2. An **additive** change is accepted — a genuinely new column succeeds under an
   explicit `schema_mode="merge"`.

> "Rejecting a breaking change and accepting an additive one are the same
> mechanism. Knowing the difference is the whole point."

**If asked about Part 1a** (it prints "ACCEPTED"): > "That's deliberate. delta-rs
has two write engines and they behave differently — the default one silently
casts the text to a number. That's the same silent-coercion failure my Pydantic
contract exists to prevent, so my pipeline writes through the strict engine
instead. I show both so the difference is on the record rather than something I
assert."

---

## Step 5 — The quality gate actually stops the pipeline (Deliverables 4 & 5)

This is the strongest thing you have. **Use the browser.**

Go to **http://localhost:8080** → `hajj_ops_pipeline` → **Graph** → select run
`gate2_failure_demo`.

> "Great Expectations runs as a gate between layers. When it fails, it raises,
> the Airflow task goes red, and everything downstream never executes."

Point at the graph:

| task | colour | state |
|---|---|---|
| validate_bronze | green | GATE 1 passed |
| **validate_silver** | **red** | GATE 2 failed |
| build_gold_zone_hourly | orange | `upstream_failed` |
| refresh_rag_index | orange | `upstream_failed` |
| smoke_test_rag | orange | `upstream_failed` |

Click `validate_silver` → **Logs**, and show the actual failure.

**Then answer the question before it's asked:**

> "You might expect corrupt data to fail a row-level check. It can't — the
> contract keeps bad records *out* of bronze entirely, they go to the DLQ. So
> what the gate actually catches is a **volume shortfall**: the run delivered a
> fraction of the expected rows. That's the volume pillar from Day 4, catching an
> upstream incident that per-row checks can't see."

Now show the healthy one — select run `final_green_run`: all 13 tasks green.

---

## Step 6 — The copilot answers with citations (Deliverable 3)

> "The retrieval side is where the engineering is. Chunking, embeddings, a real
> vector store, hybrid search, and reranking — all local and deterministic. The
> language model only phrases the final answer."

```bash
make ask Q="MATAF_01 has been above 90% for 12 minutes. Who authorizes diversion?"
```

**Point at:** the answer names the **SOC Controller**, and every claim carries
`[chunk number, document code]`.

> "I can verify that against the source document — SOP-CS-011's authority matrix
> says diversion at the CRITICAL band is authorised by the SOC Controller. The
> citation isn't decoration; it's what makes the answer checkable."

Then the multilingual one:

```bash
make ask Q="ما هي إجراءات الإخلاء؟"
```

> "The corpus and the question are Arabic. That's why I chose a multilingual
> embedding model — an English-only model retrieves badly here."

Then the most important one:

```bash
make ask Q="What is the refund policy for a cancelled Umrah booking?"
```

Output: `This is not covered in the available procedures.`

> "Refusing is the single most important behaviour in a grounded system. A model
> that invents a plausible policy is worse than useless to a duty officer."

---

## Step 7 — Hybrid search and RRF, in one slide

Open `docs/evidence/rag/hybrid_proof.md`.

> "Dense vector search matches meaning. BM25 matches exact keywords. I fuse their
> rankings with Reciprocal Rank Fusion, which I implemented by hand rather than
> importing — it's six lines and the formula is auditable."

```
score(d) = Σ  1 / (k + rank_i(d)),   k = 60
```

> "It fuses *ranks*, not scores — a cosine similarity of 0.83 and a BM25 score of
> 14.2 aren't comparable, but ranks are. And `k` damps the top ranks so one
> retriever's favourite can't dominate."

**Then be honest about the result** — this reads as strength if you own it:

> "The textbook demonstration is that dense search misses an exact document code
> and BM25 rescues it. I measured 31 identifiers and it didn't reproduce — dense
> found all of them in the top three, because with only 87 chunks there's almost
> no competition in the vector neighbourhood. What I *can* show is the opposite
> direction: on questions phrased with no shared vocabulary, BM25 drops to rank 7
> and dense carries it at rank 1. So I reported the negative result and
> demonstrated the half that's actually visible at this scale."

---

## Step 8 — Lineage and the final check

```bash
PYTHONPATH=. .venv/bin/python -c "
import json, collections
c = collections.Counter()
for line in open('docs/evidence/lineage/events.jsonl'):
    e = json.loads(line); c[e['eventType']] += 1
print(dict(c))
"
```

> "Every stage emits OpenLineage START before it reads and COMPLETE after it
> writes, with output row counts attached, and FAIL from the exception handler.
> It's a context manager, so instrumenting a stage costs one line and required
> zero changes to the pipeline logic."

Finish with:

```bash
PYTHONPATH=. .venv/bin/python scripts/rubric_selfcheck.py
```

> "65 checks against the actual repository state — files on disk, Delta
> transaction logs, the golden-question results, git history. Not against my
> memory of what I wrote."

---

## Likely questions, and honest answers

**"Where did the data come from?"**
> "I generated it. There is no public real-time Hajj crowd dataset — that
> telemetry is operationally sensitive. The rubric grades the pipeline, and every
> stage is proven with data I can regenerate deterministically from a seed. Here's
> the generator."

**"Why not Spark?"**
> "The rubric credits `deltalake` alongside `pyspark + delta-spark`. delta-rs is
> Rust, so there's no JVM in the stack — no Java dependency, no Spark startup
> failures on a laptop. The trade-off is real: this won't scale past one machine,
> and production Hajj volume would use Spark."

**"Why is there no Marquez UI?"**
> "The rubric asks for OpenLineage START/COMPLETE/FAIL events per stage, which is
> what I emit — through the official client, using its file transport instead of
> HTTP. Running Marquez plus Postgres wouldn't fit in a 5 GB Docker allocation
> alongside Kafka, Qdrant and two models on a 16 GB laptop."

**"Your reranker gave a negative score to the correct chunk."**
> "Yes — it's the 90 MB English-only cross-encoder, chosen to fit the memory
> budget. It's documented in RAG_DESIGN.md, and the model is swappable by
> environment variable. On a machine with headroom, `BAAI/bge-reranker-base`
> restores multilingual reranking."

**"How do I know you actually ran this?"**
> "`docs/evidence/` — real terminal logs, two Airflow screenshots, the lineage
> event stream, the golden-question results, and an executed notebook with all
> 14 cells' output saved."

---

## If something breaks live

- **Copilot is slow or errors** → the free model may be rate-limited. Say so:
  *"generation runs on free models, which is why I built a fallback chain and an
  answer cache."* Then show `docs/evidence/rag/golden_question_run.md` — the
  committed run of all 9 questions.
- **Airflow UI won't load** → show `docs/evidence/airflow/*.png` instead.
- **A table is missing** → `make pipeline` rebuilds everything in about 2 minutes.
- **Nothing works** → every claim in this script has committed evidence in
  `docs/evidence/`. Walk the evidence folder instead of the live system.
