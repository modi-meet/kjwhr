"""Runtime configuration. Every value documents an assumption listed in README.md."""

from __future__ import annotations

from datetime import date, time
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # GB day-ahead auction gate closure (N2EX / EPEX 60-min), UK local time. January == UTC.
    # Vintage selection uses a strict "<" comparison against this time on the decision day.
    cutoff_time: time = time(9, 50)
    # Alternative preset exposed in the UI: EPEX GB half-hourly day-ahead auction.
    cutoff_presets: dict[str, time] = {"09:50": time(9, 50), "15:30": time(15, 30)}

    # "Purchase decisions made in January 2026" -> decision days (D-1) 1..31 Jan,
    # delivery days (D) 2 Jan .. 1 Feb.
    decision_from: date = date(2026, 1, 1)
    decision_to: date = date(2026, 1, 31)

    snapshot_dir: Path = Path("backend/app/snapshot")

    @property
    def snapshot_path(self) -> Path:
        p = self.snapshot_dir
        if not p.is_absolute():
            # Resolve relative to the repo root so it works from any cwd and inside Vercel.
            p = REPO_ROOT / p
        return p


settings = Settings()
