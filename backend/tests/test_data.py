from datetime import date, time

import pandas as pd

from backend.app import data
from backend.tests.conftest import ts


def test_hourly_mean_is_labelled_by_hour_start(actuals_hh):
    h = data.hourly_actuals(data.normalise_actuals(actuals_hh))
    row = h[h["hour"] == ts("2026-01-05T00:00")].iloc[0]
    # halves are 1000 (00:00) and 1010 (00:30) -> mean 1005, labelled 00:00 not 01:00
    assert row["actual_mw"] == 1005
    assert ts("2026-01-05T01:00") in set(h["hour"])


def test_hour_with_missing_or_null_half_is_dropped(actuals_hh):
    h = data.hourly_actuals(data.normalise_actuals(actuals_hh))
    hours = set(h["hour"].dt.hour)
    assert 3 not in hours  # :30 half missing
    assert 4 not in hours  # generation null
    assert len(h) == 22


def test_select_vintage_is_strictly_before_cutoff(forecasts):
    f = data.normalise_forecasts(forecasts)
    assert data.select_vintage(f, date(2026, 1, 4), time(9, 50)) == ts("2026-01-04T09:30")
    # exactly-at-cutoff publication is NOT available
    assert data.select_vintage(f, date(2026, 1, 4), time(9, 30)) == ts("2026-01-04T07:30")
    assert data.select_vintage(f, date(2026, 1, 4), time(15, 30)) == ts("2026-01-04T11:30")
    assert data.select_vintage(f, date(2026, 1, 1), time(9, 50)) is None


def test_hindcast_rows_are_dropped():
    # A 09:30 publication carrying hours 08:00, 09:00 (past), 09:30-equal, and 10:00 (future).
    f = data.normalise_forecasts(
        pd.DataFrame(
            {
                "publishTime": ["2026-01-04T09:30:00Z"] * 4,
                "startTime": [
                    "2026-01-04T08:00:00Z",
                    "2026-01-04T09:00:00Z",
                    "2026-01-04T09:30:00Z",
                    "2026-01-04T10:00:00Z",
                ],
                "generation": [1, 2, 3, 4],
            }
        )
    )
    kept = data.drop_hindcast(f)
    assert list(kept["forecast_mw"]) == [3, 4]


def test_delivery_slice_has_24_hours_from_decision_vintage(forecasts):
    f = data.normalise_forecasts(forecasts)
    s = data.delivery_slice(f, ts("2026-01-04T09:30"), date(2026, 1, 5))
    assert len(s) == 24
    assert s["hour"].dt.date.nunique() == 1
    assert s["forecast_mw"].iloc[0] == 1020  # 09:30 base + 5*0


def test_decision_table_error_sign_and_lead(forecasts, actuals_hh):
    f = data.normalise_forecasts(forecasts)
    a = data.hourly_actuals(data.normalise_actuals(actuals_hh))
    t = data.build_decision_table(f, a, time(9, 50), date(2026, 1, 4), date(2026, 1, 4))
    assert len(t) == 24
    r = t[t["hour"] == ts("2026-01-05T00:00")].iloc[0]
    assert r["forecast_mw"] == 1020 and r["actual_mw"] == 1005
    assert r["error_mw"] == 15  # forecast - actual, positive = over-forecast
    assert r["lead_h"] == 14.5  # 09:30 D-1 -> 00:00 D
    # hours without actuals keep NaN error rather than being dropped
    assert t["error_mw"].isna().sum() == 2


def test_vintage_table_only_d_minus_1_publications(forecasts, actuals_hh):
    f = data.normalise_forecasts(forecasts)
    a = data.hourly_actuals(data.normalise_actuals(actuals_hh))
    v = data.build_vintage_table(f, a, date(2026, 1, 4), date(2026, 1, 4))
    assert set(v["vintage"]) == {"D-1 02:30", "D-1 07:30", "D-1 09:30", "D-1 11:30"}
    assert (v["delivery_day"] == date(2026, 1, 5)).all()


def test_dedupe_keeps_latest_publication():
    df = pd.DataFrame(
        {
            "startTime": ["2026-01-05T00:00:00Z"] * 2,
            "generation": [1, 2],
            "publishTime": ["2026-01-05T00:30:00Z", "2026-01-05T01:00:00Z"],
        }
    )
    a = data.normalise_actuals(df)
    assert len(a) == 1 and a["actual_mw"].iloc[0] == 2
