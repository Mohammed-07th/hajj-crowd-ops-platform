"""Data contract for Stream A - zone occupancy telemetry.

Why `strict=True` matters
-------------------------
In non-strict mode Pydantic will happily coerce the JSON string "1500" into the
integer 1500. That is exactly how corrupt data enters a warehouse wearing a
valid disguise: a sensor firmware bug starts quoting its numbers, nothing
raises, and six months of silently-typed data has to be re-derived. Strict mode
turns that into a loud rejection at the ingestion boundary.

Why validation happens with `model_validate_json` and not `json.loads` first
---------------------------------------------------------------------------
Pydantic applies a *different* strict conversion table to JSON input than to
Python input: from JSON, an ISO-8601 string is a legitimate `datetime` (JSON has
no datetime type), while a quoted number is still not an `int`. Parsing the
bytes ourselves and then calling `model_validate` would put us in Python mode,
where every `event_time` string would be rejected and we would have to loosen
the int rule to compensate. Validating the raw bytes keeps both rules correct.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from src.contracts.zones import valid_zone_ids, zone_capacity

# An event may legitimately arrive slightly ahead of our clock (sensor clock
# skew, network buffering). Beyond this it is a broken clock, not skew.
FUTURE_TOLERANCE = timedelta(minutes=5)

# Occupancy above this multiple of the zone's rated capacity is physically
# implausible and indicates a miscalibrated or wrapped sensor counter.
MAX_CAPACITY_MULTIPLE = 1.5


class ZoneOccupancyEvent(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    event_id: str
    zone_id: str
    gate_id: str
    event_time: datetime
    entries: int = Field(ge=0)
    exits: int = Field(ge=0)
    occupancy_estimate: int = Field(ge=0)
    sensor_status: Literal["OK", "DEGRADED", "OFFLINE"]
    schema_version: str = "1.0"

    @field_validator("zone_id")
    @classmethod
    def zone_must_be_known(cls, v: str) -> str:
        if v not in valid_zone_ids():
            raise ValueError(f"unknown zone_id '{v}' - not present in zones.csv reference set")
        return v

    @field_validator("event_time")
    @classmethod
    def event_time_not_in_future(cls, v: datetime) -> datetime:
        # Normalise to UTC first: a naive timestamp is ambiguous and comparing
        # it to an aware `now` raises rather than rejecting cleanly.
        v = v.replace(tzinfo=timezone.utc) if v.tzinfo is None else v.astimezone(timezone.utc)
        if v > datetime.now(timezone.utc) + FUTURE_TOLERANCE:
            raise ValueError(f"event_time '{v.isoformat()}' is in the future")
        return v

    @model_validator(mode="after")
    def occupancy_within_capacity(self) -> "ZoneOccupancyEvent":
        # Cross-field business rule: needs both zone_id and occupancy_estimate,
        # so it cannot live on either field alone.
        capacity = zone_capacity(self.zone_id)
        if capacity is not None:
            ceiling = int(capacity * MAX_CAPACITY_MULTIPLE)
            if self.occupancy_estimate > ceiling:
                raise ValueError(
                    f"occupancy_estimate {self.occupancy_estimate} exceeds "
                    f"{MAX_CAPACITY_MULTIPLE:.0%} of zone {self.zone_id} "
                    f"capacity {capacity} (ceiling {ceiling})"
                )
        return self
