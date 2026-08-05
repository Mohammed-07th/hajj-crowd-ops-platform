"""Failure demo 1 — contract rejection with recorded reasons.

Produces exactly 100 occupancy events of which 20 are deliberately malformed,
consumes them, and prints what landed where. Uses a dedicated topic and consumer
group so it can run against a live pipeline without disturbing it.

Expected: 80 accepted to bronze, 20 routed to the DLQ, every rejection carrying a
machine-readable rule id and a human-readable reason — including at least one
strict-mode coercion rejection, where the JSON string "1500" is refused for an
integer field.
"""

from __future__ import annotations

import json
import random
import subprocess
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone

import polars as pl
from confluent_kafka import Consumer, Producer

from config.settings import settings
from src.contracts.occupancy import ZoneOccupancyEvent
from src.contracts.zones import zone_reference
from src.ingestion.dlq import describe_validation_error
from src.ingestion.producers.occupancy_producer import CORRUPTION_TYPES, build_event, corrupt

TOPIC = "demo_bad_records"
GROUP = "demo-bad-records-v1"
TOTAL = 100
CORRUPT = 20


def ensure_topic() -> None:
    subprocess.run(
        ["docker", "exec", "hajj-kafka", "/opt/kafka/bin/kafka-topics.sh",
         "--bootstrap-server", "localhost:9092", "--delete", "--topic", TOPIC],
        capture_output=True,
    )
    subprocess.run(
        ["docker", "exec", "hajj-kafka", "/opt/kafka/bin/kafka-topics.sh",
         "--bootstrap-server", "localhost:9092", "--create", "--if-not-exists",
         "--topic", TOPIC, "--partitions", "1", "--replication-factor", "1"],
        capture_output=True, check=True,
    )


def main() -> int:
    rng = random.Random(1234)
    zones = zone_reference()
    zone_ids = sorted(zones)

    print("=" * 84)
    print(f"FAILURE DEMO 1 — contract rejection ({TOTAL} events, {CORRUPT} malformed)")
    print("=" * 84)

    ensure_topic()
    producer = Producer({"bootstrap.servers": settings.kafka_bootstrap_servers})

    # One of each corruption type, then fill to 20 by cycling.
    injected: list[str] = [CORRUPTION_TYPES[i % len(CORRUPTION_TYPES)] for i in range(CORRUPT)]
    corrupt_positions = set(rng.sample(range(TOTAL), CORRUPT))
    sim = datetime.now(timezone.utc) - timedelta(days=1)

    plan: list[tuple[int, str | None]] = []
    next_corruption = 0
    for i in range(TOTAL):
        zone_id = zone_ids[i % len(zone_ids)]
        event = build_event(zone_id, zones[zone_id], sim + timedelta(seconds=i * 10), 0, rng)
        if i in corrupt_positions:
            kind = injected[next_corruption]
            next_corruption += 1
            payload, _ = corrupt(event, kind, rng)
            plan.append((i, kind))
        else:
            payload = json.dumps(event).encode()
            plan.append((i, None))
        producer.produce(TOPIC, key=str(i).encode(), value=payload)
    producer.flush(30)
    print(f"\nproduced {TOTAL} events to '{TOPIC}' "
          f"({CORRUPT} malformed, {len(set(injected))} distinct corruption types)\n")

    consumer = Consumer({
        "bootstrap.servers": settings.kafka_bootstrap_servers,
        "group.id": GROUP,
        "auto.offset.reset": "earliest",
        "enable.auto.commit": False,
    })
    consumer.subscribe([TOPIC])

    accepted = 0
    rejections: list[dict] = []
    deadline = time.time() + 30
    while accepted + len(rejections) < TOTAL and time.time() < deadline:
        msg = consumer.poll(1.0)
        if msg is None or msg.error():
            continue
        try:
            ZoneOccupancyEvent.model_validate_json(msg.value())
        except Exception as exc:
            reason, rules = describe_validation_error(exc)
            rejections.append({
                "offset": msg.offset(),
                "injected": dict(plan)[msg.offset()] if msg.offset() < TOTAL else "?",
                "rules": ",".join(rules),
                "reason": reason[:96],
            })
        else:
            accepted += 1
    consumer.close()

    print("-" * 84)
    print(f"RESULT:  accepted -> bronze: {accepted}     rejected -> DLQ: {len(rejections)}")
    print("-" * 84)

    df = pl.DataFrame(rejections)
    print("\nRejections by injected corruption type and the rule that caught it:\n")
    print(df.group_by(["injected", "rules"]).agg(pl.len().alias("n")).sort("injected"))

    print("\nEvery rejection with its reason:\n")
    for r in sorted(rejections, key=lambda r: r["offset"]):
        print(f"  offset={r['offset']:>3}  injected={r['injected']:<26} "
              f"rule={r['rules']:<20} {r['reason']}")

    coercion = [r for r in rejections if r["injected"] == "string_for_int"]
    print("\n" + "=" * 84)
    print("STRICT-MODE COERCION REJECTION (the headline case)")
    print("=" * 84)
    for r in coercion:
        print(f"  The JSON string \"1500\" was refused for an integer field:")
        print(f"    rule   : {r['rules']}")
        print(f"    reason : {r['reason']}")
    print("\n  Without ConfigDict(strict=True), Pydantic would coerce \"1500\" to 1500")
    print("  and this record would enter bronze looking perfectly valid.")

    ok = accepted == TOTAL - CORRUPT and len(rejections) == CORRUPT and coercion
    print("\n" + ("DEMO PASSED" if ok else "DEMO FAILED — unexpected counts"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
