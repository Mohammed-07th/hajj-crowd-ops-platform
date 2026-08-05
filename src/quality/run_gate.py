"""Runnable quality gate. Exits non-zero when the checkpoint fails.

This is what Airflow calls. A non-zero exit is what turns the task red, which
is what leaves everything downstream `upstream_failed` / `skipped`.
"""

from __future__ import annotations

import argparse
import sys

import polars as pl

from src.lakehouse import delta_io
from src.lineage.emitter import lineage_run
from src.quality.checkpoints import (
    QualityGateFailure,
    bronze_suite_expectations,
    gate,
    gold_suite_expectations,
    run_suite,
)

LAYERS = {
    "bronze": {
        "table": "bronze_zone_occupancy",
        "suite": "bronze_suite",
        "checkpoint": "bronze_checkpoint",
    },
    "gold": {
        "table": "gold_zone_hourly",
        "suite": "gold_suite",
        "checkpoint": "gold_checkpoint",
    },
}


def main() -> int:
    ap = argparse.ArgumentParser(description="Run a Great Expectations gate")
    ap.add_argument("--layer", required=True, choices=sorted(LAYERS))
    ap.add_argument("--min-rows", type=int, default=1_000,
                    help="volume-pillar lower bound for the bronze suite")
    ap.add_argument("--max-rows", type=int, default=5_000_000)
    args = ap.parse_args()

    cfg = LAYERS[args.layer]
    with lineage_run(
        f"validate_{args.layer}",
        inputs=[cfg["table"]],
        outputs=[f"ge_validation_{args.layer}"],
    ) as run:
        df = pl.from_arrow(delta_io.read(cfg["table"])).to_pandas()
        run.record_output_rows(f"ge_validation_{args.layer}", len(df))

        if args.layer == "bronze":
            expectations = bronze_suite_expectations(args.min_rows, args.max_rows)
        else:
            expectations = gold_suite_expectations()

        summary = run_suite(df, cfg["suite"], expectations, cfg["checkpoint"])
        try:
            gate(summary)
        except QualityGateFailure as exc:
            # Re-raised so the lineage context manager emits FAIL, then the
            # non-zero exit propagates to Airflow.
            print(f"QUALITY GATE BLOCKED THE PIPELINE: {exc}", file=sys.stderr, flush=True)
            raise

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except QualityGateFailure:
        sys.exit(2)
