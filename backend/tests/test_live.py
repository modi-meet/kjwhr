"""The live Elexon path and its fallback, with the network stubbed out."""

import json

import pytest

from backend.app import data, elexon
from backend.app.settings import settings


def _snapshot_rows(name: str) -> list[dict]:
    return json.loads((settings.snapshot_path / name).read_text())


@pytest.fixture
def live(monkeypatch):
    monkeypatch.setattr(settings, "data_source", "live")
    data.reset_cache()
    yield
    data.reset_cache()


def test_live_source_is_used_and_labelled(live, monkeypatch):
    calls = {"fuelhh": 0, "windfor": 0}

    def fake_fuelhh(*_a, **_k):
        calls["fuelhh"] += 1
        return _snapshot_rows("fuelhh_wind.json")

    def fake_windfor(*_a, **_k):
        calls["windfor"] += 1
        return _snapshot_rows("windfor.json")

    monkeypatch.setattr(elexon, "fetch_fuelhh", fake_fuelhh)
    monkeypatch.setattr(elexon, "fetch_windfor", fake_windfor)

    ds = data.get_dataset()
    assert ds.meta["source"] == "live"
    assert ds.meta["windfor"]["publications"] == 256
    assert "data.elexon.co.uk" in ds.meta["sources"]["WINDFOR"]
    # second call is served from the in-memory cache: Elexon is not hit again
    data.get_dataset()
    assert calls == {"fuelhh": 1, "windfor": 1}
    assert len(ds.decision_table(settings.cutoff_time)) == 31 * 24


def test_live_failure_falls_back_to_snapshot(live, monkeypatch):
    def boom(*_a, **_k):
        raise ConnectionError("elexon down")

    monkeypatch.setattr(elexon, "fetch_fuelhh", boom)
    ds = data.get_dataset()
    assert ds.meta["source"] == "snapshot"
    assert "elexon down" in ds.meta["fallback_reason"]
    assert len(ds.decision_table(settings.cutoff_time)) == 31 * 24


def test_failed_refresh_keeps_last_good_live_copy(live, monkeypatch):
    monkeypatch.setattr(settings, "live_cache_seconds", 0)  # every call tries to refresh
    monkeypatch.setattr(
        elexon, "fetch_fuelhh", lambda *_a, **_k: _snapshot_rows("fuelhh_wind.json")
    )
    monkeypatch.setattr(elexon, "fetch_windfor", lambda *_a, **_k: _snapshot_rows("windfor.json"))
    assert data.get_dataset().meta["source"] == "live"

    def boom(*_a, **_k):
        raise TimeoutError("slow")

    monkeypatch.setattr(elexon, "fetch_fuelhh", boom)
    assert data.get_dataset().meta["source"] == "live"  # previous good copy, not the snapshot


def test_live_windows_cover_january():
    (f_from, f_to), (w_from, w_to) = data.live_windows()
    assert (f_from.isoformat(), f_to.isoformat()) == ("2026-01-01", "2026-02-01")
    assert w_from.isoformat().startswith("2025-12-31")
    assert w_to.isoformat().startswith("2026-02-01")
