"""Thin client for the Elexon Insights (BMRS) stream endpoints used by this product.

Only two datasets are in scope:
  * FUELHH  - half-hourly actual generation by fuel type; we keep fuelType == WIND.
  * WINDFOR - hourly national wind forecasts, several publications per day.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

import httpx

BASE_URL = "https://data.elexon.co.uk/bmrs/api/v1"
TIMEOUT = httpx.Timeout(60.0)


def fuelhh_url(settlement_from: date, settlement_to: date, fuel_type: str = "WIND") -> str:
    return (
        f"{BASE_URL}/datasets/FUELHH/stream"
        f"?settlementDateFrom={settlement_from.isoformat()}"
        f"&settlementDateTo={settlement_to.isoformat()}"
        f"&fuelType={fuel_type}"
    )


def windfor_url(publish_from: datetime, publish_to: datetime) -> str:
    fmt = "%Y-%m-%dT%H:%MZ"
    return (
        f"{BASE_URL}/datasets/WINDFOR/stream"
        f"?publishDateTimeFrom={publish_from.strftime(fmt)}"
        f"&publishDateTimeTo={publish_to.strftime(fmt)}"
    )


def _get_json(url: str, client: httpx.Client | None = None) -> list[dict[str, Any]]:
    own = client is None
    client = client or httpx.Client(timeout=TIMEOUT)
    try:
        resp = client.get(url)
        resp.raise_for_status()
        data = resp.json()
    finally:
        if own:
            client.close()
    if not isinstance(data, list):
        raise ValueError(f"Unexpected payload shape from {url}: {type(data).__name__}")
    return data


def fetch_fuelhh(
    settlement_from: date,
    settlement_to: date,
    client: httpx.Client | None = None,
) -> list[dict[str, Any]]:
    """Actual half-hourly wind generation (MW) for the inclusive settlement-date range."""
    rows = _get_json(fuelhh_url(settlement_from, settlement_to), client)
    return [r for r in rows if r.get("fuelType") == "WIND"]


def fetch_windfor(
    publish_from: datetime,
    publish_to: datetime,
    client: httpx.Client | None = None,
) -> list[dict[str, Any]]:
    """All WINDFOR publications whose publishTime falls in the given window."""
    return _get_json(windfor_url(publish_from, publish_to), client)
