# Wind Day-Ahead Desk

Decision support for a GB electricity-procurement desk: **what national wind forecast could they act on at
day-ahead gate closure, and how wrong does that forecast tend to be?**

Data: Elexon Insights `FUELHH` (actual generation, fuelType `WIND`) and `WINDFOR` (national wind forecast).
Scope: purchase decisions made in January 2026. React front-end, Python (FastAPI) back-end, Docker, Vercel.

**Live app:** https://kjwhr-sepia.vercel.app · **API docs:** https://kjwhr-sepia.vercel.app/api/docs

---

## What it does

| Screen | Requirement it serves | What the desk sees |
|---|---|---|
| **Decision day** | 1 - the latest forecast available when the decision is made | Pick a decision day (D-1). The app selects the newest `WINDFOR` publication *strictly before* gate closure (default 09:50 UTC), shows the hourly forecast for delivery day D with a P10-P90 error band, block averages (baseload, peak 07-19), the forecast's age at gate closure, optional earlier-vintage and actual overlays, and an hourly **procurement margin table** (wind to count on at P90/P50/P10 and the extra MW to buy for 90 % cover). |
| **Forecast accuracy** | 2 - quantify the forecast error | Across every delivery day in the window: P90 over-forecast (the headline margin), bias, MAE, RMSE, nMAE, band coverage and "days still short with a P90 margin"; error histogram with signed percentiles; error by hour of day (with lead time); forecast vs actual for the month; MAE per publication time (does waiting for a later run help?); error by forecast level; a worst-day story card; daily scorecard with CSV export. |

Headline January 2026 findings (decision vintage = 09:30 run on D-1):

| Metric | Value |
|---|---|
| Mean bias (forecast - actual) | **+1,730 MW** over-forecast |
| MAE / nMAE | 2,013 MW / 17.8 % of mean actual |
| Signed P10 / P50 / P90 error | -489 / +1,560 / **+4,144 MW** |
| Hours inside the P10-P90 band | 80 % (in-sample) |
| Days still short with a flat P90 margin | 3 of 31 |
| Worst day | 28 Jan: forecast 267 GWh, actual 138 GWh |

The persistent positive bias is the most useful single fact for the desk: the published forecast is
systematically above metered transmission-connected wind, so a margin is needed even on an "average" day.
(Likely contributors: curtailment of constrained Scottish wind and forecast scope; out of scope to prove here.)

## Repository layout

```
.
├── README.md
├── PLAN.md                     # build plan incl. review revisions (design rationale)
├── requirements.txt            # runtime Python deps (root so the Vercel function finds it)
├── requirements-dev.txt        # + pytest, ruff
├── pyproject.toml              # dependencies (Vercel installs from here), pytest / ruff config
├── vercel.json                 # build web/, bundle it into the Python function
├── Dockerfile                  # single multi-stage image: Node builds web/, Python serves it + /api
├── docker-compose.yml          # optional dev convenience (hot-reload API + Vite dev server)
├── .github/workflows/ci.yml    # ruff + pytest, tsc + vite build, docker build + smoke test
├── api/
│   └── index.py                # Vercel serverless entrypoint: imports the FastAPI app
├── backend/
│   ├── app/
│   │   ├── main.py             # FastAPI routes: /api/meta, /api/decision/{day}, /api/accuracy
│   │   ├── models.py           # Pydantic response models (drive /api/docs)
│   │   ├── settings.py         # cutoff, decision window, data source + cache (env-overridable)
│   │   ├── elexon.py           # client for the FUELHH / WINDFOR stream endpoints
│   │   ├── data.py             # live Elexon load + cache + fallback, dedupe, hourly alignment, vintage selection, hindcast filter
│   │   ├── metrics.py          # signed/abs errors, percentiles, coverage, breakdowns, margin table
│   │   └── snapshot/           # committed January 2026 fallback copy + snapshot_meta.json
│   ├── scripts/fetch_snapshot.py   # (re)build the fallback snapshot from Elexon  (--refresh)
│   └── tests/                  # pytest: alignment, cutoff rule, hindcast, metrics, API, snapshot invariants
└── web/                        # Vite + React 19 + TypeScript
    └── src/
        ├── api/client.ts       # typed fetchers + TanStack Query hooks
        ├── pages/DecisionDay.tsx
        ├── pages/Accuracy.tsx
        ├── components/         # Panel, Kpi, Segmented control, chart tooltip
        └── lib/                # number/date formatting, CSV download, reduced-motion hook
```

