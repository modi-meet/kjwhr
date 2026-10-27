import os
from datetime import UTC, datetime, timedelta

import pandas as pd
import pytest

# Tests are deterministic and offline unless a test explicitly exercises the live path.
os.environ.setdefault("DATA_SOURCE", "snapshot")


def ts(s: str) -> pd.Timestamp:
    return pd.Timestamp(s, tz="UTC")


@pytest.fixture
def actuals_hh() -> pd.DataFrame:
    """Half-hourly actuals for 2026-01-05, hour 03 missing its :30 half, hour 04 null."""
    rows = []
    t0 = datetime(2026, 1, 5, tzinfo=UTC)
    for i in range(48):
        t = t0 + timedelta(minutes=30 * i)
        if t.hour == 3 and t.minute == 30:
            continue
        gen = None if t.hour == 4 else 1000 + 10 * i
        rows.append({"startTime": t.isoformat().replace("+00:00", "Z"), "generation": gen})
    return pd.DataFrame(rows)


@pytest.fixture
def forecasts() -> pd.DataFrame:
    """Three D-1 publications (02:30, 07:30, 09:30) plus one D-2 and one post-cutoff run."""
    rows = []
    starts = [datetime(2026, 1, 5, tzinfo=UTC) + timedelta(hours=h) for h in range(-3, 27)]
    for pub in [
        "2026-01-03T22:30",
        "2026-01-04T02:30",
        "2026-01-04T07:30",
        "2026-01-04T09:30",
        "2026-01-04T11:30",
    ]:
        p = datetime.fromisoformat(pub).replace(tzinfo=UTC)
        base = {"22:30": 900, "02:30": 1100, "07:30": 1050, "09:30": 1020, "11:30": 990}[pub[-5:]]
        for s in starts:
            rows.append(
                {
                    "publishTime": p.isoformat().replace("+00:00", "Z"),
                    "startTime": s.isoformat().replace("+00:00", "Z"),
                    "generation": base + 5 * s.hour,
                }
            )
    return pd.DataFrame(rows)
