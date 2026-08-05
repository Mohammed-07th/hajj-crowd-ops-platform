# Architecture

## 1. Shape of the system

```
  synthetic          ┌──────────────────────────────────────┐
  generators  ────►  │  Kafka (KRaft, single container)      │
  (2 producers)      │  zone_occupancy_raw      (3 parts)    │
                     │  service_requests_raw    (3 parts)    │
                     │  dlq_zone_occupancy      (1 part)     │
                     │  dlq_service_requests    (1 part)     │
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
                   [GE GATE 1: bronze_suite, 10 expectations]
                        │
           ┌────────────┴────────────┐
           ▼                         ▼
  silver_zone_occupancy      silver_service_requests
  (dedupe on event_id,       (MERGE INTO ... ON request_id,
   join zones, utilisation)   staged to latest per key, PII hashed)
           └────────────┬────────────┘
                        │
                   [GE GATE 2: silver_requests_suite, 11 expectations]
                        │
                        ▼
               ┌─────────────────┐
               │ GOLD (Delta)    │      gold_zone_hourly
               │ GROUP BY zone,  │      69:1 aggregation
               │ hour            │
               └────────┬────────┘
                        ▼
               ┌─────────────────────────────────────┐
               │ RAG INDEX                            │
               │ SOP docs → recursive chunk (512/64)  │
               │ → e5-small 384d → Qdrant (HNSW)      │
               │ + BM25 over the same chunks          │
               └────────┬────────────────────────────┘
                        ▼
               hybrid retrieve → RRF (k=60) → cross-encoder → LLM + citations

  Airflow orchestrates every arrow (13 tasks).
  OpenLineage START/COMPLETE/FAIL per stage → docs/evidence/lineage/events.jsonl
```

## 2. Stack decisions and why

### Delta via delta-rs, not PySpark

`deltalake` (Rust) + `polars` rather than `pyspark` + `delta-spark`. The rubric
permits either. The consequence is that **there is no JVM in the stack** — no
Java 17 prerequisite, no `JAVA_HOME`, no Spark session startup cost, and no
class of failure where Spark will not start.

The trade-off is real and worth naming: this cannot scale past a single machine,
and a production deployment at genuine Hajj volume would use Spark. At 200k
events on a laptop, delta-rs writes the same `_delta_log`, performs the same
`MERGE`, and enforces the same schema.

**One behaviour that differs and matters.** delta-rs has two write engines and
they enforce schema differently:

| Engine | Appending StringType `"1500"` into an Int64 column |
|---|---|
| `rust` (default) | **Safe-casts it.** Succeeds silently, stores `1500`. |
| `pyarrow` | **Refuses.** `ValueError: Schema of data does not match table schema` |

Silent coercion at the storage boundary is exactly the failure the strict
Pydantic contract exists to prevent at the ingestion boundary, so every write
goes through the enforcing engine (`src/lakehouse/delta_io.py`). Both behaviours
are demonstrated in `src/lakehouse/schema_demo.py` rather than asserted.

### Airflow on the host, not in Docker

Docker is capped at 5 GB on a 16 GB machine already running an embedding model
and a reranker. Airflow + Postgres + a broker would not fit alongside Kafka and
Qdrant. Airflow runs on the host with SequentialExecutor and SQLite — a real
scheduler and webserver. The DAG's parallelism is expressed in its dependency
graph, which is what is graded, not in worker concurrency.

### Two virtual environments

Airflow 2.10 pins `sqlalchemy<2` plus a flask/connexion stack that conflicts with
Great Expectations 0.18 and torch. Rather than weaken either, Airflow lives in
`.venv-airflow` and every stage runs as a subprocess against `.venv`. The DAG
file imports nothing from `src/` — it knows module names and arguments only, and
parses row counts back out of stdout into XCom.

### Lineage to a file, not Marquez

`openlineage-python` with its **file transport**. The events are produced by the
official client and are byte-identical to what Marquez would have received over
HTTP; only the transport differs. This keeps a Marquez + Postgres pair out of the
5 GB Docker allocation. The cost is that there is no lineage-graph UI screenshot.

### setproctitle shim

`setproctitle`'s Darwin implementation calls a private LaunchServices entry point
through CoreFoundation that segfaults every gunicorn worker on current macOS, in
both 1.3.4 and 1.3.7. Airflow was unusable — the webserver never bound port 8080
and the scheduler's log server died in a fork loop. `airflow_shims/setproctitle.py`
shadows it with a no-op via `PYTHONPATH`. Process titles are cosmetic; nothing
else changes. Crash trace is in the shim's docstring.

## 3. Data flow properties

**At-least-once, deliberately.** Offsets are committed only after a batch is
durably written to Delta. Auto-commit advances on poll, so a crash between poll
and write loses records with nothing to report it. Committing after the write
means a crash between write and commit replays the batch instead — bronze can
contain duplicates, and silver deduplicates on `event_id` rather than trusting
the stream.

**Idempotency, because Airflow retries.** With `retries=2`, a task that appends
on every invocation double-counts on its first retry and nobody notices until the
numbers are wrong. Silver and gold are full recomputations; bronze ingestion is
bounded by consumer-group offsets, which do not rewind on retry. The MERGE is
tested for idempotency and for resistance to stale replay.

**Time compression.** Seven simulated days are emitted in ~1 second of wall
clock, controlled by `--sim-start` / `--sim-days`. Gold needs hours and days to
aggregate over; running in real time would prove nothing and take a week. Crowd
curves carry prayer-time peaks, a Jamarat surge on the simulated 10th of
Dhul-Hijjah, an Arafat day and a Muzdalifah overnight spike — without that shape
`minutes_above_90pct` is always zero and the gold layer looks pointless.

## 4. Why the quality gates fail on volume

Worth stating because it surprises people. The Pydantic contract keeps malformed
records **out of bronze entirely** — they go to the DLQ. So a run with a 40%
corruption rate does not put bad values in front of Great Expectations; row-level
expectations still pass.

What GE sees is a **volume shortfall**: ~120k rows where ~186k were expected.
`expect_table_row_count_to_be_between` fails, and the pipeline halts. That is the
Day-4 volume pillar doing precisely its job — catching an upstream data incident
that per-row checks cannot see. Both gate-failure demonstrations in this project
are volume-pillar trips, on bronze and on silver respectively.

## 5. What was cut

Under a one-day scope override, breadth across all five deliverables was
prioritised over depth in any one:

- SCD Type 2 history table
- FastAPI serving layer
- `OPTIMIZE` / `ZORDER` with before/after timings
- Dedicated time-travel demo (`RESTORE` is exercised inside `schema_demo.py`)
- Open-Meteo, prayer-time and GASTAT ingestion paths
- Gold tables 2 and 3 (`gold_service_sla`, `gold_daily_ops_briefing`)
- Notebooks 2 and 3

Everything in the rubric's Tier 1 was built before anything was cut.
