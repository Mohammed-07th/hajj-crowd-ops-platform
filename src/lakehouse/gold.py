"""Silver -> Gold.

Gold is a genuine aggregate, not a filtered copy of silver: every column here is
produced by a GROUP BY and none of them exist upstream. `gold_zone_hourly`
collapses ~250k readings into one row per zone-hour carrying peak/average
occupancy, utilisation against rated capacity, exposure time above the 80% and
90% escalation thresholds, and sensor health.

The threshold columns are the operationally interesting ones: SOP-CS-004
escalates on *sustained* time above a threshold, so "minutes above 90%" is the
number a duty officer acts on, and it cannot be read off a single silver row.
"""

from __future__ import annotations

import argparse
import json
import sys

import polars as pl

from src.lakehouse import delta_io
from src.lakehouse.silver import SILVER_OCCUPANCY
from src.lineage.emitter import lineage_run

GOLD_ZONE_HOURLY = "gold_zone_hourly"


def build_gold_zone_hourly() -> int:
    with lineage_run(
        "build_gold_zone_hourly",
        inputs=[SILVER_OCCUPANCY],
        outputs=[GOLD_ZONE_HOURLY],
    ) as run:
        silver = pl.from_arrow(delta_io.read(SILVER_OCCUPANCY))

        gold = (
            silver
            .group_by(["zone_id", "site", "zone_type", "hour_start"])
            .agg([
                pl.col("occupancy_estimate").max().alias("peak_occupancy"),
                pl.col("occupancy_estimate").mean().round(1).alias("avg_occupancy"),
                pl.col("capacity").first().alias("capacity"),
                pl.col("utilization_pct").max().round(2).alias("peak_utilization_pct"),
                pl.col("utilization_pct").mean().round(2).alias("avg_utilization_pct"),
                pl.len().alias("reading_count"),
                (pl.col("utilization_pct") > 80).sum().alias("_readings_above_80"),
                (pl.col("utilization_pct") > 90).sum().alias("_readings_above_90"),
                (pl.col("sensor_status") != "OK").sum().alias("_degraded_readings"),
                pl.col("entries").sum().alias("total_entries"),
                pl.col("exits").sum().alias("total_exits"),
            ])
            .with_columns([
                # Each reading represents an equal slice of its hour, so the
                # minutes a zone spent above a threshold is the share of
                # readings above it, scaled to 60 minutes. Deriving the slice
                # width from reading_count keeps this correct regardless of the
                # producer's emission rate.
                (pl.col("_readings_above_80") * 60.0 / pl.col("reading_count"))
                .round(1).alias("minutes_above_80pct"),
                (pl.col("_readings_above_90") * 60.0 / pl.col("reading_count"))
                .round(1).alias("minutes_above_90pct"),
                (pl.col("_degraded_readings") * 100.0 / pl.col("reading_count"))
                .round(2).alias("degraded_sensor_pct"),
                pl.col("hour_start").dt.date().alias("event_date"),
            ])
            .drop(["_readings_above_80", "_readings_above_90", "_degraded_readings"])
            .sort(["zone_id", "hour_start"])
        )

        n = delta_io.overwrite(GOLD_ZONE_HOURLY, gold.to_arrow(), partition_by=["event_date"])
        run.record_output_rows(GOLD_ZONE_HOURLY, n)

    return n


def main() -> int:
    ap = argparse.ArgumentParser(description="Build gold aggregates")
    ap.add_argument("--table", default="zone_hourly", choices=["zone_hourly"])
    ap.parse_args()
    n = build_gold_zone_hourly()
    print(json.dumps({"table": GOLD_ZONE_HOURLY, "rows": n}, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
