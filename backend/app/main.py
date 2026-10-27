"""FastAPI application: three read-only endpoints over the committed Elexon snapshot."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from pathlib import Path

import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import data, metrics
from .models import AccuracyResponse, DecisionResponse, Meta
from .settings import settings

app = FastAPI(
    title="Wind Day-Ahead Decision Support",
    description=(
        "National GB wind: the forecast a day-ahead desk could act on at gate closure, "
        "and how wrong it tends to be. Data: Elexon FUELHH (WIND) and WINDFOR, January 2026."
    ),
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET"], allow_headers=["*"])

ASSUMPTIONS = {
    "decision_window": (
        f"Purchase decisions made {settings.decision_from:%d %b %Y} to "
        f"{settings.decision_to:%d %b %Y} (decision day D-1) for delivery days D = D-1 + 1."
    ),
    "cutoff_rule": (
        "Decision vintage = latest WINDFOR publication with publishTime strictly before the "
        "gate closure on D-1 (default 09:50 UTC, GB day-ahead 60-min auction). "
        "January UK time == UTC."
    ),
    "aggregation": (
        "Actuals are half-hourly; an hour is the mean of HH:00 and HH:30, labelled by hour start. "
        "Hours with a missing half are dropped and counted against coverage."
    ),
    "error_sign": "error = forecast - actual. Positive = over-forecast = the desk is short.",
    "band": "P10/P50/P90 are signed percentiles of hourly error over the whole window (in-sample).",
}


def _parse_cutoff(s: str) -> time:
    try:
        return datetime.strptime(s, "%H:%M").time()
    except ValueError as e:  # pragma: no cover
        raise HTTPException(400, f"cutoff must be HH:MM, got {s!r}") from e


def _parse_day(s: str, name: str) -> date:
    try:
        return date.fromisoformat(s)
    except ValueError as e:
        raise HTTPException(400, f"{name} must be YYYY-MM-DD, got {s!r}") from e


def _points(df: pd.DataFrame) -> list[dict]:
    out = []
    for _, r in df.iterrows():
        out.append(
            {
                "hour": r["hour"].isoformat(),
                "lead_h": metrics._f(r.get("lead_h")),
                "forecast_mw": metrics._f(r.get("forecast_mw")),
                "actual_mw": metrics._f(r.get("actual_mw")),
                "error_mw": metrics._f(r.get("error_mw")),
            }
        )
    return out


def _default_decision_day(ds: data.Dataset) -> date:
    """The day with the largest daily MWh miss: the most instructive one to open on."""
    t = ds.decision_table(settings.cutoff_time)
    w = metrics.worst_day(metrics.by_day(t))
    return date.fromisoformat(w["decision_day"]) if w else settings.decision_from


@app.get("/api/meta", response_model=Meta)
def meta() -> dict:
    ds = data.get_dataset()
    vt = sorted({p.strftime("%H:%M") for p in ds.forecasts["publish"].drop_duplicates()})
    return {
        "decision_from": settings.decision_from.isoformat(),
        "decision_to": settings.decision_to.isoformat(),
        "delivery_from": (settings.decision_from + timedelta(days=1)).isoformat(),
        "delivery_to": (settings.decision_to + timedelta(days=1)).isoformat(),
        "cutoff_default": settings.cutoff_time.strftime("%H:%M"),
        "cutoff_presets": list(settings.cutoff_presets),
        "default_decision_day": _default_decision_day(ds).isoformat(),
        "vintage_times": vt,
        "snapshot": ds.meta,
        "assumptions": ASSUMPTIONS,
    }


@app.get("/api/decision/{decision_day}", response_model=DecisionResponse)
def decision(
    decision_day: str,
    cutoff: str = Query(default=None, description="Gate closure HH:MM UTC on the decision day"),
) -> dict:
    ds = data.get_dataset()
    d = _parse_day(decision_day, "decision_day")
    if not (settings.decision_from <= d <= settings.decision_to):
        raise HTTPException(
            404, f"decision day must be within {settings.decision_from}..{settings.decision_to}"
        )
    ct = _parse_cutoff(cutoff) if cutoff else settings.cutoff_time
    delivery = d + timedelta(days=1)

    pub = data.select_vintage(ds.forecasts, d, ct)
    if pub is None:
        raise HTTPException(404, "no forecast publication before the cutoff on that day")
    gate = pd.Timestamp(datetime.combine(d, ct), tz="UTC")
    same_day_pubs = data.publications_on(ds.forecasts, d)
    expected = [p for p in same_day_pubs if p < gate]
    fallback_used = pub.date() != d or (expected and pub != expected[-1])

    sl = data.delivery_slice(ds.forecasts, pub, delivery).merge(ds.actuals_h, on="hour", how="left")
    sl["lead_h"] = (sl["hour"] - pub).dt.total_seconds() / 3600.0
    sl["error_mw"] = sl["forecast_mw"] - sl["actual_mw"]

    # Band from the whole window at this cutoff (in-sample, stated in the UI).
    table = ds.decision_table(ct)
    band = {
        **metrics.error_band(table),
        "source": "January 2026 hourly errors at this cutoff (in-sample)",
    }

    # Up to two earlier same-day vintages for the "how did the forecast evolve" overlay.
    earlier = [p for p in same_day_pubs if p < pub]
    picks = []
    if earlier:
        picks.append(earlier[0])
        if len(earlier) > 2:
            picks.append(earlier[len(earlier) // 2])
        elif len(earlier) == 2:
            picks.append(earlier[1])
    others = []
    for p in picks:
        s = data.delivery_slice(ds.forecasts, p, delivery)
        others.append({"publish": p.isoformat(), "label": f"D-1 {p:%H:%M}", "points": _points(s)})

    blocks_f = metrics.block_averages(sl, "forecast_mw")
    blocks_a = metrics.block_averages(sl, "actual_mw")
    p90 = band["p90"]
    cons = metrics._f((sl["forecast_mw"] - p90).clip(lower=0).sum()) if p90 is not None else None
    return {
        "decision_day": d.isoformat(),
        "delivery_day": delivery.isoformat(),
        "cutoff": ct.strftime("%H:%M"),
        "gate_closure": gate.isoformat(),
        "publish": pub.isoformat(),
        "vintage_label": f"D-1 {pub:%H:%M}"
        if pub.date() == d
        else f"D-{(d - pub.date()).days + 1} {pub:%H:%M}",
        "forecast_age_min": int((gate - pub).total_seconds() // 60),
        "fallback_used": bool(fallback_used),
        "points": _points(sl),
        "other_vintages": others,
        "band": band,
        "blocks_forecast": blocks_f,
        "blocks_actual": blocks_a,
        "conservative_daily_mwh": cons,
        "actual_available": bool(sl["actual_mw"].notna().any()),
        "margin_table": metrics.margin_table(sl, band),
        "day_summary": metrics.summary(sl),
    }


@app.get("/api/accuracy", response_model=AccuracyResponse)
def accuracy(
    from_day: str = Query(default=None, alias="from"),
    to_day: str = Query(default=None, alias="to"),
    cutoff: str = Query(default=None),
) -> dict:
    ds = data.get_dataset()
    a = _parse_day(from_day, "from") if from_day else settings.decision_from
    b = _parse_day(to_day, "to") if to_day else settings.decision_to
    a, b = max(a, settings.decision_from), min(b, settings.decision_to)
    if a > b:
        raise HTTPException(400, "from must be <= to")
    ct = _parse_cutoff(cutoff) if cutoff else settings.cutoff_time

    t = ds.decision_table(ct, a, b)
    v = ds.vintage_table(a, b)
    band = {
        **metrics.error_band(t),
        "source": "signed hourly error percentiles over the selected window (in-sample)",
    }
    days = metrics.by_day(t)
    return {
        "from_day": a.isoformat(),
        "to_day": b.isoformat(),
        "cutoff": ct.strftime("%H:%M"),
        "summary": metrics.summary(t),
        "band": band,
        "backtest": metrics.band_backtest(t, band),
        "histogram": metrics.histogram(t),
        "by_hour": metrics.by_hour_of_day(t),
        "by_day": days,
        "by_vintage": metrics.by_vintage(v),
        "by_forecast_level": metrics.by_forecast_level(t),
        "worst_day": metrics.worst_day(days),
        "series": _points(t),
    }


@app.get("/api/health")
def health() -> dict:
    return {"ok": True}


# ---------------------------------------------------------------- static bundle (Docker image)
# When the React build exists next to the backend (single-container image), serve it here.
# On Vercel the static files are served by the platform and only /api/* reaches this app.
_DIST = Path(__file__).resolve().parents[2] / "web" / "dist"
if _DIST.is_dir():  # pragma: no cover
    app.mount("/assets", StaticFiles(directory=_DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        file = _DIST / path
        if path and file.is_file():
            return FileResponse(file)
        return FileResponse(_DIST / "index.html")
