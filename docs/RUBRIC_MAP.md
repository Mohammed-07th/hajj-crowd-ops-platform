# Rubric map — requirement → implementation → evidence

Every requirement, the file that implements it, and the executed output that
proves it ran. Evidence paths are relative to the repository root.

---

## Deliverable 1 — Ingestion (20 pts)

| Requirement | Implementation | Evidence |
|---|---|---|
| Real Kafka broker in Docker | [`docker-compose.yml`](../docker-compose.yml) — `apache/kafka:3.8.1`, KRaft, no Zookeeper | [`audit_slice3.log`](evidence/audit_slice3.log) — "Kafka broker responds to a real admin call" |
| Topics created by script | [`scripts/create_topics.sh`](../scripts/create_topics.sh) — auto-create disabled on the broker | topic list in the audit log |
| `confluent-kafka` producer + consumer | [`occupancy_producer.py`](../src/ingestion/producers/occupancy_producer.py), [`service_request_producer.py`](../src/ingestion/producers/service_request_producer.py), [`consumer.py`](../src/ingestion/consumer.py) | `200,000 events ... in 1.2s`; `accepted=185,843 rejected=14,157` |
| No queue simulation anywhere | — | [`verify_no_simulation.sh`](../scripts/verify_no_simulation.sh) → AUDIT PASSED |
| Pydantic v2 `ConfigDict(strict=True)` at the boundary | [`occupancy.py`](../src/contracts/occupancy.py), [`service_request.py`](../src/contracts/service_request.py) | [`test_contracts.py`](../tests/test_contracts.py) |
| ≥10 corruption types injectable and rejected | 10 per stream, in both producers | [`demo_bad_records.log`](evidence/failures/demo_bad_records.log) — 10 distinct rules |
| DLQ topic **and** quarantine Delta table | [`dlq.py`](../src/ingestion/dlq.py) | [`dlq_rejections.log`](evidence/failures/dlq_rejections.log) — 14,157 rows, 8 rule types across 3 partitions |
| Each record carries `rejection_reason` | `DLQEnvelope` in [`envelopes.py`](../src/contracts/envelopes.py) | every line of the DLQ log |
| Manual offset commit, reasoning documented | `enable.auto.commit=False`, commit after write — [`consumer.py`](../src/ingestion/consumer.py) module docstring | README "Design decisions" |

**Strict-mode headline:** the JSON string `"1500"` is refused for an integer
field (`rule=int_type`). Without strict mode Pydantic coerces it silently.

---

## Deliverable 2 — Delta Lakehouse (25 pts)

| Requirement | Implementation | Evidence |
|---|---|---|
| Real Delta tables (`_delta_log/` present) | [`delta_io.py`](../src/lakehouse/delta_io.py) via `deltalake` (delta-rs) | audit log lists `_delta_log` for all 6 tables |
| Bronze append-only with Kafka metadata | [`consumer.py`](../src/ingestion/consumer.py) — `_kafka_topic/_partition/_offset/_ingested_at/_source_file` | bronze schema in the notebook |
| `MERGE INTO ... ON request_id` observably updating rows | [`silver.py`](../src/lakehouse/silver.py) `build_silver_requests` | [`merge_evidence.md`](evidence/failures/merge_evidence.md) — ACKNOWLEDGED 1375→9, RESOLVED 0→1945 |
| Staging deduplicated before merge, reason commented | `_stage_latest_per_request` | [`test_merge_idempotency.py`](../tests/test_merge_idempotency.py) |
| Schema enforcement **failure** captured | [`schema_demo.py`](../src/lakehouse/schema_demo.py) | [`schema_enforcement.log`](evidence/failures/schema_enforcement.log) — `ValueError: Schema of data does not match table schema` |
| Controlled `schema_mode="merge"` success | same script, Part 2 | same log — `sensor_firmware_version` accepted |
| Gold is a genuine `GROUP BY`, not a copy | [`gold.py`](../src/lakehouse/gold.py) | 185,843 silver rows → 2,688 gold rows (69:1) |
| PII hashed in silver | [`pii.py`](../src/governance/pii.py) | [`GOVERNANCE.md`](GOVERNANCE.md); silver suite 11/11 |

