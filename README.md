# Hajj & Tourism Crowd Operations Data Platform

A real-time crowd operations platform for Hajj, Umrah and Saudi tourism sites. It
ingests zone occupancy telemetry and field service requests through **Kafka**,
lands them in a **Delta lakehouse** (bronze / silver / gold), enforces automated
**quality gates that halt the pipeline** on bad data, emits **OpenLineage** events
for every stage, and serves an **operations copilot** that answers procedural
questions from standard operating procedures with citations.

> ## ⚠️ Synthetic data disclaimer
>
> All operational data in this project is **synthetic**, generated for training
> purposes. Zone capacities, SLA targets and standard operating procedures are
> illustrative constructions and **do not represent official figures or
> procedures of any Saudi authority.** Zone and site names are real places; every
> number attached to them was produced by the generators in this repository.
> SOP thresholds are informed by published public standards (Fruin pedestrian
> level-of-service bands, ISO 7243 WBGT) and are cited as such in each document
> footer — never as official policy.

## The problem it solves

Saudi crowd-management authorities operate high-density sites: the Mataf, the
Mas'a, the Jamarat bridge levels, Mina camps, Arafat and Muzdalifah, plus
year-round tourism sites at AlUla and Diriyah. Gate sensors report occupancy
every few seconds; field staff raise service requests that progress through a
lifecycle over minutes to hours.

When a zone hits 90% capacity at 2am, the duty officer needs to know the
escalation threshold, who authorises diversion, and what the medical response SLA
is — **from the actual SOP, with a citation**, not from a model's memory. That is
what this platform delivers, on top of a lakehouse that makes the occupancy
history queryable.

## Architecture

```
  synthetic          ┌──────────────────────────────────────┐
  generators  ────►  │  Kafka (KRaft, single container)      │
  (2 producers)      │  zone_occupancy_raw      (3 parts)    │
                     │  service_requests_raw    (3 parts)    │
                     │  dlq_zone_occupancy / dlq_service_... │
                     └──────────────┬───────────────────────┘
                                    │  Pydantic v2 strict contract
                                    │  validated on raw JSON bytes
                      valid ────────┴──────── invalid
                        │                        │
                        ▼                        ▼
               ┌─────────────────┐      ┌───────────────────┐
               │ BRONZE (Delta)  │      │ dlq_* topic  +    │
               │ append-only     │      │ quarantine Delta  │
               │ + kafka metadata│      │ + rejection_reason│
               └────────┬────────┘      └───────────────────┘
                        │
                   [GE GATE 1 — bronze_suite, 10 expectations]
                        │
           ┌────────────┴────────────┐
           ▼                         ▼
  silver_zone_occupancy      silver_service_requests
  (dedupe on event_id,       (MERGE INTO ... ON request_id,
   join zones, utilisation)   staged to latest per key, PII hashed)
           └────────────┬────────────┘
                        │
                   [GE GATE 2 — silver_requests_suite, 11 expectations]
                        │
                        ▼
                gold_zone_hourly  (GROUP BY zone, hour — 69:1)
                        │
                        ▼
        SOP docs → chunk → e5 embeddings → Qdrant + BM25
                        │
        hybrid retrieve → RRF (k=60) → cross-encoder → LLM + citations

  Airflow orchestrates every arrow (13 tasks).
  OpenLineage START/COMPLETE/FAIL per stage → docs/evidence/lineage/events.jsonl
```

Full rationale in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Prerequisites

| Requirement | Version | Why |
|---|---|---|
| Docker | any recent | Kafka and Qdrant run as containers. Allocate **≥ 5 GB**. |
| Python | **3.11.x** | Airflow 2.10 and Great Expectations 0.18 do not run on 3.12+. |
| Git | any | — |
| RAM | 16 GB | Kafka + Qdrant (5 GB Docker) + embedding and reranker models. |
| Disk | ~10 GB | Container images, Delta tables, HuggingFace cache (~600 MB). |

**Java is not required.** Delta is provided by `deltalake` (delta-rs, Rust), so
there is no JVM in the stack.

Developed with `colima` as the Docker runtime; Docker Desktop works identically:

```bash
brew install colima docker docker-compose && colima start --cpu 4 --memory 5 --disk 40 --vm-type vz
```

## Setup

