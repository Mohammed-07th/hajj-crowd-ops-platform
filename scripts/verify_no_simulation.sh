#!/usr/bin/env bash
# Anti-substitution audit.
#
# Fails if any rubric-forfeiting substitution appears in the codebase. The point
# is that a substitution is invisible in a code review - a class called
# "KafkaProducer" that wraps a queue looks fine until you read it - so this runs
# after every phase and its output is committed.
#
# Adapted from the build spec for the approved stack change: Delta is provided
# by delta-rs (`deltalake`) rather than pyspark + delta-spark, so the dependency
# check looks for `deltalake` and `polars`. Both write real Delta tables with a
# real _delta_log; neither is a pandas/Parquet stand-in, which is what the
# original check existed to catch.
set -u
FOUND=0

check() {  # $1 = pattern, $2 = why it is disqualifying
  # Exclude the two scripts that check FOR these patterns: both contain every
  # banned string as a literal, so without this they report themselves and the
  # audit can never pass.
  if grep -rEn --include='*.py' --include='*.sh' --include='*.yml' \
       --exclude='verify_no_simulation.sh' --exclude='rubric_selfcheck.py' \
       "$1" src/ dags/ scripts/ 2>/dev/null; then
    echo "  ✗ DISQUALIFYING: $2"
    FOUND=1
  fi
}

cd "$(dirname "$0")/.."

echo "== anti-substitution audit =="
check 'asyncio\.Queue|queue\.Queue|MockBroker|FakeKafka|InMemoryBroker' \
      'a queue standing in for Kafka forfeits Deliverable 1 (20 pts)'
check 'to_parquet|pq\.write_table' \
      'pandas/Parquet instead of Delta forfeits Deliverable 2 (25 pts)'
check 'class .*Orchestrator|import schedule|while True:.*sleep.*run_pipeline' \
      'a custom scheduler instead of Airflow forfeits Deliverable 4 (15 pts)'
check 'cosine_similarity\(.*np\.|InMemoryVectorStore' \
      'brute-force numpy instead of a real vector store forfeits Deliverable 3 (25 pts)'
check 'print\(.*lineage.*emitted|# TODO.*openlineage' \
      'faked lineage forfeits Deliverable 5 (15 pts)'

echo "== required real dependencies =="
for pkg in confluent_kafka deltalake polars qdrant_client great_expectations openlineage; do
  ./.venv/bin/python -c "import $pkg" 2>/dev/null && echo "  ✓ $pkg importable" || { echo "  ✗ $pkg MISSING"; FOUND=1; }
done
./.venv-airflow/bin/python -c "import airflow" 2>/dev/null \
  && echo "  ✓ airflow importable (separate venv)" || { echo "  ✗ airflow MISSING"; FOUND=1; }

echo "== real artifacts on disk =="
for t in bronze_zone_occupancy silver_zone_occupancy gold_zone_hourly quarantine; do
  if [ -d "delta/$t/_delta_log" ]; then
    echo "  ✓ delta/$t has a real _delta_log ($(ls delta/$t/_delta_log/*.json 2>/dev/null | wc -l | tr -d ' ') commit(s))"
  else
    echo "  ⚠ delta/$t not built yet"
  fi
done

echo "== real broker =="
if docker exec hajj-kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 --list >/dev/null 2>&1; then
  echo "  ✓ Kafka broker responds to a real admin call"
else
  echo "  ✗ Kafka broker not reachable"; FOUND=1
fi

echo "== real lineage events =="
if [ -s docs/evidence/lineage/events.jsonl ]; then
  for state in START COMPLETE FAIL; do
    n=$(grep -c "\"eventType\": \"$state\"" docs/evidence/lineage/events.jsonl || true)
    echo "  ✓ $state events emitted: $n"
  done
else
  echo "  ⚠ no lineage events yet"
fi

echo "== secrets =="
git ls-files | grep -qx '.env' && { echo "  ✗ .env is tracked by git"; FOUND=1; } || echo "  ✓ .env not tracked"
git log -p 2>/dev/null | grep -qE 'sk-or-v1-[A-Za-z0-9]{20}' && { echo "  ✗ API key found in git history"; FOUND=1; } || echo "  ✓ no key in history"

[ $FOUND -eq 0 ] && echo "AUDIT PASSED" || { echo "AUDIT FAILED — fix before continuing"; exit 1; }
