"""Stream A producer - zone occupancy telemetry into Kafka.

Two things this deliberately does NOT do:

1. It does not run in real time. Seven simulated days are emitted in a few
   minutes of wall clock, controlled by --sim-start / --sim-days / --rate. Gold
   tables need hours and days to aggregate over; waiting a week is not an
   option and sleeping between events proves nothing.

2. It does not emit a flat line. Occupancy follows prayer-time peaks, a Jamarat
   surge on the simulated 10th of Dhul-Hijjah, an Arafat day, a Muzdalifah
   overnight spike and quiet hours. Without that shape `minutes_above_90pct` is
   always zero and the entire gold layer looks pointless in a demo.

All data emitted here is SYNTHETIC. See the disclaimer in README.md.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone

from confluent_kafka import Producer

from config.settings import settings
from src.contracts.zones import zone_reference

TOPIC = "zone_occupancy_raw"

# Local Makkah time is UTC+3; the curve below is expressed in local hours and
# converted at use, because "the Dhuhr peak" is a local-time phenomenon.
MAKKAH_UTC_OFFSET = 3

# Approximate Makkah prayer times (local hours, decimal). Real times shift by a
# few minutes across the week; that precision does not change the crowd shape.
PRAYER_HOURS = [4.5, 12.3, 15.7, 19.1, 20.6]

# Simulated day index -> the Hajj day it represents. Day 2 is 9 Dhul-Hijjah
# (Arafat), day 3 is 10 Dhul-Hijjah (Nahr / first Jamarat stoning).
ARAFAT_DAY = 2
NAHR_DAY = 3
JAMARAT_DAYS = (3, 4, 5)

CORRUPTION_TYPES = (
    "over_capacity",
    "negative_entries",
    "unknown_zone",
    "future_timestamp",
    "string_for_int",
    "bad_sensor_status",
    "missing_event_id",
    "malformed_json",
    "extra_field",
    "null_zone_id",
)


def _prayer_boost(local_hour: float) -> float:
    """Bell-shaped bump around each prayer time."""
    boost = 0.0
    for p in PRAYER_HOURS:
        delta = min(abs(local_hour - p), 24 - abs(local_hour - p))
        if delta < 1.5:
            boost += 0.35 * (1 - delta / 1.5)
    return boost


def occupancy_factor(zone_type: str, sim_dt: datetime, day_index: int, rng: random.Random) -> float:
    """Fraction of a zone's rated capacity that is occupied at `sim_dt`.

    Returns roughly 0.0-1.05. Values are intentionally allowed to approach and
    occasionally exceed 0.9 so the gold layer's minutes_above_80pct /
    minutes_above_90pct columns are non-zero for the busy zones.
    """
    local_hour = (sim_dt.hour + sim_dt.minute / 60 + MAKKAH_UTC_OFFSET) % 24

    if zone_type in ("TAWAF", "SAI", "ENTRANCE"):
        # Continuous ritual: never empty, dips 01:00-04:00, peaks at prayers.
        base = 0.45 + 0.20 * _daynight(local_hour)
        factor = base + _prayer_boost(local_hour)
        if day_index in (ARAFAT_DAY,):
            factor *= 0.55  # pilgrims are at Arafat, not the Haram
        if day_index == NAHR_DAY and local_hour > 14:
            factor *= 1.15  # tawaf al-ifadah returns
    elif zone_type == "RITUAL":
        # Jamarat: empty except on the stoning days, with a sharp daytime surge.
        if day_index not in JAMARAT_DAYS:
            factor = 0.02
        elif 8 <= local_hour <= 16:
            peak = 12.0
            factor = 0.30 + 0.65 * max(0.0, 1 - abs(local_hour - peak) / 4.5)
        else:
            factor = 0.10
    elif zone_type == "ACCOMMODATION":
        # Mina camps: full overnight, emptier during the day.
        factor = 0.75 - 0.45 * _daynight(local_hour)
        if day_index == ARAFAT_DAY:
            factor = 0.10
    elif zone_type == "GATHERING":
        # Arafat: one day only, dawn to sunset.
        factor = 0.85 if (day_index == ARAFAT_DAY and 5 <= local_hour <= 19) else 0.01
    elif zone_type == "OVERNIGHT":
        # Muzdalifah: the night of 9->10 Dhul-Hijjah only.
        in_window = (day_index == ARAFAT_DAY and local_hour >= 19) or (
            day_index == NAHR_DAY and local_hour <= 5
        )
        factor = 0.90 if in_window else 0.01
    elif zone_type == "TOURISM":
        factor = 0.55 if 9 <= local_hour <= 17 else 0.03
    else:
        factor = 0.3

    return max(0.0, factor * rng.uniform(0.90, 1.10))


def _daynight(local_hour: float) -> float:
    """1.0 at midday, 0.0 at 03:00 - a smooth day/night weight."""
    import math

    return 0.5 * (1 + math.cos((local_hour - 15) / 24 * 2 * math.pi))


def build_event(zone_id: str, zone: dict, sim_dt: datetime, day_index: int, rng: random.Random) -> dict:
    capacity = int(zone["capacity"])
    occupancy = int(capacity * occupancy_factor(str(zone["zone_type"]), sim_dt, day_index, rng))
    # Entries/exits are the flow that produced this occupancy, not independent
    # numbers - a reading where they contradict occupancy would be noise.
    churn = max(1, int(occupancy * rng.uniform(0.01, 0.04)))
    entries = churn + rng.randint(0, churn // 2)
    exits = max(0, churn - rng.randint(0, churn // 3))

    status = "OK"
    roll = rng.random()
    if roll > 0.97:
        status = "DEGRADED"
    elif roll > 0.995:
        status = "OFFLINE"

    return {
        "event_id": str(uuid.uuid4()),
        "zone_id": zone_id,
        "gate_id": f"G-{zone_id}-{rng.choice('NSEW')}",
        "event_time": sim_dt.isoformat().replace("+00:00", "Z"),
        "entries": entries,
        "exits": exits,
        "occupancy_estimate": occupancy,
        "sensor_status": status,
        "schema_version": "1.0",
    }


def corrupt(event: dict, kind: str, rng: random.Random) -> tuple[bytes, str]:
    """Return (payload_bytes, corruption_kind).

    Each corruption violates exactly one contract rule, so the DLQ evidence
    shows a one-to-one mapping between the injected fault and the rejection.
    """
    e = dict(event)
    if kind == "over_capacity":
        e["occupancy_estimate"] = 999_999
    elif kind == "negative_entries":
        e["entries"] = -42
    elif kind == "unknown_zone":
        e["zone_id"] = "MATAF_99"
    elif kind == "future_timestamp":
        e["event_time"] = (datetime.now(timezone.utc) + timedelta(days=3)).isoformat().replace("+00:00", "Z")
    elif kind == "string_for_int":
        # The strict-mode headline case: valid-looking JSON, wrong type.
        e["entries"] = "1500"
    elif kind == "bad_sensor_status":
        e["sensor_status"] = "BROKEN"
    elif kind == "missing_event_id":
        e.pop("event_id")
    elif kind == "extra_field":
        e["undeclared_column"] = "surprise"
    elif kind == "null_zone_id":
        e["zone_id"] = None
    elif kind == "malformed_json":
        raw = json.dumps(e).encode()
        return raw[: len(raw) // 2], kind  # truncated bytes - fails to parse
    else:
        raise ValueError(f"unknown corruption kind: {kind}")
    return json.dumps(e).encode(), kind


def main() -> int:
    ap = argparse.ArgumentParser(description="Emit synthetic zone occupancy events to Kafka.")
    ap.add_argument("--events", type=int, default=200_000, help="total events to emit")
    ap.add_argument("--rate", type=float, default=0.0, help="events/sec (0 = as fast as possible)")
    ap.add_argument("--corrupt-rate", type=float, default=0.07)
    ap.add_argument("--scenario", default=None, choices=(None,) + CORRUPTION_TYPES,
                    help="emit only this corruption type (for the failure demos)")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--sim-start", default="2026-05-24T00:00:00Z")
    ap.add_argument("--sim-days", type=int, default=7)
    args = ap.parse_args()

    rng = random.Random(args.seed)
    zones = zone_reference()
    zone_ids = sorted(zones.keys())

    sim_start = datetime.fromisoformat(args.sim_start.replace("Z", "+00:00"))
    total_seconds = args.sim_days * 86400
    ticks = max(1, args.events // len(zone_ids))
    step = timedelta(seconds=total_seconds / ticks)

    producer = Producer({
        "bootstrap.servers": settings.kafka_bootstrap_servers,
        "linger.ms": 50,
        "batch.size": 262_144,
        "compression.type": "lz4",
        "queue.buffering.max.messages": 500_000,
    })

    sent = corrupted = 0
    started = time.time()
    print(f"producing {args.events} events over {args.sim_days} simulated days "
          f"({len(zone_ids)} zones x {ticks} ticks, step={step})", flush=True)

    for tick in range(ticks):
        sim_dt = sim_start + step * tick
        day_index = (sim_dt - sim_start).days
        for zone_id in zone_ids:
            if sent >= args.events:
                break
            event = build_event(zone_id, zones[zone_id], sim_dt, day_index, rng)

            if args.scenario:
                payload, _ = corrupt(event, args.scenario, rng)
                corrupted += 1
            elif rng.random() < args.corrupt_rate:
                payload, _ = corrupt(event, rng.choice(CORRUPTION_TYPES), rng)
                corrupted += 1
            else:
                payload = json.dumps(event).encode()

            while True:
                try:
                    producer.produce(TOPIC, key=zone_id.encode(), value=payload)
                    break
                except BufferError:
                    # Local queue full - let librdkafka drain rather than drop.
                    producer.poll(0.5)

            sent += 1
            if sent % 25_000 == 0:
                producer.poll(0)
                print(f"  {sent:,} sent ({corrupted:,} corrupt) "
                      f"sim_time={sim_dt.isoformat()}", flush=True)
            if args.rate:
                time.sleep(1.0 / args.rate)
        producer.poll(0)
        if sent >= args.events:
            break

    producer.flush(60)
    elapsed = time.time() - started
    print(f"DONE: {sent:,} events to '{TOPIC}' "
          f"({corrupted:,} deliberately corrupt, {corrupted / max(sent,1):.1%}) "
          f"in {elapsed:.1f}s", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
