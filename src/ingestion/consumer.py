"""Kafka -> contract validation -> bronze Delta (or DLQ).

Offset handling
---------------
`enable.auto.commit` is False and offsets are committed only *after* the batch
has been durably written to Delta. Auto-commit would advance the offset on poll,
so a crash between poll and write would lose those records silently - the worst
kind of data loss, because nothing reports it.

Committing after the write gives at-least-once delivery: a crash between write
and commit replays the batch, so bronze can contain duplicates. That is a
deliberate trade (losing data is worse than duplicating it), and it is why
silver deduplicates on `event_id` rather than trusting the stream to be unique.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone

import pyarrow as pa
from confluent_kafka import Consumer, KafkaError, Producer

from config.settings import settings
from src.contracts.occupancy import ZoneOccupancyEvent
from src.ingestion.dlq import DLQWriter
from src.lakehouse import delta_io
from src.lineage.emitter import lineage_run

CONSUMER_GROUP = "bronze-ingest-v1"

BRONZE_SCHEMA = pa.schema([
    ("event_id", pa.string()),
    ("zone_id", pa.string()),
    ("gate_id", pa.string()),
    ("event_time", pa.timestamp("us", tz="UTC")),
    ("entries", pa.int32()),
    ("exits", pa.int32()),
    ("occupancy_estimate", pa.int32()),
    ("sensor_status", pa.string()),
    ("schema_version", pa.string()),
    # Ingest metadata - bronze records where a row came from, so any row can be
    # traced back to the exact broker coordinates that produced it.
    ("_kafka_topic", pa.string()),
    ("_kafka_partition", pa.int32()),
    ("_kafka_offset", pa.int64()),
    ("_ingested_at", pa.timestamp("us", tz="UTC")),
    ("_source_file", pa.string()),
    ("ingest_date", pa.string()),
])


def _to_arrow(records: list[dict]) -> pa.Table:
    cols = {name: [r[name] for r in records] for name in BRONZE_SCHEMA.names}
    return pa.table(cols, schema=BRONZE_SCHEMA)


def consume(topic: str, max_messages: int, batch_size: int, idle_timeout: float,
            bronze_table: str) -> dict[str, int]:
    consumer = Consumer({
        "bootstrap.servers": settings.kafka_bootstrap_servers,
        "group.id": CONSUMER_GROUP,
        "auto.offset.reset": "earliest",
        # Manual commit - see module docstring.
        "enable.auto.commit": False,
        "max.poll.interval.ms": 600_000,
    })
    consumer.subscribe([topic])

    dlq_producer = Producer({"bootstrap.servers": settings.kafka_bootstrap_servers})
    dlq = DLQWriter(dlq_producer, CONSUMER_GROUP)

    accepted = rejected = 0
    batch: list[dict] = []
    last_message_at = time.time()
    ingested_at = datetime.now(timezone.utc)

    def flush() -> None:
        nonlocal batch
        if batch:
            delta_io.append(bronze_table, _to_arrow(batch), partition_by=["ingest_date"])
            batch = []
        dlq.flush_to_quarantine()
        # Commit only once both the bronze rows and the quarantine rows are on
        # disk. Everything in this batch is now durably accounted for.
        consumer.commit(asynchronous=False)

    with lineage_run(
        f"ingest_bronze_{topic}",
        inputs=[f"kafka://{topic}"],
        outputs=[bronze_table, "quarantine"],
    ) as run:
        try:
            while accepted + rejected < max_messages:
                msg = consumer.poll(1.0)
                if msg is None:
                    if time.time() - last_message_at > idle_timeout:
                        print(f"  idle for {idle_timeout}s - stopping", flush=True)
                        break
                    continue
                if msg.error():
                    if msg.error().code() == KafkaError._PARTITION_EOF:
                        continue
                    raise RuntimeError(f"kafka error: {msg.error()}")

                last_message_at = time.time()
                raw = msg.value()
                try:
                    # Validate the raw BYTES, not a pre-parsed dict: Pydantic's
                    # strict JSON mode accepts an ISO string as a datetime while
                    # still rejecting a quoted integer. Parsing first would put
                    # us in Python mode and break that distinction.
                    event = ZoneOccupancyEvent.model_validate_json(raw)
                except Exception as exc:  # ValidationError or JSON decode failure
                    dlq.reject(raw=raw, source_topic=topic,
                               partition=msg.partition(), offset=msg.offset(), exc=exc)
                    rejected += 1
                else:
                    d = event.model_dump()
                    d["event_time"] = event.event_time
                    d["_kafka_topic"] = topic
                    d["_kafka_partition"] = msg.partition()
                    d["_kafka_offset"] = msg.offset()
                    d["_ingested_at"] = ingested_at
                    d["_source_file"] = f"kafka://{topic}/p{msg.partition()}"
                    d["ingest_date"] = ingested_at.date().isoformat()
                    batch.append(d)
                    accepted += 1

                if len(batch) >= batch_size:
                    flush()
                    print(f"  committed batch: accepted={accepted:,} rejected={rejected:,}", flush=True)

            flush()
        finally:
            consumer.close()

        run.record_output_rows(bronze_table, accepted)
        run.record_output_rows("quarantine", rejected)

    return {"accepted": accepted, "rejected": rejected}


def main() -> int:
    ap = argparse.ArgumentParser(description="Consume Kafka -> validate -> bronze Delta / DLQ")
    ap.add_argument("--topic", default="zone_occupancy_raw")
    ap.add_argument("--bronze-table", default="bronze_zone_occupancy")
    ap.add_argument("--max-messages", type=int, default=1_000_000)
    ap.add_argument("--batch-size", type=int, default=10_000)
    ap.add_argument("--idle-timeout", type=float, default=10.0)
    args = ap.parse_args()

    started = time.time()
    stats = consume(args.topic, args.max_messages, args.batch_size,
                    args.idle_timeout, args.bronze_table)
    total = stats["accepted"] + stats["rejected"]
    print(json.dumps({
        **stats,
        "total": total,
        "rejection_rate_pct": round(100 * stats["rejected"] / max(total, 1), 2),
        "elapsed_seconds": round(time.time() - started, 1),
        "bronze_table": args.bronze_table,
    }, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
