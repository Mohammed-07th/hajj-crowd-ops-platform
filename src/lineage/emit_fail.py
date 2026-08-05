"""Emit a standalone OpenLineage FAIL event.

Called from the Airflow `on_failure_callback` so a task-level failure appears in
the lineage stream even when the failure happened outside an instrumented stage
(a subprocess crash, an OOM kill, a retry exhaustion).
"""

from __future__ import annotations

import argparse
import sys

from src.lineage.emitter import lineage_run


class _TaskFailure(RuntimeError):
    pass


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--job", required=True)
    ap.add_argument("--message", default="task failed")
    args = ap.parse_args()

    try:
        with lineage_run(args.job):
            raise _TaskFailure(args.message)
    except _TaskFailure:
        # Expected: the context manager has emitted START then FAIL.
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
