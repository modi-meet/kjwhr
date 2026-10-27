# Plan: Wind Forecast Decision Support for UK Day-Ahead Procurement

Revision 2 (2026-10-27) - after an independent review. Changes from rev 1 are marked **[rev2]**.

## 1. What the client actually needs (interpretation)

The trading desk buys power for delivery day **D** in the GB day-ahead auction, which closes
on **D-1 at 09:50 UK time** (N2EX / EPEX GB 60-min auction). In January the UK is on UTC, so
no DST handling is needed.

At that moment they need two things:

1. **The forecast they can actually act on** - the newest Elexon wind forecast (WINDFOR)
   published *strictly before* the auction closes, sliced to delivery day D. Later
   publications are irrelevant to the decision even if they are more accurate.
2. **How wrong that forecast tends to be** - so they can size the thermal top-up with a margin
   rather than trusting a point forecast.

**Scope:** "purchase decisions made in January 2026" -> decision days 2026-01-01 .. 2026-01-31,
delivery days 2026-01-02 .. 2026-02-01. Wind only, national level, Elexon only.
**[rev2]** The alternative reading (delivery days in January) is equally plausible, so the
window is config (`DECISION_FROM/TO`) and the chosen reading is printed verbatim in the UI
header and the README "Assumptions" section.

## 2. Data facts (verified against the live API, 2026-10-27)

| Dataset | Resolution | Cadence | Notes |
|---|---|---|---|
| FUELHH (fuelType=WIND) | 30 min, 48 rows/day | ~30 min after each period | `generation` MW, field `startTime` |
| WINDFOR | **60 min**, 73 rows per publication | ~8 publications/day: 02:30, 04:30, 07:30, 09:30, 11:30, 15:30, 18:30, 22:30 UTC | each covers prev day 21:00 -> +3 days 21:00; rows with `startTime < publishTime` are hindcast |

Verified in one request each (no window cap, no duplicate keys):
- FUELHH 2026-01-01..2026-02-01 -> 1536 rows (32 days x 48), unique `startTime`.
- WINDFOR published 2025-12-31..2026-01-31 -> 18 688 rows, 256 publications, 0 duplicate `(publishTime, startTime)`.

Rules **[rev2 - made explicit]**:
- **Hourly alignment:** hour = mean of the HH:00 and HH:30 FUELHH rows, labelled by hour start.
  Both halves required, else the hour is dropped and counted in a coverage %. `generation == null`
  is missing. Unit-test the label (classic resample off-by-one).
- **Vintage selection:** group WINDFOR by exact `publishTime`; decision vintage for day D =
  max `publishTime` **< cutoff** (strict), cutoff default `D-1 09:50 UTC`. Normally the 09:30
  run; if missing, falls back to 07:30 and the UI badge says so.
- **Hindcast filter:** keep rows with `startTime >= publishTime` (only matters for the
  all-vintages / lead-time views; the day-D slice is never affected).
- **Error sign:** `error = forecast - actual`. Positive = over-forecast = desk is short and must
  cover in intraday/balancing. Band and margin use **signed** P10/P50/P90; MAE and "P90 absolute
  error" use absolute values.
- **Dedupe defensively** on `startTime` (FUELHH, keep latest publishTime) and
  `(publishTime, startTime)` (WINDFOR) even though the snapshot has none today.
- Snapshot = **JSON only** (no Parquet / pyarrow, which would threaten the Vercel function size
  limit). Write `snapshot_meta.json` (fetched_at, URLs, row counts, min/max times) next to it.

Fetch URLs:
- `https://data.elexon.co.uk/bmrs/api/v1/datasets/FUELHH/stream?settlementDateFrom=2026-01-01&settlementDateTo=2026-02-01&fuelType=WIND`
- `https://data.elexon.co.uk/bmrs/api/v1/datasets/WINDFOR/stream?publishDateTimeFrom=2025-12-31T00:00Z&publishDateTimeTo=2026-02-01T00:00Z`

## 3. Product: two screens

### Screen A - "Decision Day" (requirement 1)
- Date picker for the **decision day** (D-1). Default **[rev2]** = the January day with the
  largest daily MWh miss (computed from the snapshot), not Jan 1.
- Header: delivery day, auction close 09:50, vintage used (publishTime), and
  **"forecast age at gate closure: 20 min"** badge (replaces the meaningless "freshness" badge).
- Main chart: hourly forecast for day D (decision vintage, bold) with a shaded **signed**
  P10-P90 error band, labelled "band from January 2026 errors (in-sample)".
