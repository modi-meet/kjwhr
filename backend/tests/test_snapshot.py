"""Invariants of the committed snapshot: cheap guards that the data behind the demo is sane."""

from datetime import time, timedelta

from backend.app import data
from backend.app.settings import settings


def test_every_decision_day_has_a_vintage_before_cutoff():
    ds = data.get_dataset()
    missing = [
        d
        for d in data.decision_days()
        if data.select_vintage(ds.forecasts, d, settings.cutoff_time) is None
    ]
    assert missing == []


def test_each_publication_covers_about_three_days_hourly():
    ds = data.get_dataset()
    sizes = ds.forecasts.groupby("publish").size()
    assert sizes.between(60, 80).all(), sizes[~sizes.between(60, 80)]


def test_decision_vintage_gives_24_hours_for_every_delivery_day():
    ds = data.get_dataset()
    t = ds.decision_table(settings.cutoff_time)
    per_day = t.groupby("delivery_day").size()
    assert len(per_day) == (settings.decision_to - settings.decision_from).days + 1
    assert (per_day == 24).all()
    assert t["actual_mw"].notna().mean() > 0.95


def test_actuals_cover_all_delivery_days():
    ds = data.get_dataset()
    days = set(ds.actuals_h["hour"].dt.date)
    for d in data.decision_days():
        assert d + timedelta(days=1) in days


def test_default_cutoff_picks_the_0930_run_for_most_days():
    ds = data.get_dataset()
    picks = [data.select_vintage(ds.forecasts, d, time(9, 50)) for d in data.decision_days()]
    hhmm = [p.strftime("%H:%M") for p in picks]
    assert hhmm.count("09:30") >= 0.8 * len(hhmm), hhmm
