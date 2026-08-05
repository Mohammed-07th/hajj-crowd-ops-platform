"""Failure demo 2 - Delta schema enforcement refuses a breaking write.

Two halves, and the second is the point:

  1. A BREAKING change is refused. Appending `occupancy_estimate` as a string
     column to a table where it is an integer raises before anything is written.
  2. An ADDITIVE change is accepted, but only when the writer explicitly asks
     for it. Adding a new `sensor_firmware_version` column succeeds with
     `schema_mode="merge"`.

Rejecting a breaking change and accepting an additive one are the same
mechanism, and knowing the difference is the whole skill.

A caveat this script proves rather than assumes
-----------------------------------------------
delta-rs enforces schema differently per write engine:

  engine="rust" (default) safe-CASTS the incoming column, so appending the
  string "1500" into an Int64 column SUCCEEDS and silently stores 1500.
  engine="pyarrow" compares schemas and refuses.

That is the same silent-coercion failure the strict Pydantic contract exists to
stop at the ingestion boundary, so the lakehouse writes through the enforcing
engine (see src/lakehouse/delta_io.py). This script demonstrates BOTH engines so
the difference is on the record rather than a claim.

Exits non-zero, because a demonstration that a write was refused should itself
look like a refusal to any caller.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pyarrow as pa
from deltalake import DeltaTable, write_deltalake

from config.settings import REPO_ROOT

DEMO_TABLE = REPO_ROOT / "delta" / "_schema_demo"


def banner(text: str) -> None:
    print("\n" + "=" * 78)
    print(text)
    print("=" * 78, flush=True)


def main() -> int:
    shutil.rmtree(DEMO_TABLE, ignore_errors=True)
    DEMO_TABLE.parent.mkdir(parents=True, exist_ok=True)

    banner("SETUP - create a Delta table with occupancy_estimate as INT64")
    good = pa.table({
        "event_id": ["E1", "E2"],
        "zone_id": ["MATAF_01", "MATAF_02"],
        "occupancy_estimate": pa.array([30_000, 21_000], type=pa.int64()),
    })
    write_deltalake(str(DEMO_TABLE), good, mode="overwrite")
    print(DeltaTable(str(DEMO_TABLE)).schema().to_pyarrow())
    print(f"rows: {DeltaTable(str(DEMO_TABLE)).to_pyarrow_table().num_rows}")

    breaking = pa.table({
        "event_id": ["E3"],
        "zone_id": ["MATAF_03"],
        # StringType where the table has IntegerType. Values LOOK numeric,
        # which is exactly what makes this dangerous.
        "occupancy_estimate": pa.array(["1500"], type=pa.string()),
    })

    banner("PART 1a - BREAKING CHANGE through the default (rust) engine")
    print("appending occupancy_estimate as StringType ...")
    coerced = False
    try:
        write_deltalake(str(DEMO_TABLE), breaking, mode="append", engine="rust")
        table = DeltaTable(str(DEMO_TABLE)).to_pyarrow_table()
        coerced = True
        print("  *** ACCEPTED - the rust engine safe-cast the value ***")
        print(f"  stored occupancy_estimate: {table.column('occupancy_estimate').to_pylist()}")
        print("  NOTE: no error was raised. This is why the pipeline does not use this engine.")
    except Exception as exc:
        print(f"  REJECTED -> {type(exc).__name__}: {exc}")

    # Undo whatever part 1a did, so part 1b starts from the same clean state.
    if coerced:
        # Version 0 is the setup write; the coerced append created version 1.
        DeltaTable(str(DEMO_TABLE)).restore(0)
        print(f"  (restored to version 0; rows back to "
              f"{DeltaTable(str(DEMO_TABLE)).to_pyarrow_table().num_rows})")

    banner("PART 1b - BREAKING CHANGE through the enforcing (pyarrow) engine")
    print("appending occupancy_estimate as StringType ...")
    refused = False
    try:
        write_deltalake(str(DEMO_TABLE), breaking, mode="append", engine="pyarrow")
        print("  *** NO ERROR RAISED - schema enforcement FAILED ***")
    except Exception as exc:
        refused = True
        print(f"  REJECTED -> {type(exc).__name__}")
        print("  full message:")
        for line in str(exc).splitlines():
            print(f"    {line}")

    banner("PART 2 - ADDITIVE CHANGE accepted under an explicit schema_mode")
    additive = pa.table({
        "event_id": ["E4"],
        "zone_id": ["MASAA_L1"],
        "occupancy_estimate": pa.array([18_500], type=pa.int64()),
        "sensor_firmware_version": ["v2.1.4"],   # genuinely new, non-breaking
    })
    print("appending a new sensor_firmware_version column with schema_mode='merge' ...")
    try:
        write_deltalake(str(DEMO_TABLE), additive, mode="append", schema_mode="merge",
                        engine="rust")
        dt = DeltaTable(str(DEMO_TABLE))
        print("  ACCEPTED. Table schema is now:")
        print(f"    columns: {dt.schema().to_pyarrow().names}")
        print(f"    rows: {dt.to_pyarrow_table().num_rows}")
        print("  Existing rows keep NULL for the new column - no rewrite, no data loss.")
    except Exception as exc:
        print(f"  UNEXPECTED FAILURE -> {type(exc).__name__}: {exc}")
        return 1

    banner("HISTORY")
    for entry in reversed(DeltaTable(str(DEMO_TABLE)).history()):
        print(f"  v{entry.get('version')}  {entry.get('operation')}")

    banner("RESULT")
    if refused:
        print("Breaking change REFUSED by schema enforcement; additive change ACCEPTED.")
        print("Exiting non-zero: this script's purpose is to show a write being refused.")
        return 2
    print("Breaking change was NOT refused - schema enforcement is not working.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
