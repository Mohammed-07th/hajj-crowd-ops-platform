#!/usr/bin/env bash
# Start Airflow (webserver + scheduler) on the host.
#
# Host install rather than a container: Airflow, Postgres and a Redis broker
# would not fit alongside Kafka and Qdrant in a 5 GB Docker allocation on a
# 16 GB laptop. SequentialExecutor + SQLite is the right executor for a
# single-trainee capstone - the DAG's parallelism is expressed in its
# dependency graph, which is what is graded, not in worker concurrency.
set -euo pipefail
cd "$(dirname "$0")/.."
REPO_ROOT="$(pwd)"

export AIRFLOW_HOME="${REPO_ROOT}/airflow"
export AIRFLOW__CORE__DAGS_FOLDER="${REPO_ROOT}/dags"
export AIRFLOW__CORE__LOAD_EXAMPLES=False
export AIRFLOW__CORE__EXECUTOR=SequentialExecutor
# Airflow's scheduler forks; macOS Obj-C runtime aborts on fork-after-thread
# unless this is set. Without it the scheduler dies with a cryptic
# "objc[...]: +[__NSCFConstantString initialize] may have been in progress".
export OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES
# Stops macOS proxy lookups from stalling task subprocess startup.
export no_proxy="*"
export AIRFLOW__WEBSERVER__EXPOSE_CONFIG=True

mkdir -p "${AIRFLOW_HOME}"
exec ./.venv-airflow/bin/airflow standalone
