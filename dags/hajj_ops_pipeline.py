"""Airflow DAG orchestrating the Hajj crowd operations pipeline.

Two-venv layout
---------------
Airflow 2.10 pins sqlalchemy<2 plus a specific flask/connexion stack that
conflicts with the Great Expectations + torch dependency set. Rather than
weaken either, Airflow lives in .venv-airflow and every stage runs as a
subprocess against .venv (the pipeline interpreter). This DAG file therefore
imports nothing from src/ - it only knows module names and arguments.

Idempotency
-----------
Airflow retries failed tasks automatically (retries=2 below). A task that
appends on every invocation would double-count on the first retry and nobody
would notice until the numbers were wrong. So: silver and gold are full
recomputations (overwrite), and bronze ingestion is bounded by consumer-group
offsets, which do not rewind on retry.

XCom
----
XCom carries row counts and table names only - never a DataFrame. XCom values
are serialised into the Airflow metadata database; putting a 250k-row frame in
there would bloat the database and eventually fail on size limits.
"""

from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

from airflow import DAG
from airflow.exceptions import AirflowException
from airflow.operators.empty import EmptyOperator
from airflow.operators.python import PythonOperator
from airflow.sensors.filesystem import FileSensor

REPO_ROOT = Path(__file__).resolve().parent.parent
PIPELINE_PYTHON = str(REPO_ROOT / ".venv" / "bin" / "python")

# Corruption rate for the dev producer task. Override in the Airflow UI
# ("Trigger DAG w/ config") with {"corrupt_rate": 0.4} to drive the mandatory
# gate-failure demonstration.
DEFAULT_CORRUPT_RATE = 0.07
DEFAULT_EVENTS = 200_000
# Volume-pillar floor for the bronze gate. At the default 7% corruption rate a
# healthy run lands ~186k rows; 150k leaves headroom for normal variation but
# is far above what a 40%-corruption run can deliver.
BRONZE_MIN_ROWS = 150_000


def _run_stage(module: str, args: list[str], task_id: str) -> str:
    """Run a pipeline module in the pipeline venv; return its trailing JSON."""
    cmd = [PIPELINE_PYTHON, "-m", module, *args]
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT), "PYTHONUNBUFFERED": "1"}
    print(f"$ {' '.join(cmd)}", flush=True)
    proc = subprocess.run(cmd, cwd=str(REPO_ROOT), env=env,
                          capture_output=True, text=True)
    print(proc.stdout, flush=True)
    if proc.stderr:
        print("--- stderr ---\n" + proc.stderr, flush=True)
    if proc.returncode != 0:
        raise AirflowException(
            f"{task_id} failed (exit {proc.returncode}) running {module}. "
            f"Last stderr line: {proc.stderr.strip().splitlines()[-1] if proc.stderr.strip() else 'n/a'}"
        )
    return proc.stdout


def _tail_json(stdout: str) -> dict:
    """Pull the trailing JSON object a stage prints as its result."""
    depth, start = 0, None
    for i in range(len(stdout) - 1, -1, -1):
        c = stdout[i]
        if c == "}":
            depth += 1
            if start is None:
                start = i
        elif c == "{":
            depth -= 1
            if depth == 0 and start is not None:
                try:
                    return json.loads(stdout[i:start + 1])
                except json.JSONDecodeError:
                    start, depth = None, 0
    return {}


def produce_test_events(**context) -> dict:
    conf = context["dag_run"].conf or {}
    corrupt_rate = float(conf.get("corrupt_rate", DEFAULT_CORRUPT_RATE))
    events = int(conf.get("events", DEFAULT_EVENTS))
    _run_stage("src.ingestion.producers.occupancy_producer",
               ["--events", str(events), "--corrupt-rate", str(corrupt_rate), "--seed", "42"],
               "produce_test_events")
    return {"events": events, "corrupt_rate": corrupt_rate}


def ingest_bronze_occupancy(**context) -> dict:
    out = _run_stage("src.ingestion.consumer",
                     ["--topic", "zone_occupancy_raw",
                      "--bronze-table", "bronze_zone_occupancy",
                      "--idle-timeout", "15"],
                     "ingest_bronze_occupancy")
    result = _tail_json(out)
    # Small values only.
    return {"accepted": result.get("accepted"), "rejected": result.get("rejected")}


def validate_bronze(**context) -> dict:
    _run_stage("src.quality.run_gate",
               ["--layer", "bronze", "--min-rows", str(BRONZE_MIN_ROWS)],
               "validate_bronze")
    return {"gate": "bronze", "status": "passed"}


def build_silver_occupancy(**context) -> dict:
    out = _run_stage("src.lakehouse.silver", ["--table", "occupancy"], "build_silver_occupancy")
    return {"rows": _tail_json(out).get("rows")}


def build_gold_zone_hourly(**context) -> dict:
    out = _run_stage("src.lakehouse.gold", ["--table", "zone_hourly"], "build_gold_zone_hourly")
    return {"rows": _tail_json(out).get("rows")}


def emit_task_failure_lineage(context) -> None:
    """default_args on_failure_callback -> OpenLineage FAIL for the task."""
    ti = context["task_instance"]
    reason = str(context.get("exception", "unknown"))[:500]
    subprocess.run(
        [PIPELINE_PYTHON, "-m", "src.lineage.emit_fail",
         "--job", f"airflow.{ti.dag_id}.{ti.task_id}", "--message", reason],
        cwd=str(REPO_ROOT),
        env={**os.environ, "PYTHONPATH": str(REPO_ROOT)},
        check=False,
    )


default_args = {
    "owner": "hajj-ops",
    "retries": 2,
    "retry_delay": timedelta(minutes=1),
    "on_failure_callback": emit_task_failure_lineage,
}

with DAG(
    dag_id="hajj_ops_pipeline",
    description="Kafka -> bronze -> [GE gate] -> silver -> gold, with OpenLineage per stage",
    start_date=datetime(2026, 8, 1),
    schedule=None,
    catchup=False,
    default_args=default_args,
    max_active_runs=1,
    tags=["hajj", "sdaia", "capstone"],
) as dag:

    start = EmptyOperator(task_id="start")
    end = EmptyOperator(task_id="end")

    # Sensor on an external dependency: the SOP corpus the RAG stage indexes.
    # If the directory is not there, the pipeline waits rather than building an
    # index over nothing.
    wait_for_sop_corpus = FileSensor(
        task_id="wait_for_sop_corpus",
        filepath=str(REPO_ROOT / "data" / "sop"),
        fs_conn_id="fs_default",
        poke_interval=10,
        timeout=120,
        mode="reschedule",  # frees the worker slot between pokes
    )

    t_produce = PythonOperator(task_id="produce_test_events", python_callable=produce_test_events)
    t_ingest = PythonOperator(task_id="ingest_bronze_occupancy", python_callable=ingest_bronze_occupancy)
    t_gate1 = PythonOperator(task_id="validate_bronze", python_callable=validate_bronze)
    t_silver = PythonOperator(task_id="build_silver_occupancy", python_callable=build_silver_occupancy)
    t_gold = PythonOperator(task_id="build_gold_zone_hourly", python_callable=build_gold_zone_hourly)

    # Default trigger_rule (all_success) everywhere: when validate_bronze fails,
    # build_silver_occupancy and build_gold_zone_hourly go upstream_failed /
    # skipped instead of running on unvalidated data.
    start >> wait_for_sop_corpus >> t_produce >> t_ingest >> t_gate1 >> t_silver >> t_gold >> end
