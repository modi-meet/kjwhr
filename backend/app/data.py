"""Data layer: snapshot loading, hourly alignment, vintage selection, decision table.

Conventions (see README "Assumptions"):
  * All timestamps are UTC.  January in the UK is on GMT, so UTC == local.
  * An *hour* of actuals is the mean of the HH:00 and HH:30 FUELHH rows, labelled by hour
    start.  Both halves must be present, otherwise the hour is dropped.
  * A *vintage* is one WINDFOR publication (one exact publishTime).
  * The *decision vintage* for delivery day D is the latest publication with
    publishTime strictly before the cutoff on the decision day D-1.
  * error = forecast - actual  (positive = over-forecast = the desk is short).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from functools import lru_cache
from pathlib import Path

import pandas as pd

from .settings import settings

UTC = "UTC"


# --------------------------------------------------------------------------- loading


def load_snapshot(snapshot_dir: Path | None = None) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Return (actuals_halfhourly, forecasts, meta) from the committed JSON snapshot."""
    d = snapshot_dir or settings.snapshot_path
    actuals = pd.DataFrame(json.loads((d / "fuelhh_wind.json").read_text()))
    forecasts = pd.DataFrame(json.loads((d / "windfor.json").read_text()))
    meta = json.loads((d / "snapshot_meta.json").read_text())
    return normalise_actuals(actuals), normalise_forecasts(forecasts), meta


