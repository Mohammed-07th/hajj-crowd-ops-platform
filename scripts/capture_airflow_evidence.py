"""Capture Airflow UI screenshots as committed evidence.

Scripted rather than hand-cropped so the examiner can regenerate the exact same
images:

    .venv/bin/python scripts/capture_airflow_evidence.py \
        --run green_run_1785957798 --name airflow_green_run

Requires the Airflow webserver to be running (make airflow).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = REPO_ROOT / "docs" / "evidence" / "airflow"
BASE = "http://localhost:8080"


def capture(run_id: str, name: str, username: str, password: str) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"{name}.png"

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1680, "height": 1050})

        page.goto(f"{BASE}/login/", wait_until="networkidle")
        page.fill("#username", username)
        page.fill("#password", password)
        page.click("input[type=submit], button[type=submit]")
        page.wait_for_load_state("networkidle")

        page.goto(f"{BASE}/dags/hajj_ops_pipeline/grid?dag_run_id={run_id}&tab=graph",
                  wait_until="networkidle")
        # The graph is rendered client-side; wait for a task node to exist
        # rather than for a fixed delay.
        page.wait_for_selector("text=build_gold_zone_hourly", timeout=30_000)
        page.wait_for_timeout(2500)
        page.screenshot(path=str(out), full_page=False)
        browser.close()

    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True, help="dag_run_id to screenshot")
    ap.add_argument("--name", required=True, help="output filename stem")
    ap.add_argument("--username", default="admin")
    ap.add_argument("--password", default="admin")
    args = ap.parse_args()

    out = capture(args.run, args.name, args.username, args.password)
    print(f"wrote {out} ({out.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