```bash
git clone https://github.com/Mohammed-07th/hajj-crowd-ops-platform.git
cd hajj-crowd-ops-platform

python3.11 -m venv .venv && ./.venv/bin/pip install -r requirements.txt

# Airflow in its own venv: its pins conflict with the GE + torch stack
python3.11 -m venv .venv-airflow
./.venv-airflow/bin/pip install "apache-airflow==2.10.5" \
  --constraint "https://raw.githubusercontent.com/apache/airflow/constraints-2.10.5/constraints-3.11.txt"

cp .env.example .env      # set PII_SALT; set OPENROUTER_API_KEY for generation
make up                   # kafka + qdrant, wait for health, create topics
```

## How to run

```bash
make pipeline     # reset -> produce -> ingest -> GATE 1 -> silver -> GATE 2 -> gold
make rag-index    # chunk -> embed -> qdrant
make golden       # run the 9 golden questions, write evidence
make test         # 44 unit tests
make audit        # anti-substitution audit
```

Orchestrated end to end:

```bash
make airflow      # webserver + scheduler on http://localhost:8080 (admin/admin)
```

then trigger `hajj_ops_pipeline`. Ask the copilot directly:

```bash
make ask Q="MATAF_01 has been above 90% for 12 minutes. Who authorizes diversion?"
```

## Expected output

`make produce` / `make ingest`:

```
producing 200000 events over 7 simulated days (16 zones x 12500 ticks, step=0:00:48.384000)
DONE: 200,000 events to 'zone_occupancy_raw' (14,336 deliberately corrupt, 7.2%) in 1.2s

{ "accepted": 185843, "rejected": 14157, "total": 200000, "rejection_rate_pct": 7.08 }
```

`make gate-bronze`:

```
{ "success": true, "suite": "bronze_suite", "evaluated": 10, "successful": 10 }
GATE PASSED: 10/10 expectations met
```

The MERGE, on a second wave of lifecycle events for the same `request_id`s:

```
bronze_rows: 11054  ->  staged_rows: 2500  ->  silver rows: 2500
ACKNOWLEDGED 1375 -> 9        RESOLVED 0 -> 1945
```

Sample `gold_zone_hourly` — 185,843 silver readings collapse to 2,688 zone-hours:

```
┌───────────────┬─────────────────────────┬────────────────┬──────────┬─────────────────────┐
│ zone_id       ┆ hour_start              ┆ peak_occupancy ┆ capacity ┆ minutes_above_90pct │
╞═══════════════╪═════════════════════════╪════════════════╪══════════╪═════════════════════╡
│ MATAF_02      ┆ 2026-05-27 12:00:00 UTC ┆ 39978          ┆ 32000    ┆ 58.3                │
│ MASAA_L2      ┆ 2026-05-27 12:00:00 UTC ┆ 22378          ┆ 18000    ┆ 60.0                │
└───────────────┴─────────────────────────┴────────────────┴──────────┴─────────────────────┘
```

A grounded answer with citations:

```
Q: What is the response-time SLA for a P1 medical request?
A: The response-time SLA for a P1 medical request is **4 minutes**
   [2, SOP-MED-002] [3, SOP-OPS-001].
```

## Design decisions worth knowing

**Strict contracts.** `ConfigDict(strict=True)` on every event model. Without it
Pydantic coerces the JSON string `"1500"` into `1500` — which is how corrupt data
enters a warehouse wearing a valid disguise. Validation runs on raw JSON **bytes**
(`model_validate_json`), because Pydantic's JSON conversion table accepts an
ISO-8601 string as a `datetime` while still refusing a quoted integer; parsing
first would lose that distinction.

**Manual offset commit.** `enable.auto.commit=False`; offsets commit only after
the batch is durably written to Delta. Auto-commit advances on poll, so a crash
between poll and write loses records silently. Committing after the write gives
at-least-once delivery — bronze can contain duplicates, which is why silver
deduplicates on `event_id`.

**Why the gates fail on volume.** The contract keeps malformed records *out of
bronze*, so a 40% corruption run never puts bad values in front of Great
Expectations. What GE sees is a **volume shortfall** — and
`expect_table_row_count_to_be_between` fails. That is the Day-4 volume pillar
catching an upstream incident that per-row checks cannot see.

**Idempotency.** Airflow retries automatically, so a non-idempotent task
double-counts on its first retry and nobody notices until the numbers are wrong.
Silver and gold are full recomputations; bronze ingestion is bounded by
consumer-group offsets, which do not rewind on retry.

