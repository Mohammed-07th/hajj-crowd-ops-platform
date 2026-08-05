"""Delta write/read helpers built on delta-rs (no JVM).

Why the writes go through `engine="pyarrow"`
--------------------------------------------
delta-rs offers two write engines and they enforce schema *differently*, which
matters a great deal for Deliverable 2:

  engine="rust"    (the default)  -> safe-casts the incoming column. Appending a
                                     StringType column of "1500" into an Int64
                                     column SUCCEEDS and silently produces 1500.
  engine="pyarrow" (deprecated)   -> compares schemas and raises
                                     ValueError("Schema of data does not match
                                     table schema") before writing anything.

Verified on deltalake 0.20.2; see docs/evidence/failures/schema_enforcement.log.
Silent coercion is exactly the failure mode the strict Pydantic contract exists
to prevent at the ingestion boundary, so allowing it at the storage boundary
would be incoherent. Every append therefore uses the enforcing engine, and the
only writes permitted to change a table's schema are the ones that ask for it
explicitly via `schema_mode="merge"`.
"""

from __future__ import annotations

import warnings
from pathlib import Path

import pyarrow as pa
from deltalake import DeltaTable, write_deltalake

from config.settings import settings

# The pyarrow engine is deprecated upstream (removal in delta-rs 1.0). We pin
# 0.20.2, so it is present and correct; the warning is noise in every log.
warnings.filterwarnings("ignore", message=".*pyarrow engine is deprecated.*")


def table_path(name: str) -> str:
    return settings.delta_path(name)


def table_exists(name: str) -> bool:
    return Path(table_path(name), "_delta_log").is_dir()


def append(name: str, data: pa.Table, partition_by: list[str] | None = None) -> int:
    """Append with schema enforcement. Raises if the schema does not match."""
    path = table_path(name)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    mode = "append" if table_exists(name) else "overwrite"
    write_deltalake(path, data, mode=mode, engine="pyarrow",
                    partition_by=partition_by or None)
    return data.num_rows


def overwrite(name: str, data: pa.Table, partition_by: list[str] | None = None) -> int:
    """Full overwrite - used for gold tables, which are pure recomputations.

    Recomputing gold from scratch is what makes the Airflow tasks idempotent:
    a retry produces byte-identical output instead of double-counting.
    """
    path = table_path(name)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    write_deltalake(path, data, mode="overwrite", engine="pyarrow",
                    partition_by=partition_by or None,
                    schema_mode="overwrite")
    return data.num_rows


def read(name: str) -> pa.Table:
    return DeltaTable(table_path(name)).to_pyarrow_table()


def version(name: str) -> int:
    return DeltaTable(table_path(name)).version()


def history(name: str, limit: int = 20) -> list[dict]:
    return DeltaTable(table_path(name)).history(limit)
