"""The MERGE must be idempotent, and it must actually update.

Idempotency is not academic here: Airflow retries failed tasks automatically
(retries=2), so a merge that double-inserts on a retry corrupts silver in a way
that only shows up much later as inflated counts.
"""

from __future__ import annotations

import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

import polars as pl
import pyarrow as pa
import pytest
from deltalake import DeltaTable, write_deltalake

from src.lakehouse.silver import _stage_latest_per_request

BASE = datetime(2026, 5, 24, 6, 0, tzinfo=timezone.utc)


@pytest.fixture()
def table_path(tmp_path: Path) -> str:
    path = str(tmp_path / "silver_requests_test")
    shutil.rmtree(path, ignore_errors=True)
    return path


def _events(rows: list[tuple[str, str, int, int]]) -> pl.DataFrame:
    """rows = (request_id, status, minutes_after_base, kafka_offset)"""
    return pl.DataFrame({
        "request_id": [r[0] for r in rows],
        "status": [r[1] for r in rows],
        "updated_at": [BASE + timedelta(minutes=r[2]) for r in rows],
        "_kafka_offset": [r[3] for r in rows],
    })


def _merge(path: str, source: pa.Table) -> dict:
    if not Path(path, "_delta_log").is_dir():
        write_deltalake(path, source, mode="overwrite", engine="pyarrow")
        return {"num_target_rows_inserted": source.num_rows, "num_target_rows_updated": 0}
    return (
        DeltaTable(path)
        .merge(source=source, predicate="target.request_id = source.request_id",
               source_alias="source", target_alias="target")
        .when_matched_update_all(predicate="source.updated_at > target.updated_at")
        .when_not_matched_insert_all()
        .execute()
    )


def test_staging_reduces_to_one_row_per_request_id():
    """Without this, Delta raises 'multiple source rows matched the same target row'."""
    events = _events([
        ("REQ-A", "REPORTED", 0, 1),
        ("REQ-A", "ACKNOWLEDGED", 5, 2),
        ("REQ-A", "RESOLVED", 40, 3),
        ("REQ-B", "REPORTED", 2, 4),
    ])
    staged = _stage_latest_per_request(events)

    assert staged.height == 2
    assert staged["request_id"].n_unique() == 2
    # The winner is the highest updated_at, not merely the last row seen.
    assert staged.filter(pl.col("request_id") == "REQ-A")["status"][0] == "RESOLVED"


def test_staging_breaks_ties_on_kafka_offset():
    """Two events with identical updated_at: later offset is the later observation."""
    events = _events([
        ("REQ-A", "DISPATCHED", 10, 7),
        ("REQ-A", "ON_SITE", 10, 9),
    ])
    staged = _stage_latest_per_request(events)
    assert staged.height == 1
    assert staged["status"][0] == "ON_SITE"


def test_merge_twice_equals_merge_once(table_path: str):
    source = _stage_latest_per_request(_events([
        ("REQ-A", "ACKNOWLEDGED", 5, 1),
        ("REQ-B", "REPORTED", 2, 2),
    ])).to_arrow()

    _merge(table_path, source)
    after_first = DeltaTable(table_path).to_pyarrow_table().to_pydict()

    _merge(table_path, source)
    after_second = DeltaTable(table_path).to_pyarrow_table().to_pydict()

    assert after_first["request_id"] == after_second["request_id"]
    assert after_first["status"] == after_second["status"]
    assert len(after_second["request_id"]) == 2


def test_merge_updates_existing_rows_when_state_advances(table_path: str):
    first = _stage_latest_per_request(_events([
        ("REQ-A", "ACKNOWLEDGED", 5, 1),
        ("REQ-B", "REPORTED", 2, 2),
    ])).to_arrow()
    _merge(table_path, first)

    second = _stage_latest_per_request(_events([
        ("REQ-A", "RESOLVED", 40, 3),   # advanced
        ("REQ-C", "REPORTED", 8, 4),    # new
    ])).to_arrow()
    metrics = _merge(table_path, second)

    result = pl.from_arrow(DeltaTable(table_path).to_pyarrow_table())
    assert result.height == 3, "REQ-C inserted, REQ-A updated in place"
    assert result.filter(pl.col("request_id") == "REQ-A")["status"][0] == "RESOLVED"
    assert result.filter(pl.col("request_id") == "REQ-B")["status"][0] == "REPORTED"
    assert metrics["num_target_rows_updated"] == 1
    assert metrics["num_target_rows_inserted"] == 1


def test_stale_replay_does_not_resurrect_an_older_status(table_path: str):
    """A replayed older event must not overwrite newer state.

    At-least-once delivery means old messages can reappear. Without the
    `source.updated_at > target.updated_at` guard on the update clause, a
    replayed REPORTED would knock a RESOLVED request back to REPORTED.
    """
    _merge(table_path, _stage_latest_per_request(
        _events([("REQ-A", "RESOLVED", 40, 5)])).to_arrow())

    stale = _stage_latest_per_request(_events([("REQ-A", "REPORTED", 0, 1)])).to_arrow()
    _merge(table_path, stale)

    result = pl.from_arrow(DeltaTable(table_path).to_pyarrow_table())
    assert result.height == 1
    assert result["status"][0] == "RESOLVED", "stale replay must not win"
