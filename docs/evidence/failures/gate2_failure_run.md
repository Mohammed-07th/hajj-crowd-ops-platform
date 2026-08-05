# Failure demo 3 — quality GATE 2 halts the pipeline

DAG run: `gate2_failure_demo`, triggered with `{"unique_requests": 200, "request_events": 900}`
simulating an upstream feed that delivered a fraction of the expected service requests.

| task | state |
|---|---|
| validate_bronze | **success** (occupancy volume normal — GATE 1 passes) |
| build_silver_occupancy | success |
| build_silver_requests_merge | success |
| **validate_silver** | **failed** — GATE 2 |
| build_gold_zone_hourly | **upstream_failed** |
| refresh_rag_index | **upstream_failed** |
| smoke_test_rag | **upstream_failed** |
| end | upstream_failed |

Screenshot: [airflow_gate2_failure.png](../airflow/airflow_gate2_failure.png)

```
  "success": false,
  "suite": "silver_requests_suite",
  "checkpoint": "silver_requests_checkpoint",
  "evaluated": 11,
  "successful": 10,
  "failed_expectations": [
    {
      "expectation": "expect_table_row_count_to_be_between",
      "column": null,
      "unexpected_count": null,
      "unexpected_percent": 0,
      "partial_unexpected_list": []
    }
  ]
}
[lineage] FAIL   job=validate_silver run=2b583484-737d-4b98-853a-0f420b8d811f err=GE checkpoint 'silver_requests_checkpoint' FAILED: 1 expectation(s) failed - ['expect_table_row_count_to_be_between']
[2026-08-05T23:40:10.325+0300] {logging_mixin.py:190} INFO - --- stderr ---
QUALITY GATE BLOCKED THE PIPELINE: GE checkpoint 'silver_requests_checkpoint' FAILED: 1 expectation(s) failed - ['expect_table_row_count_to_be_between']
[2026-08-05T23:40:10.327+0300] {taskinstance.py:3313} ERROR - Task failed with exception
Traceback (most recent call last):
  File "/Users/mohammed/codes/hajj-crowd-ops-platform/.venv-airflow/lib/python3.11/site-packages/airflow/models/taskinstance.py", line 768, in _execute_task
    result = _execute_callable(context=context, **execute_callable_kwargs)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
```