- Toggle: overlay at most two earlier vintages (02:30, 07:30) - not all eight.
- Toggle: overlay actuals (hindsight view for the pitch).
- Tiles: forecast MWh for the day, **baseload (00-24) and peak (07-19) block averages** [rev2],
  P90 over-forecast in MW, "conservative wind" = forecast - signed P90 error.
- **Hourly margin table** [rev2 - folded in from the old third screen]: hour, lead time,
  forecast, P10 / P50 / P90 wind, extra MW to buy for 90 % cover. CSV download (client-side Blob).

### Screen B - "Forecast Accuracy" (requirement 2)
- Period selector (January default) and cutoff preset (09:50 default; **[rev2]** optional
  15:30 preset for the EPEX GB half-hourly auction, which picks the 11:30 run).
- KPI tiles: MAE, RMSE, mean bias, nMAE (% of mean actual), **P90 over-forecast (headline)**,
  **band coverage** = % of hours actual fell inside P10-P90 and "a P90 margin would still have
  left you short on N of 31 days" [rev2].
- Charts, in priority order [rev2]:
  1. Error histogram with signed P10/P50/P90 markers (the "how big a margin" answer).
  2. Error by hour of day, x-axis labelled "00:00 / +14.5 h" so diurnal and lead-time effects
     are both visible.
  3. Forecast vs actual hourly time series for the month.
  4. MAE per vintage (02:30 .. 09:30 .. 22:30) - proves why the cutoff matters.
  5. (if time) Error by forecast level (terciles) - replaces the scatter; shows that a
     %-of-forecast margin is more actionable than a flat MW one.
- Daily table: date, forecast MWh, actual MWh, signed error, worst hour; CSV download.
- Worst-day story card for the pitch [rev2]: date, miss in MW, what a P90 margin would have done.
- Cut list item: **persistence skill score** (naive forecast = D-1 same-hour actuals, FUELHH
  only, no new data). Nice proof the forecast adds value; only if steps 1-9 land on time.

Dropped **[rev2]**: separate "Procurement margin" screen, scatter chart, MAPE (near-zero actuals
on calm hours make it meaningless; one README sentence says so).

## 4. Architecture

```
repo/
  README.md                 # layout, run (Docker and without), deployed link, Assumptions, AI-tools disclosure
  requirements.txt          # root, so the Vercel Python function finds it   [rev2]
  vercel.json               # build web/, rewrite /api/* -> api/index, SPA fallback   [rev2]
  Dockerfile                # single multi-stage image: node builds web/, python serves it + /api   [rev2]
  docker-compose.yml        # optional dev convenience: Vite dev server proxying to the API
  .github/workflows/ci.yml  # pytest, ruff, npm ci && tsc --noEmit && vite build   [rev2]
  api/index.py              # thin Vercel shim: `from backend.app.main import app`   [rev2]
  backend/
    app/main.py             # FastAPI routes, Pydantic response models
    app/settings.py         # pydantic-settings: CUTOFF_TIME, DECISION_FROM/TO, SNAPSHOT_PATH
    app/elexon.py           # real, tested client for FUELHH / WINDFOR streams
    app/data.py             # snapshot load, dedupe, hourly alignment, vintage selection, hindcast filter
    app/metrics.py          # signed/abs errors, percentiles, coverage, by hour / vintage / day
    app/snapshot/           # jan2026_fuelhh.json, jan2026_windfor.json, snapshot_meta.json
    scripts/fetch_snapshot.py   # --refresh re-pulls from Elexon
    tests/                  # alignment label, vintage cutoff (strict), hindcast, metrics, snapshot invariants
  web/                      # Vite + React + TS, Recharts, TanStack Query, plain CSS (no UI kit)
    src/pages/DecisionDay.tsx
    src/pages/Accuracy.tsx
    src/api/client.ts
    src/components/charts/
```

API (read-only JSON, Pydantic models -> OpenAPI for the tech-lead walkthrough):
- `GET /api/meta` - decision-day range, cutoff presets, vintages present, snapshot meta
- `GET /api/decision/{decision_date}?cutoff=09:50` - delivery day, chosen vintage + age, hourly forecast, selected other vintages, actuals if available, signed band, block aggregates
- `GET /api/accuracy?from=&to=&cutoff=` - KPIs, histogram, by-hour, by-vintage, by-day, coverage, worst day

Decisions:
- **FastAPI + pandas, decided now** [rev2]. pandas+numpy fit the Vercel 250 MB limit and cold
  start is ~1-2 s. No "pandas optional" fallback path; verify on the first deploy instead.
