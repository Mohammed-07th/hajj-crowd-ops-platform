"""Every corruption type the generator can inject must be rejected.

These tests run the *same* corruption functions the producer uses, so the suite
cannot drift from what actually goes on the wire. A test that hand-writes its
own bad payload proves the model rejects that payload; this proves the model
rejects what the producer emits.
"""

from __future__ import annotations

import json
import random
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from src.contracts.occupancy import ZoneOccupancyEvent
from src.ingestion.dlq import describe_validation_error
from src.ingestion.producers.occupancy_producer import CORRUPTION_TYPES, corrupt

RNG = random.Random(0)


def valid_event() -> dict:
    return {
        "event_id": str(uuid.uuid4()),
        "zone_id": "MATAF_01",
        "gate_id": "G-MATAF_01-N",
        "event_time": (datetime.now(timezone.utc) - timedelta(hours=1))
        .isoformat().replace("+00:00", "Z"),
        "entries": 120,
        "exits": 95,
        "occupancy_estimate": 30_000,
        "sensor_status": "OK",
        "schema_version": "1.0",
    }


def test_valid_event_is_accepted():
    event = ZoneOccupancyEvent.model_validate_json(json.dumps(valid_event()).encode())
    assert event.zone_id == "MATAF_01"
    assert event.entries == 120


@pytest.mark.parametrize("kind", CORRUPTION_TYPES)
def test_every_corruption_type_is_rejected(kind: str):
    payload, _ = corrupt(valid_event(), kind, RNG)
    with pytest.raises(Exception) as excinfo:
        ZoneOccupancyEvent.model_validate_json(payload)
    # The rejection must be describable - a DLQ record without a usable reason
    # is just a second copy of the corrupt data.
    reason, rules = describe_validation_error(excinfo.value)
    assert reason and rules, f"{kind} produced an empty rejection reason"


def test_strict_mode_rejects_numeric_string():
    """The headline strict-mode case.

    Without ConfigDict(strict=True) Pydantic coerces "1500" to 1500 and this
    record enters bronze looking perfectly valid.
    """
    bad = valid_event() | {"entries": "1500"}
    with pytest.raises(ValidationError) as excinfo:
        ZoneOccupancyEvent.model_validate_json(json.dumps(bad).encode())
    assert "int_type" in [e["type"] for e in excinfo.value.errors()]


def test_iso_timestamp_string_is_still_accepted_under_strict_mode():
    """Strict mode must not reject ISO strings for datetime fields.

    This is why validation runs on raw JSON bytes: Pydantic's JSON conversion
    table allows str -> datetime (JSON has no datetime type) while still
    refusing str -> int. Validating a pre-parsed dict would lose that.
    """
    event = ZoneOccupancyEvent.model_validate_json(json.dumps(valid_event()).encode())
    assert isinstance(event.event_time, datetime)


def test_unknown_zone_is_rejected_against_reference_set():
    bad = valid_event() | {"zone_id": "MATAF_99"}
    with pytest.raises(ValidationError) as excinfo:
        ZoneOccupancyEvent.model_validate_json(json.dumps(bad).encode())
    assert "unknown zone_id" in str(excinfo.value)


def test_occupancy_above_150pct_of_capacity_is_rejected():
    # MATAF_01 capacity is 48000; 150% is 72000.
    bad = valid_event() | {"occupancy_estimate": 80_000}
    with pytest.raises(ValidationError) as excinfo:
        ZoneOccupancyEvent.model_validate_json(json.dumps(bad).encode())
    assert "exceeds" in str(excinfo.value)


def test_occupancy_just_below_ceiling_is_accepted():
    """The cross-field rule must not be so blunt it rejects real overcrowding."""
    ok = valid_event() | {"occupancy_estimate": 71_000}
    event = ZoneOccupancyEvent.model_validate_json(json.dumps(ok).encode())
    assert event.occupancy_estimate == 71_000


def test_extra_field_is_forbidden():
    bad = valid_event() | {"undeclared_column": "surprise"}
    with pytest.raises(ValidationError) as excinfo:
        ZoneOccupancyEvent.model_validate_json(json.dumps(bad).encode())
    assert "extra_forbidden" in [e["type"] for e in excinfo.value.errors()]


def test_future_timestamp_is_rejected():
    bad = valid_event() | {
        "event_time": (datetime.now(timezone.utc) + timedelta(days=3))
        .isoformat().replace("+00:00", "Z")
    }
    with pytest.raises(ValidationError) as excinfo:
        ZoneOccupancyEvent.model_validate_json(json.dumps(bad).encode())
    assert "future" in str(excinfo.value)


def test_malformed_json_is_reported_as_a_decode_failure():
    payload, _ = corrupt(valid_event(), "malformed_json", RNG)
    with pytest.raises(Exception) as excinfo:
        ZoneOccupancyEvent.model_validate_json(payload)
    reason, rules = describe_validation_error(excinfo.value)
    assert "json" in reason.lower() or "json_invalid" in rules