**Deviation:** Delta is provided by `deltalake` (delta-rs, Rust) rather than
PySpark + delta-spark, removing the JVM from the stack. See
[`ARCHITECTURE.md`](ARCHITECTURE.md) §2.

**Cut under the one-day scope override:** SCD Type 2 history table,
`OPTIMIZE`/`ZORDER` timings, dedicated time-travel demo, gold tables 2 and 3.
(`RESTORE` is nonetheless exercised inside `schema_demo.py`.)

---

## Deliverable 3 — RAG Pipeline (25 pts)

| Requirement | Implementation | Evidence |
|---|---|---|
| SOP corpus with codes and cross-references | [`data/sop/`](../data/sop) — 10 documents | corpus table in [`RAG_DESIGN.md`](RAG_DESIGN.md) §1 |
| Recursive chunking 512/64, metadata, justified | [`chunker.py`](../src/rag/chunker.py) | 87 chunks, mean 150 tokens; [`RAG_DESIGN.md`](RAG_DESIGN.md) §2 |
| Real embeddings, correct `query:`/`passage:` prefixes | [`embedder.py`](../src/rag/embedder.py) — `multilingual-e5-small`, 384d | index output: `"vector_size": 384` |
| Real vector store, explicit HNSW | [`vector_store.py`](../src/rag/vector_store.py) — Qdrant, COSINE, `m=32`, `ef_construct=200` | index output: `"hnsw_m": 32, "hnsw_ef_construct": 200` |
| BM25 over the same chunk set | [`retriever.py`](../src/rag/retriever.py) | [`hybrid_proof.md`](evidence/rag/hybrid_proof.md) |
| **RRF implemented by hand**, k=60, unit-tested | `reciprocal_rank_fusion` in [`retriever.py`](../src/rag/retriever.py) | [`test_rrf.py`](../tests/test_rrf.py) — hand-computed values |
| Cross-encoder rerank 50→5 | [`reranker.py`](../src/rag/reranker.py) | [`rerank_proof.md`](evidence/rag/rerank_proof.md) |
| OpenRouter with retry, fallback chain, answer cache, `model_used` | [`generator.py`](../src/rag/generator.py) | [`golden_question_run.md`](evidence/rag/golden_question_run.md) |
| Answers cite doc_code per claim; refuse when insufficient | system prompt in [`generator.py`](../src/rag/generator.py) | 9/9 citation hits; out-of-scope question refused verbatim |
| Golden questions incl. Arabic, committed | [`golden_questions.yaml`](../tests/golden_questions.yaml) | [`golden_question_run.md`](evidence/rag/golden_question_run.md) — **9/9 / 9/9 / 9/9** |
| Hybrid-search proof | [`generate_rag_proofs.py`](../scripts/generate_rag_proofs.py) | [`hybrid_proof.md`](evidence/rag/hybrid_proof.md) |
| Rerank proof | same script | [`rerank_proof.md`](evidence/rag/rerank_proof.md) |

**Reported honestly:** the textbook "dense misses an exact document code, BM25
rescues it" result **did not reproduce** on an 87-chunk corpus — dense found
every one of 31 identifiers in the top 3. The complementary failure (BM25 falling
to rank 7 on vocabulary-free paraphrases) is clearly measurable and is what the
proof demonstrates. See [`RAG_DESIGN.md`](RAG_DESIGN.md) §5.1.

**Cut:** FastAPI serving layer.

---

## Deliverable 4 — Orchestration (15 pts)

