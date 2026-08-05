"""No-op replacement for the `setproctitle` C extension. macOS only.

Why this exists
---------------
Gunicorn (and Airflow's scheduler, dag-processor and serve_logs) rename their
worker processes so `ps` shows "gunicorn: worker [airflow-webserver]" instead of
a bare python command. On this machine that call segfaults every worker:

    libsystem_trace.dylib   _os_log_preferences_refresh
    CoreFoundation          CFBundleGetFunctionPointerForName
    _setproctitle...so      darwin_set_process_title
    _setproctitle...so      spt_setproctitle
    -> EXC_BAD_ACCESS (SIGSEGV)

setproctitle's Darwin implementation reaches into LaunchServices through a
private CoreFoundation entry point that no longer works on current macOS. The
result is a tight fork/crash loop: the webserver never binds port 8080 and the
scheduler's log server never starts. Reproduced on setproctitle 1.3.4 and
1.3.7, so upgrading is not a fix.

What this changes
-----------------
Nothing functional. Process titles are cosmetic - they affect what `ps` prints,
not scheduling, execution, logging or the metadata database. Airflow, gunicorn
and the scheduler are all the real components; only the renaming is disabled.

This directory is prepended to PYTHONPATH by scripts/start_airflow.sh so it
shadows the installed package, which keeps the workaround visible in the repo
and reversible by deleting one line, rather than hidden in a patched
site-packages.
"""

from __future__ import annotations

import sys

_title = " ".join(sys.argv)


def setproctitle(title: str) -> None:  # noqa: D103 - mirrors upstream signature
    global _title
    _title = title


def getproctitle() -> str:  # noqa: D103
    return _title


def setthreadtitle(title: str) -> None:  # noqa: D103
    return None


def getthreadtitle() -> str:  # noqa: D103
    return ""
