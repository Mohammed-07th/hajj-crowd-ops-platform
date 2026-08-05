#!/usr/bin/env bash
# Reset to a clean slate so a pipeline run is reproducible from zero:
# drop the Delta tables, recreate the Kafka topics (which resets offsets), and
# clear the lineage event stream.
#
# This exists because the pipeline is deliberately at-least-once and
# append-based at the bronze layer: rerunning the producer without a reset adds
# a second week of events rather than replacing the first.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "== dropping delta tables =="
rm -rf delta
echo "  removed ./delta"

echo "== recreating kafka topics (resets consumer group offsets) =="
for t in zone_occupancy_raw service_requests_raw dlq_zone_occupancy dlq_service_requests; do
  docker exec hajj-kafka /opt/kafka/bin/kafka-topics.sh \
    --bootstrap-server localhost:9092 --delete --topic "$t" >/dev/null 2>&1 || true
done
./scripts/create_topics.sh 2>&1 | grep -v "^WARNING" || true

echo "== clearing lineage event stream =="
: > docs/evidence/lineage/events.jsonl
echo "  truncated docs/evidence/lineage/events.jsonl"

echo "RESET COMPLETE"
