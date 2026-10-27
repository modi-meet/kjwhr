"""Pull the January 2026 Elexon data into a committed JSON snapshot.

Why a snapshot: the month is historical and fixed, so serving from a committed file removes
Elexon availability from the demo, keeps the Vercel function stateless and makes tests
deterministic.  Re-run with --refresh to re-pull from the live API.

Usage:
    python backend/scripts/fetch_snapshot.py            # skip if files exist
    python backend/scripts/fetch_snapshot.py --refresh  # always re-pull
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.app.elexon import fetch_fuelhh, fetch_windfor, fuelhh_url, windfor_url  # noqa: E402
from backend.app.settings import settings  # noqa: E402

# Decision days D-1 = decision_from..decision_to  ->  delivery days D = +1 day each.
DELIVERY_FROM = settings.decision_from + timedelta(days=1)
DELIVERY_TO = settings.decision_to + timedelta(days=1)
# Actuals from the first decision day (needed for a persistence baseline) to the last delivery day.
FUELHH_FROM, FUELHH_TO = settings.decision_from, DELIVERY_TO
# Forecasts published from the day before the first decision day through the last decision day.
WINDFOR_FROM = datetime.combine(
    settings.decision_from - timedelta(days=1), datetime.min.time(), UTC
)
WINDFOR_TO = datetime.combine(settings.decision_to + timedelta(days=1), datetime.min.time(), UTC)


def dedupe(rows: list[dict], key: tuple[str, ...], prefer: str | None = None) -> list[dict]:
    """Keep one row per key.  With `prefer`, keep the row with the largest value of that field."""
    best: dict[tuple, dict] = {}
    for r in rows:
        k = tuple(r[f] for f in key)
        if k not in best or (prefer and r[prefer] > best[k][prefer]):
            best[k] = r
    return list(best.values())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true", help="re-pull even if the snapshot exists")
    args = ap.parse_args()

    out = settings.snapshot_path
    out.mkdir(parents=True, exist_ok=True)
    f_path, w_path, m_path = (
        out / "fuelhh_wind.json",
        out / "windfor.json",
        out / "snapshot_meta.json",
    )
    if not args.refresh and f_path.exists() and w_path.exists():
        print(f"snapshot already present in {out}; use --refresh to re-pull")
        return 0

    print("fetching FUELHH", fuelhh_url(FUELHH_FROM, FUELHH_TO))
    fuelhh = fetch_fuelhh(FUELHH_FROM, FUELHH_TO)
    n_f_raw = len(fuelhh)
    fuelhh = dedupe(fuelhh, ("startTime",), prefer="publishTime")
    fuelhh.sort(key=lambda r: r["startTime"])

    print("fetching WINDFOR", windfor_url(WINDFOR_FROM, WINDFOR_TO))
    windfor = fetch_windfor(WINDFOR_FROM, WINDFOR_TO)
    n_w_raw = len(windfor)
    windfor = dedupe(windfor, ("publishTime", "startTime"))
    windfor.sort(key=lambda r: (r["publishTime"], r["startTime"]))

    keep_f = ("startTime", "settlementDate", "settlementPeriod", "generation", "publishTime")
    keep_w = ("publishTime", "startTime", "generation")
    fuelhh_slim = [{k: r.get(k) for k in keep_f} for r in fuelhh]
    windfor_slim = [{k: r.get(k) for k in keep_w} for r in windfor]

    f_path.write_text(json.dumps(fuelhh_slim, separators=(",", ":")))
    w_path.write_text(json.dumps(windfor_slim, separators=(",", ":")))

    pubs = sorted({r["publishTime"] for r in windfor_slim})
    meta = {
        "fetched_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "sources": {
            "FUELHH": fuelhh_url(FUELHH_FROM, FUELHH_TO),
            "WINDFOR": windfor_url(WINDFOR_FROM, WINDFOR_TO),
        },
        "fuelhh": {
            "rows_raw": n_f_raw,
            "rows": len(fuelhh_slim),
            "start_min": fuelhh_slim[0]["startTime"],
            "start_max": fuelhh_slim[-1]["startTime"],
        },
        "windfor": {
            "rows_raw": n_w_raw,
            "rows": len(windfor_slim),
            "publications": len(pubs),
            "publish_min": pubs[0],
            "publish_max": pubs[-1],
        },
    }
    m_path.write_text(json.dumps(meta, indent=2))
    print(json.dumps(meta, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