## How to run

### Option A - Docker (one container, what reviewers should use)

```bash
docker build -t wind-da .
docker run --rm -p 8000:8000 wind-da
```

Open <http://localhost:8000>. The API docs are at <http://localhost:8000/api/docs>.

### Option B - local dev (hot reload)

```bash
python3.12 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/uvicorn backend.app.main:app --reload --port 8000
```

```bash
cd web && npm ci && npm run dev        # http://localhost:5173, proxies /api to :8000
```

Or `docker compose up` for the same two processes in containers.

### Tests and lint

```bash
.venv/bin/pytest -q && .venv/bin/ruff check backend
cd web && npx tsc --noEmit && npm run build
```

### Data source: live API, snapshot as fallback

The backend calls the Elexon Insights API (`FUELHH` and `WINDFOR`) on the first request, keeps the result in
memory for an hour (`LIVE_CACHE_SECONDS`), and refreshes it afterwards. The cold first request takes about
2.5 s; later ones are served from memory. If Elexon is unreachable, it serves the committed snapshot instead and
the UI footer says so. `DATA_SOURCE=snapshot` forces offline mode (the tests use it).

```bash
.venv/bin/python backend/scripts/fetch_snapshot.py --refresh
```

Re-pulls both datasets for the configured window from Elexon, dedupes, and rewrites
`backend/app/snapshot/*.json` and `snapshot_meta.json`. The snapshot is only the fallback copy (see above).

### Deploying to Vercel

One Vercel project. Vercel detects the FastAPI app (`api/index.py`, which imports `backend/`) and installs
its dependencies from `pyproject.toml` (keep it in sync with `requirements.txt`, which the Docker image uses).
`vercel.json` builds the React app (`web/dist`) and bundles it into the function, so the same app serves the
UI and `/api/*`. No environment variables are needed.

```bash
npx vercel login
npx vercel deploy --prod
```

Turn **off** Deployment Protection in the project settings so the link opens in incognito. Vercel does not run
the Docker image; the image is the local/reviewer artifact and would deploy unchanged to Heroku
(`heroku container:push web`) if needed.

## Assumptions (the ones a reviewer will ask about)

1. **Decision time.** GB day-ahead 60-min auctions (N2EX / EPEX) close at 09:50 UK local on D-1. January
   UK time == UTC, so no DST handling. A second preset (15:30, the half-hourly auction) is in the UI.
2. **"Latest forecast available" = strict.** Decision vintage = the `WINDFOR` publication with the largest
   `publishTime` **strictly before** the cutoff. A run stamped exactly at the cutoff is not usable.
   Normally this is the 09:30 run (age 20 min at gate closure); if it is missing the rule falls back to
   the previous run and the UI badge says so.
3. **"Purchase decisions made in January 2026"** = decision days 1-31 Jan (D-1), delivery days
   2 Jan - 1 Feb (D). The alternative reading (delivery days in January) is a config change
   (`DECISION_FROM/TO`); the chosen reading is printed in the UI footer.
4. **Hourly alignment.** `FUELHH` is half-hourly, `WINDFOR` hourly. An hour of actuals is the mean of the
   HH:00 and HH:30 rows, labelled by hour start (energy-consistent). Hours with a missing or null half are
   dropped and reported as coverage; January 2026 has 100 % coverage.
5. **Hindcast rows.** Each `WINDFOR` publication also carries hours already in the past; rows with
   `startTime < publishTime` are discarded (only matters for the all-vintages view).
