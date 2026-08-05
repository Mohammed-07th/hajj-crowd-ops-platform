"""Zone reference set, loaded once from data/reference/zones.csv.

The contract validates `zone_id` against this set, which makes an unknown zone
code a *contract* violation rather than something discovered three layers later
when a join silently drops rows.
"""

from __future__ import annotations

import csv
from functools import lru_cache

from config.settings import settings


@lru_cache(maxsize=1)
def zone_reference() -> dict[str, dict[str, str | int]]:
    path = settings.reference_dir / "zones.csv"
    with path.open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    return {
        r["zone_id"]: {
            "site": r["site"],
            "zone_name_en": r["zone_name_en"],
            "zone_name_ar": r["zone_name_ar"],
            "capacity": int(r["capacity"]),
            "zone_type": r["zone_type"],
        }
        for r in rows
    }


@lru_cache(maxsize=1)
def valid_zone_ids() -> frozenset[str]:
    return frozenset(zone_reference().keys())


def zone_capacity(zone_id: str) -> int | None:
    zone = zone_reference().get(zone_id)
    return None if zone is None else int(zone["capacity"])
