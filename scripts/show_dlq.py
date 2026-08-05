"""Print the dead-letter contents with rejection reasons.

Reads the quarantine Delta table (the queryable copy) and summarises what was
rejected and why. Committed output lives in docs/evidence/failures/.
"""

from __future__ import annotations

import argparse
import json
import sys

import polars as pl

from src.lakehouse import delta_io


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=12, help="sample rows to print")
    args = ap.parse_args()

    q = pl.from_arrow(delta_io.read("quarantine"))

    print("=" * 100)
    print(f"QUARANTINE TABLE - {q.height:,} rejected records")
    print("=" * 100)

    print("\n--- rejections by rule (failed_rules) ---")
    by_rule = (
        q.with_columns(pl.col("failed_rules").str.json_decode().alias("rules"))
        .explode("rules")
        .group_by("rules")
        .agg(pl.len().alias("count"))
        .sort("count", descending=True)
    )
    print(by_rule)

    print("\n--- rejections by source topic / partition ---")
    print(q.group_by(["source_topic", "partition"]).agg(pl.len().alias("count")).sort("partition"))

    print(f"\n--- sample of {args.limit} rejections with reasons ---")
    for row in q.head(args.limit).iter_rows(named=True):
        print(f"\n  partition={row['partition']} offset={row['offset']}")
        print(f"  reason : {row['rejection_reason']}")
        print(f"  rules  : {row['failed_rules']}")
        payload = row["original_payload"]
        print(f"  payload: {payload[:150]}{'...' if len(payload) > 150 else ''}")

    print("\n" + "=" * 100)
    print("Every rejected record carries a machine-readable rule id and a human-readable reason.")
    print("=" * 100)

    print("\n" + json.dumps({
        "quarantined_total": q.height,
        "distinct_rules": by_rule.height,
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
