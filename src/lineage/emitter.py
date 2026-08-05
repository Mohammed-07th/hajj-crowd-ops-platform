"""OpenLineage instrumentation.

Every pipeline stage emits START before it reads, COMPLETE after it writes (with
the output row count as an OutputStatisticsOutputDatasetFacet), and FAIL from
the exception handler. Events are real OpenLineage RunEvents serialised by the
official client - the only thing that differs from a Marquez deployment is the
transport, which writes newline-delimited JSON to
docs/evidence/lineage/events.jsonl instead of POSTing to an HTTP collector.
That keeps a Marquez + Postgres pair out of a 5 GB Docker allocation while the
emitted payloads stay byte-identical to what Marquez would have received.

Instrumentation is a context manager, so wiring a stage costs one line and
required zero changes to the pipeline logic itself:

    with lineage_run("build_gold_zone_hourly",
                     inputs=["silver_zone_occupancy"],
                     outputs=["gold_zone_hourly"]) as run:
        ...
        run.record_output_rows("gold_zone_hourly", n)
"""

from __future__ import annotations

import traceback
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from openlineage.client import OpenLineageClient
from openlineage.client.event_v2 import InputDataset, Job, OutputDataset, Run, RunEvent, RunState
from openlineage.client.facet_v2 import error_message_run, output_statistics_output_dataset
from openlineage.client.transport.file import FileConfig, FileTransport

from config.settings import REPO_ROOT, settings

NAMESPACE = settings.openlineage_namespace


def _client() -> OpenLineageClient:
    path = Path(settings.openlineage_events_path)
    if not path.is_absolute():
        path = REPO_ROOT / path
    path.parent.mkdir(parents=True, exist_ok=True)
    # append=True: a DAG run appends to the same file so the whole run's
    # lineage is one readable stream.
    return OpenLineageClient(transport=FileTransport(FileConfig(log_file_path=str(path), append=True)))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class LineageRun:
    """Handle passed to the instrumented block."""

    def __init__(self, job_name: str, run_id: str) -> None:
        self.job_name = job_name
        self.run_id = run_id
        self._output_rows: dict[str, int] = {}

    def record_output_rows(self, dataset: str, rows: int) -> None:
        self._output_rows[dataset] = rows

    @property
    def output_rows(self) -> dict[str, int]:
        return dict(self._output_rows)


def _datasets(names: list[str], rows: dict[str, int] | None = None, output: bool = False):
    rows = rows or {}
    out = []
    for name in names:
        if output:
            facets = {}
            if name in rows:
                facets["outputStatistics"] = output_statistics_output_dataset.OutputStatisticsOutputDatasetFacet(
                    rowCount=rows[name]
                )
            out.append(OutputDataset(namespace=NAMESPACE, name=name, outputFacets=facets))
        else:
            out.append(InputDataset(namespace=NAMESPACE, name=name))
    return out


@contextmanager
def lineage_run(
    job_name: str,
    inputs: list[str] | None = None,
    outputs: list[str] | None = None,
) -> Iterator[LineageRun]:
    inputs = inputs or []
    outputs = outputs or []
    client = _client()
    run_id = str(uuid.uuid4())
    job = Job(namespace=NAMESPACE, name=job_name)
    handle = LineageRun(job_name, run_id)

    client.emit(RunEvent(
        eventType=RunState.START,
        eventTime=_now(),
        run=Run(runId=run_id),
        job=job,
        inputs=_datasets(inputs),
        outputs=_datasets(outputs),
        producer=f"https://github.com/Mohammed-07th/hajj-crowd-ops-platform",
    ))
    print(f"[lineage] START  job={job_name} run={run_id}", flush=True)

    try:
        yield handle
    except BaseException as exc:
        # FAIL carries the error message facet so the failure is diagnosable
        # from the lineage stream alone, without opening task logs.
        client.emit(RunEvent(
            eventType=RunState.FAIL,
            eventTime=_now(),
            run=Run(runId=run_id, facets={
                "errorMessage": error_message_run.ErrorMessageRunFacet(
                    message=str(exc),
                    programmingLanguage="python",
                    stackTrace="".join(traceback.format_exception(type(exc), exc, exc.__traceback__))[:4000],
                )
            }),
            job=job,
            inputs=_datasets(inputs),
            outputs=_datasets(outputs),
            producer=f"https://github.com/Mohammed-07th/hajj-crowd-ops-platform",
        ))
        print(f"[lineage] FAIL   job={job_name} run={run_id} err={exc}", flush=True)
        raise
    else:
        client.emit(RunEvent(
            eventType=RunState.COMPLETE,
            eventTime=_now(),
            run=Run(runId=run_id),
            job=job,
            inputs=_datasets(inputs),
            outputs=_datasets(outputs, handle.output_rows, output=True),
            producer=f"https://github.com/Mohammed-07th/hajj-crowd-ops-platform",
        ))
        print(f"[lineage] COMPLETE job={job_name} run={run_id} rows={handle.output_rows}", flush=True)
