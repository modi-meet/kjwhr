from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)


def test_meta():
    r = client.get("/api/meta")
    assert r.status_code == 200
    m = r.json()
    assert m["cutoff_default"] == "09:50"
    assert m["delivery_from"] == "2026-01-02" and m["delivery_to"] == "2026-02-01"
    assert "09:30" in m["vintage_times"]
    assert m["decision_from"] <= m["default_decision_day"] <= m["decision_to"]


def test_decision_default_cutoff_picks_0930_and_24_points():
    r = client.get("/api/decision/2026-01-10")
    assert r.status_code == 200
    d = r.json()
    assert d["delivery_day"] == "2026-01-11"
    assert d["publish"].endswith("T09:30:00+00:00")
    assert d["forecast_age_min"] == 20
    assert len(d["points"]) == 24 and len(d["margin_table"]) == 24
    assert d["actual_available"] is True
    assert d["band"]["p10"] < d["band"]["p90"]
    assert 1 <= len(d["other_vintages"]) <= 2


def test_decision_alternative_cutoff():
    d = client.get("/api/decision/2026-01-10?cutoff=15:30").json()
    assert d["publish"].endswith("T11:30:00+00:00")


def test_decision_out_of_window_is_404():
    assert client.get("/api/decision/2025-12-01").status_code == 404
    assert client.get("/api/decision/not-a-date").status_code == 400


def test_accuracy_whole_month():
    r = client.get("/api/accuracy")
    assert r.status_code == 200
    a = r.json()
    assert a["summary"]["n_hours"] == 31 * 24
    assert a["summary"]["mae_mw"] > 0
    assert len(a["by_hour"]) == 24 and len(a["by_day"]) == 31
    assert any(v["vintage"] == "D-1 09:30" for v in a["by_vintage"])
    assert a["backtest"]["days_total"] == 31
    assert a["worst_day"]["delivery_day"]


def test_accuracy_sub_window():
    a = client.get("/api/accuracy?from=2026-01-10&to=2026-01-12").json()
    assert len(a["by_day"]) == 3


def test_docs_and_schema_live_under_api_prefix():
    # /api/* is what Vercel routes to the function and what the UI links to.
    assert client.get("/api/openapi.json").headers["content-type"].startswith("application/json")
    assert "swagger" in client.get("/api/docs").text.lower()
