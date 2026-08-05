"""Dead-letter routing.

A rejected record goes to two places on purpose:

  1. the Kafka topic `dlq_<source>` - so a downstream consumer, an alerting
     service or a replay tool can react to rejections in real time;
  2. the `quarantine` Delta table - so rejections are *queryable* alongside the
     rest of the lakehouse ("how many records did we drop yesterday, by rule?"
     is a SQL question, not a log-grepping question).

Both carry the rejection reason. A DLQ without the reason is just a second copy
of the corrupt data.
"""

from __future__ import annotations

import json
from typing import Iterable

import pyarrow as pa
from confluent_kafka import Producer
from pydantic import ValidationError

from src.contracts.envelopes import DLQEnvelope
from src.lakehouse import delta_io

QUARANTINE_TABLE = "quarantine"


def describe_validation_error(exc: Exception) -> tuple[str, list[str]]:
    """Turn an exception into (human reason, machine rule ids).

    Pydantic reports every failing field; we join them so a single envelope
    explains a record that broke more than one rule.
    """
    if isinstance(exc, ValidationError):
        parts, rules = [], []
        for err in exc.errors():
            loc = ".".join(str(p) for p in err["loc"]) or "<root>"
            parts.append(f"{loc}: {err['msg']}")
            rules.append(err["type"])
        return "; ".join(parts), rules
    if isinstance(exc, json.JSONDecodeError):
        return f"json decode failure: {exc.msg} at pos {exc.pos}", ["json_invalid"]
    return f"{type(exc).__name__}: {exc}", [type(exc).__name__]


class DLQWriter:
    def __init__(self, producer: Producer, consumer_group: str) -> None:
        self._producer = producer
        self._group = consumer_group
        self._buffer: list[DLQEnvelope] = []

    def reject(self, *, raw: bytes, source_topic: str, partition: int, offset: int,
               exc: Exception) -> DLQEnvelope:
        reason, rules = describe_validation_error(exc)
        envelope = DLQEnvelope(
            # errors="replace" so truncated/invalid UTF-8 (the malformed-JSON
            # corruption) is still representable rather than blowing up here.
            original_payload=raw.decode("utf-8", errors="replace"),
            rejection_reason=reason,
            failed_rules=rules,
            source_topic=source_topic,
            partition=partition,
            offset=offset,
            consumer_group=self._group,
        )
        self._producer.produce(
            f"dlq_{source_topic.replace('_raw', '')}",
            key=str(offset).encode(),
            value=envelope.model_dump_json().encode(),
        )
        self._buffer.append(envelope)
        return envelope

    def flush_to_quarantine(self) -> int:
        """Append buffered rejections to the quarantine Delta table."""
        if not self._buffer:
            self._producer.flush(30)
            return 0
        rows = [e.model_dump() for e in self._buffer]
        table = pa.table({
            "original_payload": [r["original_payload"] for r in rows],
            "rejection_reason": [r["rejection_reason"] for r in rows],
            "failed_rules": [json.dumps(r["failed_rules"]) for r in rows],
            "source_topic": [r["source_topic"] for r in rows],
            "partition": pa.array([r["partition"] for r in rows], type=pa.int32()),
            "offset": pa.array([r["offset"] for r in rows], type=pa.int64()),
            "rejected_at": pa.array([r["rejected_at"] for r in rows], type=pa.timestamp("us", tz="UTC")),
            "consumer_group": [r["consumer_group"] for r in rows],
        })
        n = delta_io.append(QUARANTINE_TABLE, table)
        self._buffer.clear()
        self._producer.flush(30)
        return n

    @property
    def pending(self) -> int:
        return len(self._buffer)