- **Committed JSON snapshot**: the month is historical and fixed; removes Elexon availability
  from the demo; deterministic tests. `--refresh` keeps the live path demonstrable.
- **Single container is the primary Docker artifact** [rev2]: one `docker run` for the reviewer.
  Compose is dev-only. README states honestly that Vercel does not run the image.
- **Deploy: Vercel** (static `web/dist` + Python function). Deployment protection off,
  incognito-checked. **Fallback: Heroku container deploy** (`heroku container:push web`, Eco
  dyno, ~15 min switch) if Vercel's function packaging fights back.

## 5. Build order (16 h) **[rev2 - reordered, deploy early]**

| # | Step | Est. | Done when |
|---|---|---|---|
| 1 | Domain + data exploration (done) | 0.5 h | rules in section 2 written down |
| 2 | Fetch script, snapshot + meta, dedupe | 1.0 h | both JSON files + `snapshot_meta.json` committed |
| 3 | Data + metrics module with tests | 2.5 h | alignment label, strict cutoff, hindcast, signed percentiles, coverage; pytest green |
| 4 | FastAPI routes + Pydantic models + settings | 1.0 h | three endpoints; `/docs` renders |
| 5 | **Skeleton deploy to Vercel** (placeholder page + `/api/meta`) + single-container Dockerfile | 1.5 h | public URL works in incognito; `docker run` works; snapshot present in the function |
| 6 | Frontend scaffold, routing, API client, CI workflow | 1.0 h | both pages load real data; CI green |
| 7 | Decision Day page incl. margin table | 2.5 h | chart, band, vintage/actual toggles, tiles, table, CSV |
| 8 | Accuracy page | 3.0 h | KPIs, 4 charts, daily table, worst-day card, CSV |
| 9 | README (layout, run, link, Assumptions, AI-tools disclosure) | 1.0 h | reviewer can run it from README alone |
| 10 | Video: ~4 min client pitch + ~4 min tech walkthrough, recorded separately | 2.0 h | unlisted YouTube link, < 10 min total |
| - | Buffer | 0.0 h | absorbed by the cut list |

Cut list, in order: persistence skill score, error-by-forecast-level chart, vintage overlay,
worst-day card, CSV export. Never cut: strict decision-vintage logic, signed band, KPIs,
error-by-hour, README Assumptions, video.

## 6. Risks and handling

- **Cutoff assumption** (09:50 strict) -> shown in UI and README; query param; second preset.
- **January interpretation** -> config + stated verbatim in UI/README.
- **Hourly vs half-hourly** -> mean of both halves, hour-start label, unit-tested.
- **Hindcast rows** -> filtered, tested.
- **Missing / null periods** -> dropped, coverage % shown.
- **In-sample band** -> labelled as such in UI and README; leave-one-day-out only if time.
- **Elexon downtime** -> snapshot committed; no runtime dependency.
- **Vercel packaging** (api/ convention, snapshot not bundled, function size) -> shim layout,
  read snapshot relative to `__file__`, `functions.includeFiles` if needed, verified at step 5;
  Heroku container as fallback.
- **Time overrun** -> cut list; video recorded against whatever is deployed.

## 7. README "Assumptions" section (must exist)

Cutoff and strict comparison; January-decision-day interpretation; hourly aggregation rule;
error sign convention; in-sample band; both series are transmission-connected (BM-unit) wind,
embedded wind excluded, so they are consistent; why no MAPE; snapshot date and how to refresh.
Plus: file tree, run with and without Docker, deployed link, and a specific AI-tools disclosure
(which tools, for what, how the output was verified).

## 8. Video story

- **Client (~4 min)**: the problem (buy tomorrow's gap today); Decision Day for the worst
  January day; Accuracy: "the 09:30 forecast is off by X MW on average, P90 over-forecast is
  Y MW, a Y MW margin would have covered you on N of 31 days"; end on the margin table.
- **Tech lead (~4 min)**: open the deployed URL in incognito; repo tour; data flow
  (Elexon -> snapshot -> alignment -> metrics -> API -> React); the strict-cutoff rule and its
  test; refresh path; Docker + Vercel + CI; what AI tools did and how it was verified.

## 9. Review suggestions deliberately not taken

- `desk_lead_minutes` parameter: over-engineering; the "forecast age" badge conveys the same thing.
- Day-by-day chunked fetching: verified unnecessary (month-long requests return complete data);
  kept only the dedupe and meta file.
- Fetching WINDFOR from Dec 30 for D-2 vintages: lead-time chart works with D-1 vintages alone.
- Leave-one-day-out band: optional, not planned.
