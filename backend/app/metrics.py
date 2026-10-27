"""Forecast-accuracy metrics for a procurement desk.

All functions take the long "decision table" produced by data.build_decision_table
(columns: delivery_day, publish, hour, lead_h, forecast_mw, actual_mw, error_mw) or the
vintage table.  error_mw = forecast - actual; positive means the desk is short.

Percentiles are *signed* unless the name says abs.  MAPE is deliberately absent: calm hours
with near-zero actual generation make it meaningless.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

PEAK_HOURS = range(7, 19)  # 07:00-19:00 GB "peak" block


def _f(x) -> float | None:
    """Round for JSON; NaN -> None."""
    if x is None or (isinstance(x, float) and math.isnan(x)) or pd.isna(x):
        return None
    return round(float(x), 1)


def matched(t: pd.DataFrame) -> pd.DataFrame:
    return t.dropna(subset=["error_mw"])


# --------------------------------------------------------------------------- headline


def error_band(t: pd.DataFrame) -> dict:
    """Signed P10 / P50 / P90 of forecast - actual."""
    e = matched(t)["error_mw"]
    if e.empty:
        return {"p10": None, "p50": None, "p90": None}
    q = e.quantile([0.1, 0.5, 0.9])
    return {"p10": _f(q[0.1]), "p50": _f(q[0.5]), "p90": _f(q[0.9])}


def summary(t: pd.DataFrame) -> dict:
    m = matched(t)
    e = m["error_mw"]
    band = error_band(t)
    mean_actual = m["actual_mw"].mean() if not m.empty else float("nan")
    mae = e.abs().mean() if not m.empty else float("nan")
    return {
        "n_hours": int(len(t)),
        "n_matched": int(len(m)),
        "coverage_pct": _f(100.0 * len(m) / len(t)) if len(t) else None,
        "mae_mw": _f(mae),
        "rmse_mw": _f(math.sqrt((e**2).mean())) if not m.empty else None,
        "bias_mw": _f(e.mean()) if not m.empty else None,
        "nmae_pct": _f(100.0 * mae / mean_actual) if mean_actual and not m.empty else None,
        "p90_abs_mw": _f(e.abs().quantile(0.9)) if not m.empty else None,
        "mean_actual_mw": _f(mean_actual),
        "mean_forecast_mw": _f(m["forecast_mw"].mean()) if not m.empty else None,
        **{f"{k}_mw": v for k, v in band.items()},
    }


def band_backtest(t: pd.DataFrame, band: dict | None = None) -> dict:
    """How often the signed P10-P90 band contained the actual, and how often a P90 margin
    would still have left the desk short (hourly and per delivery day, on daily MWh)."""
    m = matched(t)
    band = band or error_band(t)
    if m.empty or band["p90"] is None:
        return {
            "hours_in_band_pct": None,
            "hours_short_pct": None,
            "days_short": None,
            "days_total": 0,
        }
    lo, hi = m["forecast_mw"] - band["p90"], m["forecast_mw"] - band["p10"]
    in_band = (m["actual_mw"] >= lo) & (m["actual_mw"] <= hi)
    hours_short = m["error_mw"] > band["p90"]
    daily = m.groupby("delivery_day").agg(
        actual=("actual_mw", "sum"), cons=("forecast_mw", "sum"), n=("hour", "size")
    )
    daily["cons"] = daily["cons"] - band["p90"] * daily["n"]
    days_short = int((daily["actual"] < daily["cons"]).sum())
    return {
        "hours_in_band_pct": _f(100.0 * in_band.mean()),
        "hours_short_pct": _f(100.0 * hours_short.mean()),
        "days_short": days_short,
        "days_total": int(len(daily)),
    }


# --------------------------------------------------------------------------- breakdowns


def by_hour_of_day(t: pd.DataFrame) -> list[dict]:
    m = matched(t).copy()
    m["hod"] = m["hour"].dt.hour
    rows = []
    for hod, g in m.groupby("hod"):
        e = g["error_mw"]
        rows.append(
            {
                "hour": int(hod),
                "lead_h": _f(g["lead_h"].mean()),
                "n": int(len(g)),
                "mae_mw": _f(e.abs().mean()),
                "bias_mw": _f(e.mean()),
                "p10_mw": _f(e.quantile(0.1)),
                "p90_mw": _f(e.quantile(0.9)),
            }
        )
    return rows


def by_day(t: pd.DataFrame) -> list[dict]:
    rows = []
    for day, g in t.groupby("delivery_day"):
        m = matched(g)
        worst = m.loc[m["error_mw"].abs().idxmax()] if not m.empty else None
        rows.append(
            {
                "delivery_day": day.isoformat(),
                "decision_day": g["decision_day"].iloc[0].isoformat()
                if "decision_day" in g
                else None,
                "publish": g["publish"].iloc[0].isoformat(),
                "forecast_mwh": _f(g["forecast_mw"].sum()),
                "actual_mwh": _f(m["actual_mw"].sum()) if not m.empty else None,
                "error_mwh": _f(m["error_mw"].sum()) if not m.empty else None,
                "mae_mw": _f(m["error_mw"].abs().mean()) if not m.empty else None,
                "worst_hour": worst["hour"].isoformat() if worst is not None else None,
                "worst_error_mw": _f(worst["error_mw"]) if worst is not None else None,
                "n_matched": int(len(m)),
            }
        )
    return rows


def worst_day(days: list[dict]) -> dict | None:
    scored = [d for d in days if d["error_mwh"] is not None]
    return max(scored, key=lambda d: abs(d["error_mwh"])) if scored else None


def histogram(t: pd.DataFrame, bins: int = 24) -> dict:
    e = matched(t)["error_mw"].to_numpy()
    if e.size == 0:
        return {"edges": [], "counts": []}
    counts, edges = np.histogram(e, bins=bins)
    return {"edges": [_f(x) for x in edges], "counts": [int(c) for c in counts]}


def by_vintage(v: pd.DataFrame) -> list[dict]:
    rows = []
    for label, g in v.groupby("vintage"):
        e = g["error_mw"]
        rows.append(
            {
                "vintage": label,
                "n": int(len(g)),
                "n_days": int(g["delivery_day"].nunique()),
                "mean_lead_h": _f(g["lead_h"].mean()),
                "mae_mw": _f(e.abs().mean()),
                "rmse_mw": _f(math.sqrt((e**2).mean())),
                "bias_mw": _f(e.mean()),
                "p90_mw": _f(e.quantile(0.9)),
            }
        )
    # Hide one-off ad-hoc runs (e.g. a single 12:25 publication): they are not a schedule the
    # desk can plan around and would distort the comparison with one day of data.
    if rows:
        most = max(r["n_days"] for r in rows)
        rows = [r for r in rows if r["n_days"] >= 0.5 * most]
    return sorted(rows, key=lambda r: r["vintage"])


def by_forecast_level(t: pd.DataFrame, n_bins: int = 3) -> list[dict]:
    """Error binned by forecast level (terciles): is a %-of-forecast margin more sensible?"""
    m = matched(t).copy()
    if len(m) < n_bins * 2:
        return []
    m["bin"] = pd.qcut(m["forecast_mw"], n_bins, labels=False, duplicates="drop")
    rows = []
    for b, g in m.groupby("bin"):
        e = g["error_mw"]
        mf = g["forecast_mw"].mean()
        rows.append(
            {
                "bin": int(b),
                "forecast_min_mw": _f(g["forecast_mw"].min()),
                "forecast_max_mw": _f(g["forecast_mw"].max()),
                "n": int(len(g)),
                "mae_mw": _f(e.abs().mean()),
                "bias_mw": _f(e.mean()),
                "p90_mw": _f(e.quantile(0.9)),
                "p90_pct_of_forecast": _f(100.0 * e.quantile(0.9) / mf) if mf else None,
            }
        )
    return rows


# --------------------------------------------------------------------------- decision-day helpers


def block_averages(hourly: pd.DataFrame, col: str = "forecast_mw") -> dict:
    """Baseload (00-24) and peak (07-19) mean MW, plus daily MWh."""
    s = hourly.dropna(subset=[col])
    if s.empty:
        return {"baseload_mw": None, "peak_mw": None, "daily_mwh": None}
    peak = s[s["hour"].dt.hour.isin(PEAK_HOURS)]
    return {
        "baseload_mw": _f(s[col].mean()),
        "peak_mw": _f(peak[col].mean()) if not peak.empty else None,
        "daily_mwh": _f(s[col].sum()),
    }


def margin_table(hourly: pd.DataFrame, band: dict) -> list[dict]:
    """Per hour: forecast, P10/P50/P90 wind, and extra MW to buy for 90 % cover.

    actual = forecast - error, so the conservative (P90) wind is forecast - P90(error) and
    the extra to buy is max(P90(error), 0).
    """
    rows = []
    p10, p50, p90 = band["p10"], band["p50"], band["p90"]
    for _, r in hourly.iterrows():
        f = r["forecast_mw"]
        rows.append(
            {
                "hour": r["hour"].isoformat(),
                "lead_h": _f(r.get("lead_h")),
                "forecast_mw": _f(f),
                "wind_p90_mw": _f(max(f - p90, 0.0)) if p90 is not None else None,
                "wind_p50_mw": _f(max(f - p50, 0.0)) if p50 is not None else None,
                "wind_p10_mw": _f(max(f - p10, 0.0)) if p10 is not None else None,
                "extra_to_buy_mw": _f(max(p90, 0.0)) if p90 is not None else None,
                "actual_mw": _f(r.get("actual_mw")),
            }
        )
    return rows
