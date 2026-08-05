"""Dead-letter envelope.

A rejected message is only useful if you can answer "why?" without re-running
the pipeline. The envelope therefore carries the original bytes, a
human-readable reason, the machine-readable rule identifiers Pydantic raised,
and the exact Kafka coordinates so the message can be found again on the broker.
"""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field


class DLQEnvelope(BaseModel):
    # Not strict: this model is constructed by our own code, never parsed from
    # an untrusted source. Strictness here would buy nothing.
    original_payload: str
    rejection_reason: str
    failed_rules: list[str] = Field(default_factory=list)
    source_topic: str
    partition: int
    offset: int
    rejected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    consumer_group: str
