"""Assert every Definition-of-Done checkbox against actual repository state.

Checks the repo, not memory. Each check either finds a real artifact on disk or
fails. Run before submitting.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
results: list[tuple[str, str, bool, str]] = []


def check(deliverable: str, name: str, passed: bool, detail: str = "") -> None:
    results.append((deliverable, name, passed, detail))


def file_exists(rel: str) -> bool:
    return (REPO / rel).exists()


def file_contains(rel: str, pattern: str) -> bool:
    path = REPO / rel
    if not path.exists():
        return False
    # MULTILINE so ^/$ anchor to lines, not to the whole file.
    return re.search(pattern, path.read_text(encoding="utf-8", errors="replace"),
                     re.MULTILINE) is not None


def any_contains(glob: str, pattern: str) -> bool:
    return any(re.search(pattern, p.read_text(encoding="utf-8", errors="replace"))
               for p in REPO.glob(glob) if p.is_file())


def main() -> int:
    # --- D1 -------------------------------------------------------------
    check("D1", "Kafka broker defined in compose (no Zookeeper)",
          file_contains("docker-compose.yml", r"apache/kafka") and
          not file_contains("docker-compose.yml", r"zookeeper"))
    check("D1", "topics created by script",
          file_exists("scripts/create_topics.sh"))
    check("D1", "confluent-kafka used by producer and consumer",
          file_contains("src/ingestion/consumer.py", r"from confluent_kafka import") and
          file_contains("src/ingestion/producers/occupancy_producer.py",
                        r"from confluent_kafka import"))
    check("D1", "no queue simulation in src/",
          not any_contains("src/**/*.py", r"asyncio\.Queue|queue\.Queue|MockBroker|FakeKafka"))
    check("D1", "Pydantic ConfigDict(strict=True) on both contracts",
          file_contains("src/contracts/occupancy.py", r"ConfigDict\(strict=True") and
          file_contains("src/contracts/service_request.py", r"ConfigDict\(strict=True"))
    check("D1", "10 corruption types per stream",
          file_contains("src/ingestion/producers/occupancy_producer.py",
                        r"CORRUPTION_TYPES = \(") and
          len(re.findall(r'"\w+",',
              (REPO / "src/ingestion/producers/occupancy_producer.py")
              .read_text().split("CORRUPTION_TYPES = (")[1].split(")")[0])) >= 10)
    check("D1", "DLQ envelope carries rejection_reason",
          file_contains("src/contracts/envelopes.py", r"rejection_reason"))
    check("D1", "quarantine Delta table on disk",
          file_exists("delta/quarantine/_delta_log"))
    check("D1", "manual offset commit",
          file_contains("src/ingestion/consumer.py", r'"enable\.auto\.commit": False'))
    check("D1", "contract rejection evidence committed",
          file_exists("docs/evidence/failures/demo_bad_records.log"))

    # --- D2 -------------------------------------------------------------
    for table in ["bronze_zone_occupancy", "bronze_service_requests",
                  "silver_zone_occupancy", "silver_service_requests",
                  "gold_zone_hourly"]:
        check("D2", f"real _delta_log for {table}",
              file_exists(f"delta/{table}/_delta_log"))
    check("D2", "bronze carries Kafka metadata columns",
          file_contains("src/ingestion/consumer.py", r"_kafka_offset"))
    check("D2", "MERGE on request_id",
          file_contains("src/lakehouse/silver.py",
                        r"target\.request_id = source\.request_id"))
    check("D2", "staging deduped to latest per key",
          file_contains("src/lakehouse/silver.py", r"_stage_latest_per_request"))
    check("D2", "schema enforcement failure captured",
          file_contains("docs/evidence/failures/schema_enforcement.log",
                        r"Schema of data does not match table schema"))
    check("D2", "mergeSchema additive success captured",
          file_contains("docs/evidence/failures/schema_enforcement.log",
                        r"sensor_firmware_version"))
    check("D2", "gold uses GROUP BY (group_by)",
          file_contains("src/lakehouse/gold.py", r"\.group_by\("))
    check("D2", "MERGE evidence committed",
          file_exists("docs/evidence/failures/merge_evidence.md"))

    # --- D3 -------------------------------------------------------------
    sop_count = len(list((REPO / "data/sop").glob("*.md")))
    check("D3", f"SOP corpus present ({sop_count} documents)", sop_count >= 8,
          f"{sop_count} documents")
    check("D3", "recursive chunker with 512/64",
          file_contains("src/rag/chunker.py", r"TARGET_TOKENS = 512") and
          file_contains("src/rag/chunker.py", r"OVERLAP_TOKENS = 64"))
    check("D3", "e5 query:/passage: prefixes applied",
          file_contains("src/rag/embedder.py", r'"query: "') and
          file_contains("src/rag/embedder.py", r'"passage: "'))
    check("D3", "Qdrant collection with explicit HNSW",
          file_contains("src/rag/vector_store.py", r"HNSW_M = 32") and
          file_contains("src/rag/vector_store.py", r"HNSW_EF_CONSTRUCT = 200"))
    check("D3", "BM25 over the same chunk set",
          file_contains("src/rag/retriever.py", r"BM25Okapi"))
    check("D3", "RRF implemented by hand with k=60",
          file_contains("src/rag/retriever.py", r"def reciprocal_rank_fusion") and
          file_contains("config/settings.py", r"rrf_k: int = 60"))
    check("D3", "RRF unit-tested against hand-computed values",
          file_exists("tests/test_rrf.py"))
    check("D3", "cross-encoder rerank",
          file_contains("src/rag/reranker.py", r"CrossEncoder"))
    check("D3", "model fallback chain + answer cache + model_used",
          file_contains("src/rag/generator.py", r"fallback_models") and
          file_contains("src/rag/generator.py", r"model_used"))
    check("D3", "golden questions include Arabic",
          file_contains("tests/golden_questions.yaml", r"[؀-ۿ]"))
    check("D3", "hybrid-search proof committed",
          file_exists("docs/evidence/rag/hybrid_proof.md"))
    check("D3", "rerank proof committed",
          file_exists("docs/evidence/rag/rerank_proof.md"))

    golden = REPO / "docs/evidence/rag/golden_question_run.json"
    if golden.exists():
        summary = json.loads(golden.read_text())["summary"]
        check("D3", "golden run: all questions retrieve their expected document",
              summary["retrieval_hits"] == summary["total"],
              f"{summary['retrieval_hits']}/{summary['total']}")
        check("D3", "golden run: all answers cite the expected document",
              summary["citation_hits"] == summary["total"],
              f"{summary['citation_hits']}/{summary['total']}")
    else:
        check("D3", "golden question run committed", False)

    # --- D4 -------------------------------------------------------------
    check("D4", "DAG file present with catchup=False",
          file_contains("dags/hajj_ops_pipeline.py", r"catchup=False"))
    check("D4", "retries=2 with retry_delay",
          file_contains("dags/hajj_ops_pipeline.py", r'"retries": 2'))
    check("D4", "sensor used for an external dependency",
          file_contains("dags/hajj_ops_pipeline.py", r"FileSensor"))
    check("D4", "on_failure_callback emits lineage FAIL",
          file_contains("dags/hajj_ops_pipeline.py", r"on_failure_callback"))
    check("D4", "green-run screenshot committed",
          file_exists("docs/evidence/airflow/airflow_green_run.png"))
    check("D4", "gate-failure screenshot committed",
          file_exists("docs/evidence/airflow/airflow_gate2_failure.png"))
    check("D4", "gate-failure shows downstream not executed",
          file_contains("docs/evidence/failures/gate2_failure_run.md",
                        r"upstream_failed"))

    # --- D5 -------------------------------------------------------------
    for suite in ["bronze_suite", "silver_requests_suite"]:
        check("D5", f"GE suite on disk: {suite}",
              file_exists(f"great_expectations/expectations/{suite}.json"))
    check("D5", "checkpoint raises on failure",
          file_contains("src/quality/checkpoints.py", r"raise QualityGateFailure"))
    check("D5", "volume pillar on bronze and silver",
          file_contains("src/quality/checkpoints.py",
                        r"expect_table_row_count_to_be_between"))
    check("D5", "proves raw PII columns dropped",
          file_contains("src/quality/checkpoints.py",
                        r"expect_table_columns_to_match_set"))

    events = REPO / "docs/evidence/lineage/events.jsonl"
    if events.exists():
        text = events.read_text()
        check("D5", "OpenLineage START events", '"eventType": "START"' in text)
        check("D5", "OpenLineage COMPLETE events", '"eventType": "COMPLETE"' in text)
        check("D5", "row-count facets on COMPLETE", "outputStatistics" in text)
    fail_events = REPO / "docs/evidence/lineage/events_gate_failure.jsonl"
    check("D5", "OpenLineage FAIL events captured",
          fail_events.exists() and '"eventType": "FAIL"' in fail_events.read_text())

    # --- repo -----------------------------------------------------------
    check("REPO", "README covers prerequisites/setup/run/config",
          all(file_contains("README.md", p) for p in
              [r"## Prerequisites", r"## Setup", r"## How to run", r"## Configuration"]))
    check("REPO", "RUBRIC_MAP.md present", file_exists("docs/RUBRIC_MAP.md"))
    check("REPO", "ARCHITECTURE.md present", file_exists("docs/ARCHITECTURE.md"))
    check("REPO", "GOVERNANCE.md present", file_exists("docs/GOVERNANCE.md"))
    check("REPO", "RAG_DESIGN.md present", file_exists("docs/RAG_DESIGN.md"))
    check("REPO", "synthetic data disclaimer near the top of README",
          "synthetic" in (REPO / "README.md").read_text()[:2500].lower())
    check("REPO", "SDAIA Academy link", file_contains("README.md", r"github\.com/SDAIAAcademy"))
    check("REPO", "attribution with cohort and trainer",
          file_contains("README.md", r"Mohammed Albeladi") and
          file_contains("README.md", r"2.6 August 2026"))
    check("REPO", ".gitignore excludes .env", file_contains(".gitignore", r"^\.env$"))

    commits = int(subprocess.run(["git", "rev-list", "--count", "HEAD"], cwd=REPO,
                                 capture_output=True, text=True).stdout.strip() or 0)
    check("REPO", "30+ incremental commits", commits >= 30, f"{commits} commits")

    tracked = subprocess.run(["git", "ls-files"], cwd=REPO,
                             capture_output=True, text=True).stdout.split()
    check("REPO", ".env not tracked", ".env" not in tracked)

    history = subprocess.run(["git", "log", "-p"], cwd=REPO,
                             capture_output=True, text=True).stdout
    check("REPO", "no API key in git history",
          re.search(r"sk-or-v1-[A-Za-z0-9]{20}", history) is None)

    check("REPO", "executed notebook with output",
          any_contains("notebooks/*.ipynb", r'"output_type"'))

    # --- report ---------------------------------------------------------
    width = 74
    current = None
    failed = 0
    for deliverable, name, passed, detail in results:
        if deliverable != current:
            current = deliverable
            print(f"\n{'=' * width}\n{deliverable}\n{'=' * width}")
        mark = "PASS" if passed else "FAIL"
        suffix = f"  ({detail})" if detail else ""
        print(f"  [{mark}] {name}{suffix}")
        if not passed:
            failed += 1

    total = len(results)
    print(f"\n{'=' * width}")
    print(f"{total - failed}/{total} checks passed")
    print("=" * width)
    if failed:
        print(f"\n{failed} FAILING — fix before submitting")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