def normalise_actuals(df: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame(
        {
            "start": pd.to_datetime(df["startTime"], utc=True),
            "actual_mw": pd.to_numeric(df["generation"], errors="coerce"),
        }
    )
    if "publishTime" in df:
        out["publish"] = pd.to_datetime(df["publishTime"], utc=True)
        out = out.sort_values("publish")
    # Defensive dedupe: one row per half hour, keep the latest publication.
    out = out.drop_duplicates("start", keep="last")
    return out.sort_values("start").reset_index(drop=True)[["start", "actual_mw"]]


def normalise_forecasts(df: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame(
        {
            "publish": pd.to_datetime(df["publishTime"], utc=True),
            "start": pd.to_datetime(df["startTime"], utc=True),
            "forecast_mw": pd.to_numeric(df["generation"], errors="coerce"),
        }
    )
    out = out.drop_duplicates(["publish", "start"], keep="last")
    return out.sort_values(["publish", "start"]).reset_index(drop=True)


# --------------------------------------------------------------------------- transforms


def hourly_actuals(actuals_hh: pd.DataFrame) -> pd.DataFrame:
    """Mean of the two half-hours, labelled by hour start; hours with a missing half are dropped."""
    df = actuals_hh.dropna(subset=["actual_mw"]).copy()
    df["hour"] = df["start"].dt.floor("h")
    g = df.groupby("hour")["actual_mw"].agg(["mean", "count"]).reset_index()
    g = g[g["count"] == 2]
    return g.rename(columns={"mean": "actual_mw"})[["hour", "actual_mw"]].reset_index(drop=True)


def drop_hindcast(forecasts: pd.DataFrame) -> pd.DataFrame:
    """A publication also carries rows for hours already in the past; keep only true forecasts."""
    return forecasts[forecasts["start"] >= forecasts["publish"]].reset_index(drop=True)


def select_vintage(
    forecasts: pd.DataFrame, decision_day: date, cutoff: time
) -> pd.Timestamp | None:
    """Latest publishTime strictly before `cutoff` on `decision_day`, or None."""
    gate = pd.Timestamp(datetime.combine(decision_day, cutoff), tz=UTC)
    pubs = forecasts.loc[forecasts["publish"] < gate, "publish"]
    return None if pubs.empty else pubs.max()


def publications_on(forecasts: pd.DataFrame, day: date) -> list[pd.Timestamp]:
    pubs = forecasts["publish"].drop_duplicates()
    return sorted(p for p in pubs if p.date() == day)


def delivery_slice(
    forecasts: pd.DataFrame, publish: pd.Timestamp, delivery_day: date
) -> pd.DataFrame:
    """Hourly forecast rows from one publication that fall on the delivery day."""
    f = forecasts[(forecasts["publish"] == publish) & (forecasts["start"].dt.date == delivery_day)]
    return f[["start", "forecast_mw"]].rename(columns={"start": "hour"}).reset_index(drop=True)


# --------------------------------------------------------------------------- decision table


@dataclass(frozen=True)
class DecisionRow:
    decision_day: date
    delivery_day: date
    publish: pd.Timestamp | None


def decision_days(start: date | None = None, end: date | None = None) -> list[date]:
    a, b = start or settings.decision_from, end or settings.decision_to
    return [a + timedelta(days=i) for i in range((b - a).days + 1)]


def build_decision_table(
    forecasts: pd.DataFrame,
    actuals_h: pd.DataFrame,
    cutoff: time,
    start: date | None = None,
    end: date | None = None,
) -> pd.DataFrame:
    """One row per (decision day, delivery hour) using the decision vintage.

    Columns: decision_day, delivery_day, publish, hour, lead_h, forecast_mw, actual_mw, error_mw.
    Hours without a matched actual keep NaN actual/error (counted in coverage, excluded from stats).
    """
    frames = []
    for d in decision_days(start, end):
        pub = select_vintage(forecasts, d, cutoff)
        if pub is None:
            continue
        s = delivery_slice(forecasts, pub, d + timedelta(days=1))
        if s.empty:
            continue
        s["decision_day"] = d
        s["delivery_day"] = d + timedelta(days=1)
        s["publish"] = pub
        frames.append(s)
    if not frames:
        return pd.DataFrame(
            columns=[
                "decision_day",
                "delivery_day",
                "publish",
                "hour",
                "lead_h",
                "forecast_mw",
                "actual_mw",
                "error_mw",
            ]
        )
    t = pd.concat(frames, ignore_index=True)
    t = t.merge(actuals_h, on="hour", how="left")
    t["lead_h"] = (t["hour"] - t["publish"]).dt.total_seconds() / 3600.0
    t["error_mw"] = t["forecast_mw"] - t["actual_mw"]
    cols = [
        "decision_day",
        "delivery_day",
        "publish",
        "hour",
        "lead_h",
        "forecast_mw",
        "actual_mw",
        "error_mw",
    ]
    return t[cols].sort_values(["delivery_day", "hour"]).reset_index(drop=True)


def build_vintage_table(
    forecasts: pd.DataFrame,
    actuals_h: pd.DataFrame,
    start: date | None = None,
    end: date | None = None,
) -> pd.DataFrame:
    """All D-1 publications for every delivery day, labelled by publish time-of-day.

    Used for the "error by vintage" view: does the 09:30 run beat the 02:30 run?
    """
    f = drop_hindcast(forecasts).copy()
    f["delivery_day"] = f["start"].dt.date
    f["publish_day"] = f["publish"].dt.date
    f = f[(f["delivery_day"] - f["publish_day"]) == timedelta(days=1)]
    days = set(d + timedelta(days=1) for d in decision_days(start, end))
    f = f[f["delivery_day"].isin(days)]
    f = f.rename(columns={"start": "hour"}).merge(actuals_h, on="hour", how="inner")
    f["vintage"] = "D-1 " + f["publish"].dt.strftime("%H:%M")
    f["error_mw"] = f["forecast_mw"] - f["actual_mw"]
    f["lead_h"] = (f["hour"] - f["publish"]).dt.total_seconds() / 3600.0
    return f[
        [
            "delivery_day",
            "publish",
            "vintage",
            "hour",
            "lead_h",
            "forecast_mw",
            "actual_mw",
            "error_mw",
        ]
    ]


# --------------------------------------------------------------------------- cached dataset


@dataclass
class Dataset:
    actuals_hh: pd.DataFrame
    actuals_h: pd.DataFrame
    forecasts: pd.DataFrame
    meta: dict

    def decision_table(
        self, cutoff: time, start: date | None = None, end: date | None = None
    ) -> pd.DataFrame:
        return build_decision_table(self.forecasts, self.actuals_h, cutoff, start, end)

    def vintage_table(self, start: date | None = None, end: date | None = None) -> pd.DataFrame:
        return build_vintage_table(self.forecasts, self.actuals_h, start, end)


@lru_cache(maxsize=1)
def get_dataset() -> Dataset:
    actuals_hh, forecasts, meta = load_snapshot()
    return Dataset(actuals_hh, hourly_actuals(actuals_hh), forecasts, meta)
