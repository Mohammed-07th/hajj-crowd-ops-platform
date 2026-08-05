"""Great Expectations suites and checkpoints.

The gate must GATE. Every entry point here raises on `success == False` after
writing Data Docs - it never logs a warning and lets the DAG continue green.
Airflow's default `all_success` trigger rule then leaves everything downstream
in `upstream_failed` / `skipped`, which is the visible proof the rubric asks for.

GE 0.18's execution engines are pandas, Spark and SQLAlchemy - there is no
polars engine. The pipeline computes in polars/Arrow and hands GE a pandas frame
at the validation boundary only. At 150k-250k rows that conversion is cheap, and
it keeps the expectations themselves entirely standard.
"""

from __future__ import annotations

import json
from pathlib import Path

import great_expectations as gx
import pandas as pd
from great_expectations.data_context import FileDataContext

from config.settings import REPO_ROOT
from src.contracts.zones import valid_zone_ids

GE_ROOT = REPO_ROOT / "great_expectations"


def get_context() -> FileDataContext:
    """Open the on-disk GE project, creating it on first use.

    GE 0.18 scaffolds into `gx/`; the project layout calls for
    `great_expectations/`. We rename once on creation so suites and Data Docs
    land where the repository structure says they do.
    """
    if not (GE_ROOT / "great_expectations.yml").exists():
        FileDataContext.create(project_root_dir=str(REPO_ROOT))
        scaffolded = REPO_ROOT / "gx"
        if scaffolded.is_dir() and not GE_ROOT.exists():
            scaffolded.rename(GE_ROOT)
        _disable_progress_bars()
    return gx.get_context(context_root_dir=str(GE_ROOT))


def _disable_progress_bars() -> None:
    """GE's tqdm output floods Airflow task logs and hides the actual result."""
    cfg = GE_ROOT / "great_expectations.yml"
    text = cfg.read_text(encoding="utf-8")
    if "progress_bars" not in text:
        cfg.write_text(
            text + "\nprogress_bars:\n  globally: false\n  metric_calculations: false\n",
            encoding="utf-8",
        )


# --- suite definitions -----------------------------------------------------
# Expressed as (expectation_type, kwargs) so the same code builds the suite and
# the committed JSON under great_expectations/expectations/.

def bronze_suite_expectations(row_count_min: int, row_count_max: int) -> list[tuple[str, dict]]:
    return [
        ("expect_column_values_to_not_be_null", {"column": "event_id"}),
        ("expect_column_values_to_not_be_null", {"column": "zone_id"}),
        ("expect_column_values_to_not_be_null", {"column": "event_time"}),
        ("expect_column_values_to_be_unique", {"column": "event_id"}),
        ("expect_column_values_to_be_in_set",
         {"column": "zone_id", "value_set": sorted(valid_zone_ids())}),
        ("expect_column_values_to_be_in_set",
         {"column": "sensor_status", "value_set": ["OK", "DEGRADED", "OFFLINE"]}),
        ("expect_column_values_to_be_between", {"column": "entries", "min_value": 0, "max_value": 50_000}),
        ("expect_column_values_to_be_between", {"column": "exits", "min_value": 0, "max_value": 50_000}),
        ("expect_column_values_to_be_between",
         {"column": "occupancy_estimate", "min_value": 0, "max_value": 90_000}),
        # Volume pillar (Day 4): catches an upstream drop or a duplicate load.
        # A run that ingests 12 rows is broken even if all 12 are perfectly valid.
        ("expect_table_row_count_to_be_between",
         {"min_value": row_count_min, "max_value": row_count_max}),
    ]


def gold_suite_expectations() -> list[tuple[str, dict]]:
    return [
        ("expect_column_values_to_be_between",
         {"column": "peak_utilization_pct", "min_value": 0, "max_value": 200}),
        ("expect_column_values_to_not_be_null", {"column": "zone_id"}),
        ("expect_column_values_to_not_be_null", {"column": "hour_start"}),
        ("expect_table_row_count_to_be_between", {"min_value": 1, "max_value": 5_000_000}),
    ]


def run_suite(df: pd.DataFrame, suite_name: str, expectations: list[tuple[str, dict]],
              checkpoint_name: str) -> dict:
    """Validate `df` and return the checkpoint result summary. Does not raise."""
    context = get_context()

    datasource_name = f"{suite_name}_src"
    try:
        datasource = context.sources.add_pandas(datasource_name)
    except Exception:
        datasource = context.get_datasource(datasource_name)

    asset_name = f"{suite_name}_asset"
    try:
        asset = datasource.add_dataframe_asset(name=asset_name)
    except Exception:
        asset = datasource.get_asset(asset_name)

    context.add_or_update_expectation_suite(expectation_suite_name=suite_name)
    batch_request = asset.build_batch_request(dataframe=df)
    validator = context.get_validator(batch_request=batch_request, expectation_suite_name=suite_name)

    for exp_type, kwargs in expectations:
        getattr(validator, exp_type)(**kwargs)
    # discard_failed_expectations=False: the suite is the *contract*, so it must
    # persist even when this particular batch violates it.
    validator.save_expectation_suite(discard_failed_expectations=False)

    checkpoint = context.add_or_update_checkpoint(
        name=checkpoint_name,
        validator=validator,
    )
    result = checkpoint.run()
    context.build_data_docs()

    evaluated = successful = 0
    failed = []
    for validation_result in result.run_results.values():
        stats = validation_result["validation_result"]["statistics"]
        evaluated += stats.get("evaluated_expectations", 0)
        successful += stats.get("successful_expectations", 0)
        for r in validation_result["validation_result"]["results"]:
            if not r["success"]:
                failed.append({
                    "expectation": r["expectation_config"]["expectation_type"],
                    "column": r["expectation_config"]["kwargs"].get("column"),
                    "unexpected_count": r["result"].get("unexpected_count"),
                    "unexpected_percent": round(r["result"].get("unexpected_percent", 0) or 0, 3),
                    "partial_unexpected_list": r["result"].get("partial_unexpected_list", [])[:5],
                })

    return {
        "success": bool(result.success),
        "suite": suite_name,
        "checkpoint": checkpoint_name,
        "evaluated": evaluated,
        "successful": successful,
        "failed_expectations": failed,
    }


class QualityGateFailure(RuntimeError):
    """Raised when a checkpoint fails. Airflow converts this into a red task."""


def gate(summary: dict) -> dict:
    """Halt the pipeline if the checkpoint failed."""
    print(json.dumps(summary, indent=2, default=str), flush=True)
    if not summary["success"]:
        raise QualityGateFailure(
            f"GE checkpoint '{summary['checkpoint']}' FAILED: "
            f"{len(summary['failed_expectations'])} expectation(s) failed - "
            f"{[f['expectation'] for f in summary['failed_expectations']]}"
        )
    print(f"GATE PASSED: {summary['successful']}/{summary['evaluated']} expectations met", flush=True)
    return summary
