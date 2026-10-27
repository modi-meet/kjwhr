from datetime import date

import pandas as pd

from backend.app import metrics
from backend.tests.conftest import ts


def _table():
    hours = pd.date_range("2026-01-05T00:00", periods=6, freq="h", tz="UTC")
    return pd.DataFrame(
        {
            "decision_day": [date(2026, 1, 4)] * 6,
            "delivery_day": [date(2026, 1, 5)] * 6,
            "publish": [ts("2026-01-04T09:30")] * 6,
            "hour": hours,
            "lead_h": [14.5 + i for i in range(6)],
            "forecast_mw": [100, 100, 100, 100, 100, 100],
            "actual_mw": [90, 110, 80, 100, None, 120],
            "error_mw": [10, -10, 20, 0, None, -20],
        }
    )


def test_summary_sign_convention_and_coverage():
    s = metrics.summary(_table())
    assert s["n_hours"] == 6 and s["n_matched"] == 5
    assert s["coverage_pct"] == 83.3
    assert s["mae_mw"] == 12.0
    assert s["bias_mw"] == 0.0
    assert s["nmae_pct"] == 12.0  # mean actual = 100
    assert s["p90_abs_mw"] == 20.0


def test_error_band_is_signed():
    b = metrics.error_band(_table())
    assert b["p10"] < 0 < b["p90"]
    assert b["p50"] == 0.0


def test_band_backtest_counts_days_short_on_daily_mwh():
    t = _table()
    bt = metrics.band_backtest(t, {"p10": -15, "p50": 0, "p90": 15})
    # in band: actual within [f-15, f+15] -> 90,110,100 yes; 80,120 no -> 60%
    assert bt["hours_in_band_pct"] == 60.0
    # error > 15 only for the 80 MW hour -> 20% of matched hours
    assert bt["hours_short_pct"] == 20.0
    # daily actual 500 vs conservative 5*(100-15)=425 -> not short
    assert bt["days_short"] == 0 and bt["days_total"] == 1


def test_by_day_reports_worst_hour():
    d = metrics.by_day(_table())[0]
    assert d["forecast_mwh"] == 600.0 and d["actual_mwh"] == 500.0
    assert d["worst_error_mw"] in (20.0, -20.0)
    assert d["n_matched"] == 5


def test_margin_table_conservative_wind_never_negative():
    hourly = _table()[["hour", "forecast_mw", "lead_h", "actual_mw"]]
    rows = metrics.margin_table(hourly, {"p10": -30, "p50": 5, "p90": 150})
    assert rows[0]["wind_p90_mw"] == 0.0
    assert rows[0]["wind_p10_mw"] == 130.0
    assert rows[0]["extra_to_buy_mw"] == 150.0


def test_block_averages_peak_window():
    hours = pd.date_range("2026-01-05T00:00", periods=24, freq="h", tz="UTC")
    df = pd.DataFrame({"hour": hours, "forecast_mw": [1.0] * 7 + [10.0] * 12 + [1.0] * 5})
    b = metrics.block_averages(df)
    assert b["peak_mw"] == 10.0
    assert b["daily_mwh"] == 132.0
    assert b["baseload_mw"] == 5.5


def test_histogram_shape():
    h = metrics.histogram(_table(), bins=4)
    assert len(h["edges"]) == 5 and sum(h["counts"]) == 5
