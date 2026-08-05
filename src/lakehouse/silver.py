"""Bronze -> Silver.

Silver is the cleaned, conformed layer: deduplicated, joined to reference data,
typed, with derived columns. Computation is in polars; storage is Delta.
"""

from __future__ import annotations

import argparse
import json
import sys

import polars as pl
from deltalake import DeltaTable

from config.settings import settings
from src.contracts.zones import zone_reference
from src.governance.pii import hash_pii
from src.lakehouse import delta_io
from src.lineage.emitter import lineage_run

SILVER_OCCUPANCY = "silver_zone_occupancy"
BRONZE_OCCUPANCY = "bronze_zone_occupancy"
SILVER_REQUESTS = "silver_service_requests"
BRONZE_REQUESTS = "bronze_service_requests"


def _zones_frame() -> pl.DataFrame:
    ref = zone_reference()
    return pl.DataFrame({
        "zone_id": list(ref.keys()),
        "site": [str(v["site"]) for v in ref.values()],
        "zone_name_en": [str(v["zone_name_en"]) for v in ref.values()],
        "capacity": [int(v["capacity"]) for v in ref.values()],
        "zone_type": [str(v["zone_type"]) for v in ref.values()],
    })


def build_silver_occupancy() -> int:
    with lineage_run(
        "build_silver_occupancy",
        inputs=[BRONZE_OCCUPANCY, "zones_reference"],
        outputs=[SILVER_OCCUPANCY],
    ) as run:
        bronze = pl.from_arrow(delta_io.read(BRONZE_OCCUPANCY))

        silver = (
            bronze
            # Deduplicate on event_id. Bronze can legitimately contain
            # duplicates: offsets are committed after the write, so a crash
            # between the two replays a batch (at-least-once). Keeping the
            # earliest ingest makes this deterministic across reruns.
            .sort("_ingested_at")
            .unique(subset=["event_id"], keep="first")
            .join(_zones_frame().lazy().collect(), on="zone_id", how="inner")
            .with_columns([
                (pl.col("occupancy_estimate") / pl.col("capacity") * 100)
                .round(2).alias("utilization_pct"),
                pl.col("event_time").dt.convert_time_zone("UTC").alias("event_time"),
                pl.col("event_time").dt.truncate("1h").alias("hour_start"),
                pl.col("event_time").dt.date().alias("event_date"),
                (pl.col("entries") - pl.col("exits")).alias("net_flow"),
            ])
            .select([
                "event_id", "zone_id", "site", "zone_name_en", "zone_type", "gate_id",
                "event_time", "hour_start", "event_date", "entries", "exits", "net_flow",
                "occupancy_estimate", "capacity", "utilization_pct", "sensor_status",
                "schema_version", "_kafka_topic", "_kafka_partition", "_kafka_offset",
                "_ingested_at",
            ])
            .sort(["zone_id", "event_time"])
        )

        # Full overwrite: silver is a pure function of bronze, so recomputing it
        # is idempotent. An Airflow retry re-derives the same table rather than
        # appending a second copy.
        n = delta_io.overwrite(SILVER_OCCUPANCY, silver.to_arrow(), partition_by=["event_date"])
        run.record_output_rows(SILVER_OCCUPANCY, n)

    return n


def _stage_latest_per_request(bronze: pl.DataFrame) -> pl.DataFrame:
    """Reduce the bronze event stream to ONE row per request_id.

    This is mandatory, not an optimisation. Bronze holds every lifecycle
    transition, so a single request appears 4-6 times. Handing that straight to
    MERGE makes multiple source rows match the same target row, and Delta
    refuses the whole operation:

        DeltaError: Multiple source rows matched the same target row

    It refuses for a good reason - with several candidates and no ordering,
    "which one wins?" has no defined answer. We answer it explicitly: the row
    with the highest updated_at wins, breaking ties on the Kafka offset (later
    offset = later observation). That is the window-function-then-filter pattern,
    expressed here as a sort plus keep-last.
    """
    return (
        bronze
        .sort(["request_id", "updated_at", "_kafka_offset"])
        .unique(subset=["request_id"], keep="last")
    )


def build_silver_requests() -> dict:
    """Bronze -> silver_service_requests via a real Delta MERGE on request_id.

    Result: one row per request holding its CURRENT state.
    """
    with lineage_run(
        "build_silver_requests_merge",
        inputs=[BRONZE_REQUESTS],
        outputs=[SILVER_REQUESTS],
    ) as run:
        bronze = pl.from_arrow(delta_io.read(BRONZE_REQUESTS))
        bronze = bronze.unique(subset=["event_id"], keep="first")  # at-least-once replay

        staged = _stage_latest_per_request(bronze).with_columns([
            # PII is hashed HERE - bronze keeps the raw values as the immutable
            # record; silver is the first layer anyone queries routinely.
            pl.col("pilgrim_ref")
              .map_elements(hash_pii, return_dtype=pl.String).alias("pilgrim_ref_hash"),
            pl.col("reporter_phone")
              .map_elements(hash_pii, return_dtype=pl.String).alias("reporter_phone_hash"),
            (pl.col("updated_at") - pl.col("reported_at"))
              .dt.total_seconds().truediv(60).round(2).alias("age_minutes"),
            pl.col("reported_at").dt.date().alias("reported_date"),
        ]).select([
            "request_id", "event_id", "zone_id", "category", "priority", "status",
            "reported_at", "updated_at", "resolved_at", "reported_date", "age_minutes",
            "crew_id", "reporter_language",
            # Raw pilgrim_ref / reporter_phone are deliberately NOT selected -
            # they do not exist in silver at all.
            "pilgrim_ref_hash", "reporter_phone_hash",
            "description", "schema_version",
        ])

        source = staged.to_arrow()
        target_path = delta_io.table_path(SILVER_REQUESTS)

        if not delta_io.table_exists(SILVER_REQUESTS):
            # First run: nothing to merge into.
            rows = delta_io.append(SILVER_REQUESTS, source)
            metrics = {"num_target_rows_inserted": rows, "num_target_rows_updated": 0,
                       "first_load": True}
        else:
            dt = DeltaTable(target_path)
            metrics = (
                dt.merge(
                    source=source,
                    predicate="target.request_id = source.request_id",
                    source_alias="source",
                    target_alias="target",
                )
                # Only overwrite when the incoming state is genuinely newer;
                # a replayed older event must not resurrect a stale status.
                .when_matched_update_all(predicate="source.updated_at > target.updated_at")
                .when_not_matched_insert_all()
                .execute()
            )
            metrics = {k: v for k, v in metrics.items() if isinstance(v, (int, float))}

        total = delta_io.read(SILVER_REQUESTS).num_rows
        run.record_output_rows(SILVER_REQUESTS, total)

    return {"table": SILVER_REQUESTS, "rows": total,
            "staged_rows": staged.height, "bronze_rows": bronze.height,
            "merge_metrics": metrics}


def main() -> int:
    ap = argparse.ArgumentParser(description="Build silver layer")
    ap.add_argument("--table", default="occupancy", choices=["occupancy", "requests"])
    args = ap.parse_args()

    if args.table == "requests":
        result = build_silver_requests()
    else:
        n = build_silver_occupancy()
        result = {"table": SILVER_OCCUPANCY, "rows": n,
                  "path": settings.delta_path(SILVER_OCCUPANCY)}
    print(json.dumps(result, indent=2, default=str), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