**XCom carries only row counts and table names** — never a DataFrame.

## Failure demonstrations

| # | Demonstration | Command | Evidence |
|---|---|---|---|
| 1 | **Contract rejection** — 100 events, 20 malformed, 10 distinct rules, incl. strict-mode coercion | `PYTHONPATH=. .venv/bin/python scripts/demo_failures/demo_bad_records.py` | [demo_bad_records.log](docs/evidence/failures/demo_bad_records.log) |
| 2 | **Schema enforcement** — breaking change refused, additive accepted | `make schema-demo` | [schema_enforcement.log](docs/evidence/failures/schema_enforcement.log) |
| 3 | **Quality gate halts the pipeline** — GATE 2 fails, all downstream `upstream_failed` | trigger DAG with `{"unique_requests": 200, "request_events": 900}` | [gate2_failure_run.md](docs/evidence/failures/gate2_failure_run.md), [screenshot](docs/evidence/airflow/airflow_gate2_failure.png) |
| 4 | Time-travel `RESTORE` | cut under the one-day scope override; `RESTORE` is exercised inside `schema_demo.py` | [schema_enforcement.log](docs/evidence/failures/schema_enforcement.log) |

## Configuration

| Variable | Purpose |
|---|---|
| `KAFKA_BOOTSTRAP_SERVERS` | Broker address (default `localhost:9092`) |
| `QDRANT_URL` / `QDRANT_COLLECTION` | Vector store endpoint and collection |
| `DELTA_ROOT` | Root directory for Delta tables (default `./delta`) |
| `PII_SALT` | Salt for SHA-256 hashing of `pilgrim_ref` / `reporter_phone` |
| `OPENLINEAGE_NAMESPACE` | Lineage namespace (`hajj-ops`) |
| `OPENLINEAGE_EVENTS_PATH` | Where OpenLineage JSON events are written |
| `EMBEDDING_MODEL` / `EMBEDDING_DIM` | `intfloat/multilingual-e5-small`, 384 |
| `RERANKER_MODEL` | Cross-encoder for reranking (English-only by default — see RAG_DESIGN) |
| `OPENROUTER_API_KEY` | Generation only; retrieval is entirely local |
| `LLM_MODEL_PRIMARY` / `LLM_MODEL_FALLBACKS` | Free-model chain with fallback |
| `LLM_MAX_RETRIES` / `LLM_TIMEOUT_SECONDS` | Backoff behaviour for free-tier limits |
| `RRF_K` / `RETRIEVE_TOP_K` / `RERANK_TOP_K` | Retrieval tuning (60 / 50 / 5) |

## Results

| Deliverable | Headline evidence |
|---|---|
| 1 — Ingestion | 185,843 accepted / 14,157 rejected, exactly matching injections; 10 rule types |
| 2 — Lakehouse | 6 Delta tables; MERGE moved 2,490 → 2,500 rows with statuses advancing; schema violation refused |
| 3 — RAG | Golden questions **9/9 retrieval, 9/9 citation, 9/9 fact**, incl. Arabic and a refusal |
| 4 — Orchestration | 13-task DAG green; GATE 2 failure leaves 3 downstream tasks `upstream_failed` |
| 5 — Quality + Lineage | bronze 10/10, silver 11/11; 8 START / 8 COMPLETE with row-count facets, FAIL on gate failure |

Full mapping in [docs/RUBRIC_MAP.md](docs/RUBRIC_MAP.md). Design rationale in
[docs/RAG_DESIGN.md](docs/RAG_DESIGN.md), [docs/GOVERNANCE.md](docs/GOVERNANCE.md)
and [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

Two results are reported that did **not** match expectations — the hybrid-search
demonstration and delta-rs's default schema behaviour. Both are documented with
their measurements rather than smoothed over.

## Training program attribution

> Completed as the capstone project for **Modern Data Engineering for AI Systems**,
> SDAIA Academy, delivered via Learning Space. Cohort: `2–6 August 2026`.
> Trainer: Mohammed Albeladi.

SDAIA Academy on GitHub: https://github.com/SDAIAAcademy

## Author

Built and submitted by a single trainee working solo.

**mohammed alshaigi** — [@Mohammed-07th](https://github.com/Mohammed-07th)

## License

MIT — see [LICENSE](LICENSE).
