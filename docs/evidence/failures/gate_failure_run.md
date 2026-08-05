# Failure demo 3 — quality gate halts the pipeline

DAG run: gate_failure_demo, triggered with {"corrupt_rate": 0.4}
Task states: validate_bronze=failed, build_silver_occupancy=upstream_failed, build_gold_zone_hourly=upstream_failed

```
    ret = args.func(args, dag=self.dag)
          ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/mohammed/codes/hajj-crowd-ops-platform/.venv-airflow/lib/python3.11/site-packages/airflow/cli/cli_config.py", line 49, in command
    return func(*args, **kwargs)
           ^^^^^^^^^^^^^^^^^^^^^
  File "/Users/mohammed/codes/hajj-crowd-ops-platform/.venv-airflow/lib/python3.11/site-packages/airflow/utils/cli.py", line 116, in wrapper
    return f(*args, **kwargs)
           ^^^^^^^^^^^^^^^^^^
  File "/Users/mohammed/codes/hajj-crowd-ops-platform/.venv-airflow/lib/python3.11/site-packages/airflow/cli/commands/task_command.py", line 483, in task_run
    task_return_code = _run_task_by_selected_method(args, _dag, ti)
                       ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/mohammed/codes/hajj-crowd-ops-platform/.venv-airflow/lib/python3.11/site-packages/airflow/cli/commands/task_command.py", line 256, in _run_task_by_selected_method
    return _run_raw_task(args, ti)
           ^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/mohammed/codes/hajj-crowd-ops-platform/.venv-airflow/lib/python3.11/site-packages/airflow/cli/commands/task_command.py", line 341, in _run_raw_task
    return ti._run_raw_task(
           ^^^^^^^^^^^^^^^^^
  File "/Users/mohammed/codes/hajj-crowd-ops-platform/.venv-airflow/lib/python3.11/site-packages/airflow/utils/session.py", line 97, in wrapper
    return func(*args, session=session, **kwargs)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/mohammed/codes/hajj-crowd-ops-platform/.venv-airflow/lib/python3.11/site-packages/airflow/models/taskinstance.py", line 3006, in _run_raw_task
    return _run_raw_task(
           ^^^^^^^^^^^^^^
  File "/Users/mohammed/codes/hajj-crowd-ops-platform/.venv-airflow/lib/python3.11/site-packages/airflow/models/taskinstance.py", line 274, in _run_raw_task
    TaskInstance._execute_task_with_callbacks(
  File "/Users/mohammed/codes/hajj-crowd-ops-platform/.venv-airflow/lib/python3.11/site-packages/airflow/models/taskinstance.py", line 3161, in _execute_task_with_callbacks
    result = self._execute_task(context, task_orig)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/mohammed/codes/hajj-crowd-ops-platform/.venv-airflow/lib/python3.11/site-packages/airflow/models/taskinstance.py", line 3185, in _execute_task
    return _execute_task(self, context, task_orig)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/mohammed/codes/hajj-crowd-ops-platform/.venv-airflow/lib/python3.11/site-packages/airflow/models/taskinstance.py", line 768, in _execute_task
    result = _execute_callable(context=context, **execute_callable_kwargs)
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/mohammed/codes/hajj-crowd-ops-platform/.venv-airflow/lib/python3.11/site-packages/airflow/models/taskinstance.py", line 734, in _execute_callable
    return ExecutionCallableRunner(
           ^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/mohammed/codes/hajj-crowd-ops-platform/.venv-airflow/lib/python3.11/site-packages/airflow/utils/operator_helpers.py", line 252, in run
    return self.func(*args, **kwargs)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/mohammed/codes/hajj-crowd-ops-platform/.venv-airflow/lib/python3.11/site-packages/airflow/models/baseoperator.py", line 424, in wrapper
    return func(self, *args, **kwargs)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/mohammed/codes/hajj-crowd-ops-platform/.venv-airflow/lib/python3.11/site-packages/airflow/operators/python.py", line 238, in execute
    return_value = self.execute_callable()
                   ^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/mohammed/codes/hajj-crowd-ops-platform/.venv-airflow/lib/python3.11/site-packages/airflow/operators/python.py", line 256, in execute_callable
    return runner.run(*self.op_args, **self.op_kwargs)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/mohammed/codes/hajj-crowd-ops-platform/.venv-airflow/lib/python3.11/site-packages/airflow/utils/operator_helpers.py", line 252, in run
    return self.func(*args, **kwargs)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/Users/mohammed/codes/hajj-crowd-ops-platform/dags/hajj_ops_pipeline.py", line 113, in validate_bronze
    _run_stage("src.quality.run_gate",
  File "/Users/mohammed/codes/hajj-crowd-ops-platform/dags/hajj_ops_pipeline.py", line 65, in _run_stage
    raise AirflowException(
airflow.exceptions.AirflowException: validate_bronze failed (exit 2) running src.quality.run_gate. Last stderr line: QUALITY GATE BLOCKED THE PIPELINE: GE checkpoint 'bronze_checkpoint' FAILED: 1 expectation(s) failed - ['expect_table_row_count_to_be_between']
[2026-08-05T22:32:01.214+0300] {local_task_job_runner.py:266} INFO - Task exited with return code 1
[2026-08-05T22:32:01.220+0300] {taskinstance.py:3901} INFO - 0 downstream tasks scheduled from follow-on schedule check
[2026-08-05T22:32:01.221+0300] {local_task_job_runner.py:245} INFO - ::endgroup::
```
