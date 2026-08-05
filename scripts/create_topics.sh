#!/usr/bin/env bash
# Creates the four Kafka topics used by the platform.
#
# Auto-topic-creation is disabled on the broker, so every topic this pipeline
# uses is created here with an explicit partition count. That makes the DLQ a
# first-class topic rather than something that springs into existence the first
# time a producer typos a name.
set -euo pipefail

KAFKA_CONTAINER="${KAFKA_CONTAINER:-hajj-kafka}"
BOOTSTRAP="${KAFKA_BOOTSTRAP_INTERNAL:-localhost:9092}"
KT="/opt/kafka/bin/kafka-topics.sh"

create() {  # $1 = topic, $2 = partitions
  docker exec "$KAFKA_CONTAINER" "$KT" \
    --bootstrap-server "$BOOTSTRAP" \
    --create --if-not-exists \
    --topic "$1" --partitions "$2" --replication-factor 1
}

echo "== creating topics =="
# Main streams get 3 partitions so the consumer's partition/offset metadata in
# bronze and in the DLQ envelope is non-trivial (offset 0 on partition 0 for
# everything would prove nothing).
create zone_occupancy_raw    3
create service_requests_raw  3
# Dead-letter topics are single-partition: ordering of rejections is more
# useful than throughput, and volume here is by definition low.
create dlq_zone_occupancy    1
create dlq_service_requests  1

echo
echo "== topics now on the broker =="
docker exec "$KAFKA_CONTAINER" "$KT" --bootstrap-server "$BOOTSTRAP" --list
