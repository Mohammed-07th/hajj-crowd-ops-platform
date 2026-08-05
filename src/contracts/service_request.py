"""Data contract for Stream B - field service requests.

Emitted once per state change, so the same `request_id` appears several times
with a rising `updated_at`. That is what makes the silver MERGE a real upsert
rather than an append with extra steps.

The conditional-required rules below (`crew_id` once a crew is assigned,
`resolved_at` once resolved) are the interesting part: they cannot be expressed
as field constraints because they depend on `status`. A record that violates
them is structurally valid JSON with correct types - only a cross-field rule
catches it.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from src.contracts.zones import valid_zone_ids

FUTURE_TOLERANCE = timedelta(minutes=5)

# Statuses at which a crew must have been assigned.
CREW_REQUIRED_STATUSES = ("DISPATCHED", "ON_SITE", "RESOLVED")


class ServiceRequestEvent(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    event_id: str
    request_id: str  # BUSINESS KEY for the MERGE
    zone_id: str
    category: Literal["MEDICAL", "LOST_PERSON", "CROWD_PRESSURE",
                      "SANITATION", "WATER", "WAYFINDING", "SECURITY"]
    priority: Literal["P1", "P2", "P3", "P4"]
    status: Literal["REPORTED", "ACKNOWLEDGED", "DISPATCHED",
                    "ON_SITE", "RESOLVED", "CANCELLED"]
    reported_at: datetime
    updated_at: datetime
    resolved_at: datetime | None = None
    crew_id: str | None = None
    reporter_language: Literal["ar", "en", "ur", "id", "tr", "fr", "ms", "fa", "bn", "ha"]
    pilgrim_ref: str | None = None      # PII - hashed in silver
    reporter_phone: str | None = None   # PII - hashed in silver
    description: str                    # may contain names - redacted before embedding
    schema_version: str = "1.0"

    @field_validator("zone_id")
    @classmethod
    def zone_must_be_known(cls, v: str) -> str:
        if v not in valid_zone_ids():
            raise ValueError(f"unknown zone_id '{v}' - not present in zones.csv reference set")
        return v

    @field_validator("reported_at", "updated_at", "resolved_at")
    @classmethod
    def normalise_utc(cls, v: datetime | None) -> datetime | None:
        if v is None:
            return None
        return v.replace(tzinfo=timezone.utc) if v.tzinfo is None else v.astimezone(timezone.utc)

    @model_validator(mode="after")
    def check_lifecycle_consistency(self) -> "ServiceRequestEvent":
        if self.updated_at < self.reported_at:
            raise ValueError(
                f"updated_at {self.updated_at.isoformat()} precedes "
                f"reported_at {self.reported_at.isoformat()}"
            )
        if self.updated_at > datetime.now(timezone.utc) + FUTURE_TOLERANCE:
            raise ValueError(f"updated_at '{self.updated_at.isoformat()}' is in the future")

        if self.status == "RESOLVED":
            if self.resolved_at is None:
                raise ValueError("resolved_at is required when status is RESOLVED")
            if self.resolved_at < self.reported_at:
                raise ValueError(
                    f"resolved_at {self.resolved_at.isoformat()} precedes "
                    f"reported_at {self.reported_at.isoformat()}"
                )
        if self.status in CREW_REQUIRED_STATUSES and not self.crew_id:
            raise ValueError(f"crew_id is required when status is {self.status}")
        return self