6. **Error sign.** `error = forecast - actual`. Positive = over-forecast = the desk would be short.
   P10/P50/P90 are signed percentiles of hourly error; MAE and "P90 absolute" use absolute values.
7. **In-sample band.** The P10-P90 band on the Decision Day screen is computed from the whole window,
   including the day shown. With one month of data there is no clean hold-out; the UI labels it in-sample.
8. **No MAPE.** Calm hours with near-zero actual generation make MAPE meaningless; nMAE is normalised by
   mean actual instead (no installed-capacity data in scope).
9. **What the series are.** Both `FUELHH` WIND and `WINDFOR` describe transmission-connected (BM-unit)
   wind; embedded wind is excluded from both, so they are comparable.
10. **Live API, with a saved fallback.** Data is fetched from the Elexon API at runtime and cached in
    memory. A January 2026 snapshot (about 2 MB of JSON) is committed only as a fallback so the demo still
    works if Elexon is down, and so the tests are deterministic and offline.
11. **One-off publications are hidden from the vintage comparison.** A single ad-hoc 12:25 run exists in
    January; it is not a schedule the desk can plan around, so runs seen on fewer than half the days are
    dropped from the "does waiting help?" chart.

## Design notes for the reviewer

- **Data flow:** Elexon API (snapshot fallback) -> `data.py` (normalise, dedupe, hourly
  mean, vintage selection) -> `metrics.py` (pure functions over a long "decision table") -> `main.py`
  (Pydantic-typed JSON) -> React (TanStack Query + Recharts).
- **Everything is a function of (window, cutoff).** Both endpoints take `cutoff=HH:MM`, so the desk can
  see how the picture changes if they decide later; nothing is hard-coded to 09:30.
- **Tests** cover the things that are easy to get silently wrong: the hour label after resampling, the
  strict cutoff comparison, the hindcast filter, the sign convention, the band backtest, and invariants
  of the committed snapshot (every decision day has a usable vintage, 24 hours per delivery day).
- **Page composition.** Each screen answers one question first. Decision Day: a clickable month strip
  for wayfinding, the forecast chart beside a "buy for tomorrow" card, and the hourly table one level
  deeper. Accuracy: the answer (extra cover to buy) beside the error distribution, one explorer panel
  that switches between by-hour / by-run-time / by-wind-level, and a month view (strip + series + table).
- **Type and colour.** Google Fonts: Inter for UI and all figures (tabular numerals), Sora for headings
  and hero numbers. Colour is assigned by job: one accent for interaction; data series in a fixed
  categorical order (blue = forecast / MAE, orange = actual / bias, aqua = the P90 threshold); earlier
  forecast runs are ordinal, so they take lighter steps of the same blue; status colours (good / short /
  warning) are reserved for state and always paired with a label. The palette was checked with a
  colour-vision-deficiency and contrast validator and every text token
  clears 4.5:1 on its surface.
- **UI conventions (Apple HIG-inspired, plain CSS):** grainy canvas background (SVG noise over a soft glow)
  so panels read as surfaces; size-specific tracking and tabular
  numerals; a single light theme (no dark mode) defined as tokens that charts inherit; translucent
  sticky chrome with a scroll-edge fade; press feedback on pointer-down; segmented controls for one-of-N
  choices; keyboard ←/→ to step days; when a new day loads the previous chart stays and animates to the
  new values rather than flashing empty; `prefers-reduced-motion`, `-transparency` and `-contrast` honoured.
- **Cut for time (16 h budget):** persistence skill score, leave-one-day-out band, frontend unit tests
  (CI runs `tsc` and `vite build` instead).

## AI tools disclosure

This project was built with **Claude Code (Anthropic)** as a pair programmer, for: the build plan and an
independent review of it, scaffolding, writing the data/metrics/API modules and tests, the React pages,
Docker/Vercel/CI configuration and this README. All domain assumptions (auction timing, hourly alignment,
sign convention, interpretation of the January window) were verified by me against the live Elexon API
and the challenge brief, and every generated module is covered by the test suite in `backend/tests`
(31 tests) plus a manual browser check of both screens against the real January data.
