"""Stream B producer - field service request lifecycle events.

Each request is a small state machine. The producer holds every open request in
memory and advances one at a time, emitting a message per transition:

    REPORTED -> ACKNOWLEDGED -> DISPATCHED -> ON_SITE -> RESOLVED
                     (CANCELLED possible from any non-terminal state)

So ~2,500 unique request_ids produce ~12,000 messages, roughly 4-6 per request.
That is deliberate: it is what makes the silver MERGE non-trivial. A single
event per request would upsert into an empty table and prove nothing.

Response and resolution times are drawn around the SLA targets in
data/reference/sla_matrix.csv, with a deliberate minority of breaches, so
downstream SLA aggregates have something real to measure.

All data emitted here is SYNTHETIC. See the disclaimer in README.md.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import sys
import time

from datetime import datetime, timedelta, timezone

from confluent_kafka import Producer

from config.settings import settings
from src.contracts.zones import zone_reference

TOPIC = "service_requests_raw"

CATEGORIES = ["MEDICAL", "LOST_PERSON", "CROWD_PRESSURE", "SANITATION",
              "WATER", "WAYFINDING", "SECURITY"]
LANGUAGES = ["ar", "en", "ur", "id", "tr", "fr", "ms", "fa", "bn", "ha"]
LIFECYCLE = ["REPORTED", "ACKNOWLEDGED", "DISPATCHED", "ON_SITE", "RESOLVED"]

# Relative likelihood of each priority within a category - a medical call is
# rarely the lowest priority. These are only *preferences*: the actual options
# are intersected with what sla_matrix.csv defines (see priority_options), so
# the producer can never emit a (category, priority) pair that has no SLA
# target. The SLA matrix must match SOP-OPS-001 exactly, so it is the authority
# and this table bends to it.
PRIORITY_WEIGHTS = {
    "MEDICAL": {"P1": 0.45, "P2": 0.55},
    "CROWD_PRESSURE": {"P1": 0.40, "P2": 0.60},
    "SECURITY": {"P1": 0.65, "P2": 0.35},
    "LOST_PERSON": {"P2": 0.55, "P3": 0.45},
    "WATER": {"P3": 1.0},
    "SANITATION": {"P4": 1.0},
    "WAYFINDING": {"P4": 1.0},
}


def priority_options(category: str, sla: dict) -> tuple[list[str], list[float]]:
    """Priorities defined for this category in the SLA matrix, with weights."""
    allowed = [p for (c, p) in sla if c == category]
    if not allowed:
        raise ValueError(f"sla_matrix.csv defines no priority for category {category}")
    prefs = PRIORITY_WEIGHTS.get(category, {})
    weights = [prefs.get(p, 1.0) for p in allowed]
    return allowed, weights

DESCRIPTIONS = {
    "MEDICAL": ["Elderly pilgrim collapsed near gate, conscious but unresponsive to questions",
                "Heat exhaustion case, patient Name: Abdullah requires shaded triage",
                "Chest pain reported, ambulance corridor requested"],
    "LOST_PERSON": ["Child separated from family, approx 7 years old, wearing green wristband",
                    "Elderly woman lost from group, contact 0555123456 for family liaison",
                    "Missing adult male reported by group leader Name: Yusuf"],
    "CROWD_PRESSURE": ["Counterflow building at the entry ramp, movement slowing",
                       "Density rising above comfortable levels near the eastern approach",
                       "Queue backing up onto the pedestrian bridge"],
    "SANITATION": ["Waste bins overflowing at rest area",
                   "Cleaning required after spillage in the corridor"],
    "WATER": ["Zamzam dispenser empty at station 4",
              "Water station pressure low, refill requested"],
    "WAYFINDING": ["Group requesting directions to the correct level",
                   "Signage obscured by temporary barrier, pilgrims taking wrong turn"],
    "SECURITY": ["Unattended bag reported near the barrier",
                 "Altercation between groups, marshals requested",
                 "Unauthorised vendor blocking an egress route"],
}

CORRUPTION_TYPES = (
    "resolved_before_reported",
    "resolved_without_crew",
    "bad_priority",
    "missing_request_id",
    "updated_before_reported",
    "unknown_zone",
    "bad_category",
    "bad_language",
    "extra_field",
    "malformed_json",
)


def load_sla() -> dict[tuple[str, str], tuple[int, int]]:
    path = settings.reference_dir / "sla_matrix.csv"
    with path.open(encoding="utf-8") as fh:
        return {
            (r["category"], r["priority"]):
                (int(r["response_target_min"]), int(r["resolution_target_min"]))
            for r in csv.DictReader(fh)
        }


def seeded_id(rng: random.Random, prefix: str) -> str:
    """Identifier drawn from the seeded RNG, not uuid4().

    uuid4() ignores --seed, which would make the "reproducibility" flag a lie
    and, more usefully, would stop a second run from re-emitting the SAME
    request_ids with further lifecycle progress. Deriving ids from the seeded
    stream is what makes the late-arriving-updates scenario reproducible - and
    that scenario is what proves the MERGE updates rather than only inserts.
    """
    return f"{prefix}-{rng.getrandbits(48):012X}"


class Request:
    """One in-flight service request advancing through its lifecycle."""

    def __init__(self, rng: random.Random, zone_id: str, reported_at: datetime,
                 sla: dict) -> None:
        self.request_id = seeded_id(rng, "REQ")
        self.zone_id = zone_id
        self.category = rng.choice(CATEGORIES)
        options, weights = priority_options(self.category, sla)
        self.priority = rng.choices(options, weights=weights)[0]
        self.reported_at = reported_at
        self.updated_at = reported_at
        self.status_index = 0
        self.cancelled = False
        self.crew_id: str | None = None
        self.resolved_at: datetime | None = None
        self.language = rng.choices(LANGUAGES, weights=[30, 20, 12, 10, 8, 5, 5, 4, 3, 3])[0]
        self.description = rng.choice(DESCRIPTIONS[self.category])
        self.pilgrim_ref = f"PIL-{rng.randint(10**7, 10**8 - 1)}"
        self.reporter_phone = f"+9665{rng.randint(10**7, 10**8 - 1)}"

        response_target, resolution_target = sla[(self.category, self.priority)]
        # 22% of requests breach their response target; a platform where nothing
        # ever breaches makes the SLA aggregate meaningless.
        breach = rng.random() < 0.22
        self._response_min = (rng.uniform(1.4, 3.0) if breach else rng.uniform(0.25, 0.95)) * response_target
        self._resolution_min = (rng.uniform(1.2, 2.4) if breach else rng.uniform(0.4, 0.95)) * resolution_target

    @property
    def status(self) -> str:
        return "CANCELLED" if self.cancelled else LIFECYCLE[self.status_index]

    @property
    def terminal(self) -> bool:
        return self.cancelled or self.status_index >= len(LIFECYCLE) - 1

    def advance(self, rng: random.Random) -> None:
        """Move to the next state and set the timestamp that state implies."""
        if rng.random() < 0.04:  # cancellations happen from any live state
            self.cancelled = True
            self.updated_at += timedelta(minutes=rng.uniform(1, 15))
            return

        self.status_index += 1
        status = LIFECYCLE[self.status_index]
        if status == "ACKNOWLEDGED":
            self.updated_at = self.reported_at + timedelta(minutes=self._response_min)
        elif status == "DISPATCHED":
            self.crew_id = f"CREW-{rng.randint(1, 60):03d}"
            self.updated_at += timedelta(minutes=rng.uniform(0.5, 4))
        elif status == "ON_SITE":
            self.updated_at += timedelta(minutes=rng.uniform(1, 10))
        elif status == "RESOLVED":
            self.resolved_at = self.reported_at + timedelta(minutes=self._resolution_min)
            # Resolution must not predate arrival on site.
            self.resolved_at = max(self.resolved_at, self.updated_at + timedelta(minutes=1))
            self.updated_at = self.resolved_at

    def to_event(self, rng: random.Random) -> dict:
        return {
            "event_id": seeded_id(rng, "EVT"),
            "request_id": self.request_id,
            "zone_id": self.zone_id,
            "category": self.category,
            "priority": self.priority,
            "status": self.status,
            "reported_at": _iso(self.reported_at),
            "updated_at": _iso(self.updated_at),
            "resolved_at": _iso(self.resolved_at) if self.resolved_at else None,
            "crew_id": self.crew_id,
            "reporter_language": self.language,
            "pilgrim_ref": self.pilgrim_ref,
            "reporter_phone": self.reporter_phone,
            "description": self.description,
            "schema_version": "1.0",
        }


def _iso(dt: datetime) -> str:
    return dt.isoformat().replace("+00:00", "Z")


def corrupt(event: dict, kind: str, rng: random.Random) -> tuple[bytes, str]:
    e = dict(event)
    if kind == "resolved_before_reported":
        e["status"] = "RESOLVED"
        e["crew_id"] = e.get("crew_id") or "CREW-001"
        reported = datetime.fromisoformat(e["reported_at"].replace("Z", "+00:00"))
        e["resolved_at"] = _iso(reported - timedelta(hours=2))
    elif kind == "resolved_without_crew":
        e["status"] = "RESOLVED"
        e["crew_id"] = None
        e["resolved_at"] = e["updated_at"]
    elif kind == "bad_priority":
        e["priority"] = "P9"
    elif kind == "missing_request_id":
        e.pop("request_id")
    elif kind == "updated_before_reported":
        reported = datetime.fromisoformat(e["reported_at"].replace("Z", "+00:00"))
        e["updated_at"] = _iso(reported - timedelta(minutes=30))
    elif kind == "unknown_zone":
        e["zone_id"] = "MINA_CAMP_Z"
    elif kind == "bad_category":
        e["category"] = "CATERING"
    elif kind == "bad_language":
        e["reporter_language"] = "xx"
    elif kind == "extra_field":
        e["triage_notes"] = "undeclared column"
    elif kind == "malformed_json":
        raw = json.dumps(e).encode()
        return raw[: len(raw) // 2], kind
    else:
        raise ValueError(f"unknown corruption kind: {kind}")
    return json.dumps(e).encode(), kind


def main() -> int:
    ap = argparse.ArgumentParser(description="Emit synthetic service request lifecycle events.")
    ap.add_argument("--events", type=int, default=12_000, help="total messages to emit")
    ap.add_argument("--requests", type=int, default=2_500, help="unique request_ids")
    ap.add_argument("--rate", type=float, default=0.0)
    ap.add_argument("--corrupt-rate", type=float, default=0.07)
    ap.add_argument("--scenario", default=None, choices=(None,) + CORRUPTION_TYPES)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--sim-start", default="2026-05-24T00:00:00Z")
    ap.add_argument("--sim-days", type=int, default=7)
    args = ap.parse_args()

    rng = random.Random(args.seed)
    sla = load_sla()
    zone_ids = sorted(zone_reference().keys())
    sim_start = datetime.fromisoformat(args.sim_start.replace("Z", "+00:00"))
    window = timedelta(days=args.sim_days)

    producer = Producer({
        "bootstrap.servers": settings.kafka_bootstrap_servers,
        "linger.ms": 50,
        "compression.type": "lz4",
        "queue.buffering.max.messages": 200_000,
    })

    # Create every request up front with a reported_at spread across the window,
    # then advance them round-robin. This interleaves requests on the topic the
    # way a real stream would, instead of emitting each request's whole history
    # contiguously.
    open_requests: list[Request] = []
    for _ in range(args.requests):
        reported_at = sim_start + timedelta(seconds=rng.uniform(0, window.total_seconds() * 0.85))
        open_requests.append(Request(rng, rng.choice(zone_ids), reported_at, sla))

    sent = corrupted = 0
    started = time.time()
    print(f"producing up to {args.events} lifecycle messages "
          f"for {args.requests} unique requests over {args.sim_days} simulated days", flush=True)

    def emit(req: Request) -> None:
        nonlocal sent, corrupted
        event = req.to_event(rng)
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
                # Key by request_id so all events for one request land on the
                # same partition and stay in order.
                producer.produce(TOPIC, key=req.request_id.encode(), value=payload)
                break
            except BufferError:
                producer.poll(0.5)
        sent += 1
        if args.rate:
            time.sleep(1.0 / args.rate)

    # Initial REPORTED for every request.
    for req in open_requests:
        if sent >= args.events:
            break
        emit(req)

    # Then advance until everything is terminal or the budget is spent.
    while open_requests and sent < args.events:
        still_open = []
        for req in open_requests:
            if sent >= args.events:
                still_open.append(req)
                continue
            req.advance(rng)
            emit(req)
            if not req.terminal:
                still_open.append(req)
        open_requests = still_open
        producer.poll(0)
        if sent % 2_000 < len(open_requests):
            print(f"  {sent:,} sent ({corrupted:,} corrupt), {len(open_requests):,} still open", flush=True)

    producer.flush(60)
    print(f"DONE: {sent:,} messages to '{TOPIC}' for {args.requests:,} unique requests "
          f"({corrupted:,} corrupt, {corrupted / max(sent,1):.1%}) in {time.time() - started:.1f}s",
          flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
