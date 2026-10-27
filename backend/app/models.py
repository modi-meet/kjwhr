"""Pydantic response models - they drive the OpenAPI schema at /docs."""

from __future__ import annotations

from pydantic import BaseModel


class Assumptions(BaseModel):
    decision_window: str
    cutoff_rule: str
    aggregation: str
    error_sign: str
    band: str


class Meta(BaseModel):
    decision_from: str
    decision_to: str
    delivery_from: str
    delivery_to: str
    cutoff_default: str
    cutoff_presets: list[str]
    default_decision_day: str
    vintage_times: list[str]
    snapshot: dict
    assumptions: Assumptions


class HourPoint(BaseModel):
    hour: str
    lead_h: float | None = None
    forecast_mw: float | None = None
    actual_mw: float | None = None
    error_mw: float | None = None


class VintageSeries(BaseModel):
    publish: str
    label: str
    points: list[HourPoint]


class Band(BaseModel):
    p10: float | None
    p50: float | None
    p90: float | None
    source: str


class Blocks(BaseModel):
    baseload_mw: float | None
    peak_mw: float | None
    daily_mwh: float | None


class MarginRow(BaseModel):
    hour: str
    lead_h: float | None
    forecast_mw: float | None
    wind_p90_mw: float | None
    wind_p50_mw: float | None
    wind_p10_mw: float | None
    extra_to_buy_mw: float | None
    actual_mw: float | None


class DecisionResponse(BaseModel):
    decision_day: str
    delivery_day: str
    cutoff: str
    gate_closure: str
    publish: str
    vintage_label: str
    forecast_age_min: int
    fallback_used: bool
    points: list[HourPoint]
    other_vintages: list[VintageSeries]
    band: Band
    blocks_forecast: Blocks
    blocks_actual: Blocks
    conservative_daily_mwh: float | None
    actual_available: bool
    margin_table: list[MarginRow]
    day_summary: dict


class AccuracyResponse(BaseModel):
    from_day: str
    to_day: str
    cutoff: str
    summary: dict
    band: Band
    backtest: dict
    histogram: dict
    by_hour: list[dict]
    by_day: list[dict]
    by_vintage: list[dict]
    by_forecast_level: list[dict]
    worst_day: dict | None
    series: list[HourPoint]