| Requirement | Implementation | Evidence |
|---|---|---|
| Real Airflow, DAG parses, `catchup=False` | [`hajj_ops_pipeline.py`](../dags/hajj_ops_pipeline.py) — Airflow 2.10.5 | `airflow dags list-import-errors` → "No data found" |
| Correct dependencies, parallel branches | 13 tasks; parallel ingest pair and parallel silver pair | [`airflow_green_run.png`](evidence/airflow/airflow_green_run.png) |
| Every task idempotent | silver/gold overwrite; bronze bounded by consumer offsets | README "Design decisions"; [`test_merge_idempotency.py`](../tests/test_merge_idempotency.py) |
| XCom carries only small values | row counts and table names only | code comments in the DAG module docstring |
| Sensor for an external dependency | `FileSensor` on `data/sop`, `mode="reschedule"` | green-run screenshot; it genuinely blocked when the directory was empty |
| `on_failure_callback` emitting lineage FAIL | `emit_task_failure_lineage` → [`emit_fail.py`](../src/lineage/emit_fail.py) | FAIL events in [`events_gate_failure.jsonl`](evidence/lineage/events_gate_failure.jsonl) |
| Green-run screenshot | — | [`airflow_green_run.png`](evidence/airflow/airflow_green_run.png) — 13/13 success |
| **Gate-failure screenshot with skipped downstream** | — | [`airflow_gate2_failure.png`](evidence/airflow/airflow_gate2_failure.png) — `validate_silver` failed; `build_gold_zone_hourly`, `refresh_rag_index`, `smoke_test_rag` all `upstream_failed` |

---

## Deliverable 5 — Quality Gate + Lineage (15 pts)

| Requirement | Implementation | Evidence |
|---|---|---|
| GE suites for bronze, silver and gold | [`checkpoints.py`](../src/quality/checkpoints.py); suites in [`great_expectations/expectations/`](../great_expectations/expectations) | bronze 10/10, silver 11/11 |
| Checkpoint failure raises and **blocks** | `QualityGateFailure` → non-zero exit → `AirflowException` | [`gate2_failure_run.md`](evidence/failures/gate2_failure_run.md) |
| Volume pillar | `expect_table_row_count_to_be_between` on bronze and silver | both gate-failure demos are volume-pillar trips |
| Conditional-required expectation | `crew_id` not null where status is DISPATCHED/ON_SITE/RESOLVED | silver suite |
| Proves raw PII dropped | `expect_table_columns_to_match_set` (exact) | [`GOVERNANCE.md`](GOVERNANCE.md) §4 |
| OpenLineage START / COMPLETE / FAIL per stage | [`emitter.py`](../src/lineage/emitter.py) — context manager, one line per stage | [`events.jsonl`](evidence/lineage/events.jsonl) — 8 START / 8 COMPLETE |
| Row-count facets on COMPLETE | `OutputStatisticsOutputDatasetFacet` | `bronze_zone_occupancy rowCount=185,843` etc. |
| FAIL events | exception handler + `on_failure_callback` | [`events_gate_failure.jsonl`](evidence/lineage/events_gate_failure.jsonl) |

**Deviation:** OpenLineage events are written by the official client through its
**file transport** rather than POSTed to Marquez, to keep a Marquez + Postgres
pair out of a 5 GB Docker allocation. The payloads are the client's own
serialisation — byte-identical to what Marquez would have received. No Marquez UI
screenshot exists as a result.

---

## Repository requirements

| Requirement | Status |
|---|---|
| Clear description on the landing page | [`README.md`](../README.md) |
| Prerequisites / setup / run / expected output / config table | README §Prerequisites–§Configuration |
| `docs/RUBRIC_MAP.md` mapping requirement → file → evidence | this document |
| 30+ meaningful incremental commits | 38+ at slice 3; conventional messages, no bulk upload |
| `.gitignore` excludes secrets and generated files | [`.gitignore`](../.gitignore); `docs/evidence/**` deliberately re-included |
| No API key anywhere in history | audit checks `sk-or-v1-` across all commits on every run |
| Program attribution with cohort and trainer | README §Training program attribution |
| Link to SDAIA Academy | README |
| Executed notebook with output saved | [`notebooks/01_pipeline_walkthrough.ipynb`](../notebooks/01_pipeline_walkthrough.ipynb) |
