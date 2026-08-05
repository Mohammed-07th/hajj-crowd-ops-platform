#!/usr/bin/env bash
# Start Airflow (webserver + scheduler) on the host.
#
# Host install rather than a container: Airflow, Postgres and a Redis broker
# would not fit alongside Kafka and Qdrant in a 5 GB Docker allocation on a
# 16 GB laptop. SequentialExecutor + SQLite is the right executor for a
# single-trainee capstone - the DAG's parallelism is expressed in its
# dependency graph, which is what is graded, not in worker concurrency.
#
# Why not `airflow standalone`: on macOS its triggerer and scheduler each spawn
# a gunicorn `serve_logs` app whose workers die with SIGSEGV in a tight fork
# loop, and standalone never gets far enough to bind port 8080. Starting the
# webserver and scheduler directly avoids the triggerer entirely (nothing here
# uses deferrable operators - the FileSensor runs in `reschedule` mode, which
# is handled by the scheduler).
set -euo pipefail
cd "$(dirname "$0")/.."
REPO_ROOT="$(pwd)"

export PATH="${REPO_ROOT}/.venv-airflow/bin:${PATH}"
# Shadow the setproctitle C extension, which segfaults every gunicorn worker on
# current macOS. See airflow_shims/setproctitle.py for the crash trace and why
# disabling it costs nothing.
export PYTHONPATH="${REPO_ROOT}/airflow_shims${PYTHONPATH:+:${PYTHONPATH}}"
export AIRFLOW_HOME="${REPO_ROOT}/airflow"
export AIRFLOW__CORE__DAGS_FOLDER="${REPO_ROOT}/dags"
export AIRFLOW__CORE__LOAD_EXAMPLES=False
export AIRFLOW__CORE__EXECUTOR=SequentialExecutor
# macOS Obj-C runtime aborts on fork-after-thread without this.
export OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES
# Stops macOS proxy lookups from stalling/crashing forked subprocesses.
export no_proxy="*"
export AIRFLOW__WEBSERVER__EXPOSE_CONFIG=True
# One gunicorn worker: fewer forks, and a single-user local UI needs no more.
export AIRFLOW__WEBSERVER__WORKERS=1

mkdir -p "${AIRFLOW_HOME}" "${AIRFLOW_HOME}/logs"

airflow db migrate >/dev/null 2>&1 || airflow db init >/dev/null 2>&1

# Idempotent: creating an existing user is a no-op error we can ignore.
airflow users create --username admin --password admin \
  --firstname Mohammed --lastname Alshaigi --role Admin \
  --email alshaigi1212@gmail.com >/dev/null 2>&1 || true

airflow webserver --port 8080 > "${AIRFLOW_HOME}/webserver.log" 2>&1 &
echo "webserver pid $!"
airflow scheduler > "${AIRFLOW_HOME}/scheduler.log" 2>&1 &
echo "scheduler pid $!"

echo "Airflow starting: http://localhost:8080  (admin / admin)"
wait
