import { keepPreviousData, useQuery } from '@tanstack/react-query'

export type HourPoint = {
  hour: string
  lead_h: number | null
  forecast_mw: number | null
  actual_mw: number | null
  error_mw: number | null
}
export type Band = { p10: number | null; p50: number | null; p90: number | null; source: string }
export type Blocks = { baseload_mw: number | null; peak_mw: number | null; daily_mwh: number | null }
export type MarginRow = {
  hour: string
  lead_h: number | null
  forecast_mw: number | null
  wind_p90_mw: number | null
  wind_p50_mw: number | null
  wind_p10_mw: number | null
  extra_to_buy_mw: number | null
  actual_mw: number | null
}
export type Summary = {
  n_hours: number
  n_matched: number
  coverage_pct: number | null
  mae_mw: number | null
  rmse_mw: number | null
  bias_mw: number | null
  nmae_pct: number | null
  p90_abs_mw: number | null
  mean_actual_mw: number | null
  mean_forecast_mw: number | null
  p10_mw: number | null
  p50_mw: number | null
  p90_mw: number | null
}
export type Meta = {
  decision_from: string
  decision_to: string
  delivery_from: string
  delivery_to: string
  cutoff_default: string
  cutoff_presets: string[]
  default_decision_day: string
  vintage_times: string[]
  source: { source?: 'live' | 'snapshot'; fetched_at?: string; fallback_reason?: string; sources?: Record<string, string>; [k: string]: unknown }
  assumptions: Record<'decision_window' | 'cutoff_rule' | 'aggregation' | 'error_sign' | 'band', string>
}
export type Decision = {
  decision_day: string
  delivery_day: string
  cutoff: string
  gate_closure: string
  publish: string
  vintage_label: string
  forecast_age_min: number
  fallback_used: boolean
  points: HourPoint[]
  other_vintages: { publish: string; label: string; points: HourPoint[] }[]
  band: Band
  blocks_forecast: Blocks
  blocks_actual: Blocks
  conservative_daily_mwh: number | null
  actual_available: boolean
  margin_table: MarginRow[]
  day_summary: Summary
}
export type DayRow = {
  delivery_day: string
  decision_day: string | null
  publish: string
  forecast_mwh: number | null
  actual_mwh: number | null
  error_mwh: number | null
  mae_mw: number | null
  worst_hour: string | null
  worst_error_mw: number | null
  n_matched: number
}
export type Accuracy = {
  from_day: string
  to_day: string
  cutoff: string
  summary: Summary
  band: Band
  backtest: {
    hours_in_band_pct: number | null
    hours_short_pct: number | null
    days_short: number | null
    days_total: number
  }
  histogram: { edges: number[]; counts: number[] }
  by_hour: { hour: number; lead_h: number; n: number; mae_mw: number; bias_mw: number; p10_mw: number; p90_mw: number }[]
  by_day: DayRow[]
  by_vintage: { vintage: string; n: number; n_days: number; mean_lead_h: number; mae_mw: number; rmse_mw: number; bias_mw: number; p90_mw: number }[]
  by_forecast_level: { bin: number; forecast_min_mw: number; forecast_max_mw: number; n: number; mae_mw: number; bias_mw: number; p90_mw: number; p90_pct_of_forecast: number | null }[]
  worst_day: DayRow | null
  series: HourPoint[]
}

async function get<T>(url: string): Promise<T> {
  const r = await fetch(url)
  if (!r.ok) {
    let detail = r.statusText
    try {
      detail = (await r.json()).detail ?? detail
    } catch {
      /* ignore */
    }
    throw new Error(`${r.status}: ${detail}`)
  }
  return r.json() as Promise<T>
}

export const useMeta = () => useQuery({ queryKey: ['meta'], queryFn: () => get<Meta>('/api/meta') })

export const useDecision = (day: string | null, cutoff: string) =>
  useQuery({
    queryKey: ['decision', day, cutoff],
    queryFn: () => get<Decision>(`/api/decision/${day}?cutoff=${encodeURIComponent(cutoff)}`),
    enabled: !!day,
    placeholderData: keepPreviousData, // keep the last day on screen; the chart animates to the new one
  })

export const useAccuracy = (from: string, to: string, cutoff: string) =>
  useQuery({
    queryKey: ['accuracy', from, to, cutoff],
    queryFn: () =>
      get<Accuracy>(`/api/accuracy?from=${from}&to=${to}&cutoff=${encodeURIComponent(cutoff)}`),
    enabled: !!from && !!to,
    placeholderData: keepPreviousData,
  })
