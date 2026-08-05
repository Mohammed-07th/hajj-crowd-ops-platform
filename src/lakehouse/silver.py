"""Bronze -> Silver.

Silver is the cleaned, conformed layer: deduplicated, joined to reference data,
typed, with derived columns. Computation is in polars; storage is Delta.
"""

from __future__ import annotations

import argparse
import json
import sys

import polars as pl

from config.settings import settings
from src.contracts.zones import zone_reference
from src.lakehouse import delta_io
from src.lineage.emitter import lineage_run

SILVER_OCCUPANCY = "silver_zone_occupancy"
BRONZE_OCCUPANCY = "bronze_zone_occupancy"


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


def main() -> int:
    ap = argparse.ArgumentParser(description="Build silver layer")
    ap.add_argument("--table", default="occupancy", choices=["occupancy"])
    ap.parse_args()
    n = build_silver_occupancy()
    print(json.dumps({"table": SILVER_OCCUPANCY, "rows": n,
                      "path": settings.delta_path(SILVER_OCCUPANCY)}, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
