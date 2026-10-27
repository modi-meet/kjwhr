import { useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Area, CartesianGrid, ComposedChart, Legend, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { useAccuracy, useDecision, useMeta } from '../api/client'
import { ChartTip } from '../components/ChartTip'
import { MonthStrip } from '../components/MonthStrip'
import { ErrorBox, Loading, Panel, Segmented } from '../components/ui'
import { addDays, dateLabel, downloadCsv, fmt, fmtSigned, gwh, hourLabel, timeLabel } from '../lib/format'
import { chartMotion, useReducedMotion } from '../lib/motion'

const RUN_COLORS = ['var(--run-a)', 'var(--run-b)'] // ordinal: earliest run lightest

export default function DecisionDay() {
  const meta = useMeta()
  const reduced = useReducedMotion()
  const motion = chartMotion(reduced)
  const [params, setParams] = useSearchParams()
  const [cutoff, setCutoff] = useState<string>('')
  const [showVintages, setShowVintages] = useState(false)
  const [showActual, setShowActual] = useState(false)

  const m = meta.data
  const day = params.get('day') ?? m?.default_decision_day ?? null
  useEffect(() => {
    if (m && !cutoff) setCutoff(m.cutoff_default)
  }, [m, cutoff])
  const ct = cutoff || m?.cutoff_default || '09:50'

  const q = useDecision(day, ct)
  const month = useAccuracy(m?.decision_from ?? '', m?.decision_to ?? '', ct)
  const d = q.data

  const setDay = (v: string) => setParams({ day: v })
  const canPrev = !!day && !!m && day > m.decision_from
  const canNext = !!day && !!m && day < m.decision_to
  const shiftDay = (n: number) => {
    if (!day) return
    if ((n < 0 && !canPrev) || (n > 0 && !canNext)) return
    setDay(addDays(day, n))
  }
  useEffect(() => {
    const on = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement | null
      if (t && (t.tagName === 'INPUT' || t.tagName === 'SELECT' || t.tagName === 'TEXTAREA')) return
      if (e.key === 'ArrowLeft') shiftDay(-1)
      if (e.key === 'ArrowRight') shiftDay(1)
    }
    window.addEventListener('keydown', on)
    return () => window.removeEventListener('keydown', on)
  })

  const chart = useMemo(() => {
    if (!d) return []
    const byHour = new Map<string, Record<string, number | string | null | [number, number]>>()
    for (const p of d.points) {
      const f = p.forecast_mw ?? 0
      const lo = d.band.p90 === null ? null : Math.max(f - d.band.p90, 0)
      const hi = d.band.p10 === null ? null : Math.max(f - d.band.p10, 0)
      byHour.set(p.hour, { hour: p.hour, label: hourLabel(p.hour), forecast: p.forecast_mw, actual: p.actual_mw, band: lo !== null && hi !== null ? [lo, hi] : null })
    }
    d.other_vintages.forEach((v, i) => {
      for (const p of v.points) {
        const row = byHour.get(p.hour)
        if (row) row[`v${i}`] = p.forecast_mw
      }
    })
    return [...byHour.values()]
  }, [d])

  const shortHours = useMemo(
    () => (d ? d.margin_table.map((r) => (r.actual_mw === null || r.wind_p90_mw === null ? null : r.actual_mw < r.wind_p90_mw)) : []),
    [d],
  )
  const nShort = shortHours.filter((x) => x === true).length
  const nMatched = shortHours.filter((x) => x !== null).length

  if (meta.isLoading) return <Loading />
  if (meta.error) return <ErrorBox error={meta.error} />
  if (!m) return null

  const p90 = d?.band.p90 ?? null
  const dayErr = d?.day_summary

  return (
    <div className="enter">
      <div className="page-head">
        <div>
          <h1>Decision day · {day ? dateLabel(day) : ''}</h1>
          <p>
            What the desk could see at gate closure on D-1, for delivery day D: the newest forecast published <em>strictly before</em> the cutoff, with the
            January error range around it.
          </p>
        </div>
        <div className="controls">
          <label>
            <span className="eyebrow">Decision day (D-1)</span>
            <span className="btn-row">
              <button className="btn icon" onClick={() => shiftDay(-1)} disabled={!canPrev} aria-label="Previous day" title="Previous day (←)">
                ‹
              </button>
              <input type="date" min={m.decision_from} max={m.decision_to} value={day ?? ''} onChange={(e) => e.target.value && setDay(e.target.value)} />
              <button className="btn icon" onClick={() => shiftDay(1)} disabled={!canNext} aria-label="Next day" title="Next day (→)">
                ›
              </button>
            </span>
          </label>
          <label>
            <span className="eyebrow">Gate closure (UTC)</span>
            <Segmented
              ariaLabel="Gate closure"
              value={ct}
              onChange={setCutoff}
              options={m.cutoff_presets.map((c) => ({ value: c, label: c, hint: c === '09:50' ? '60-min auction' : '30-min auction' }))}
            />
          </label>
        </div>
      </div>

      {month.data ? (
        <Panel title="January at a glance" sub="One cell per delivery day, tinted by how far the decision-time forecast missed. Click a day to open it.">
          <MonthStrip days={month.data.by_day} selected={day} onSelect={setDay} />
          <div className="strip-legend">
            <span>
              <i className="swatch" style={{ background: 'var(--bad)' }} />
              over-forecast (desk short)
            </span>
            <span>
              <i className="swatch" style={{ background: 'var(--good)' }} />
              under-forecast
            </span>
            <span>
              <span className="kbd">←</span> <span className="kbd">→</span> step days
            </span>
          </div>
        </Panel>
      ) : null}

      {q.isLoading ? <Loading /> : null}
      {q.error ? <ErrorBox error={q.error} /> : null}
      {d ? (
        <div className={`fade ${q.isFetching ? 'pending' : ''}`} aria-busy={q.isFetching}>
          <div className="layout">
            <div className="stack">
              <Panel
                title={`Wind forecast for ${dateLabel(d.delivery_day)}`}
                sub={`${d.vintage_label} run, published ${timeLabel(d.publish)}. Band: forecast minus signed P10…P90 error (in-sample).`}
                right={
                  <div className="btn-row">
                    <button className={`btn ${showVintages ? 'active' : ''}`} aria-pressed={showVintages} onClick={() => setShowVintages((v) => !v)} disabled={!d.other_vintages.length}>
                      Earlier runs
                    </button>
                    <button className={`btn ${showActual ? 'active' : ''}`} aria-pressed={showActual} onClick={() => setShowActual((v) => !v)} disabled={!d.actual_available}>
                      Actual
                    </button>
                  </div>
                }
              >
                <ResponsiveContainer width="100%" height={380}>
                  <ComposedChart data={chart} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" vertical={false} />
                    <XAxis dataKey="label" tick={{ fill: 'var(--muted)', fontSize: 12 }} axisLine={false} tickLine={false} interval={2} />
                    <YAxis tick={{ fill: 'var(--muted)', fontSize: 12 }} width={60} tickFormatter={(v) => fmt(v)} axisLine={false} tickLine={false} />
                    <Tooltip content={<ChartTip />} isAnimationActive={false} cursor={{ stroke: 'var(--line-strong)' }} />
                    <Legend wrapperStyle={{ fontSize: 12 }} />
                    <Area type="monotone" dataKey="band" name="P90–P10 range" fill="var(--band)" stroke="none" {...motion} />
                    {showVintages
                      ? d.other_vintages.map((v, i) => (
                          <Line key={v.publish} type="monotone" dataKey={`v${i}`} name={v.label} stroke={RUN_COLORS[i]} strokeDasharray="5 4" dot={false} strokeWidth={1.5} {...motion} />
                        ))
                      : null}
                    <Line type="monotone" dataKey="forecast" name={`Forecast ${d.vintage_label}`} stroke="var(--forecast)" strokeWidth={2.5} dot={false} {...motion} />
                    {showActual ? <Line type="monotone" dataKey="actual" name="Actual (FUELHH)" stroke="var(--actual)" strokeWidth={2} dot={false} {...motion} /> : null}
                  </ComposedChart>
                </ResponsiveContainer>
                {d.actual_available ? (
                  <>
                    <div className="hours" aria-label="Hours covered by a P90 margin">
                      {shortHours.map((s, i) => (
                        <span key={i} className={s === null ? '' : s ? 'short' : 'ok'} title={`${String(i).padStart(2, '0')}:00 ${s === null ? 'no actual' : s ? 'short even with P90 margin' : 'covered'}`} />
                      ))}
                    </div>
                    <p className="legend-note">
                      Hindsight: with a P90 margin the desk would have been short in {nShort} of {nMatched} hours.
                    </p>
                  </>
                ) : (
                  <p className="legend-note">Lead time from this run: {fmt(d.points[0]?.lead_h, 1)} h at 00:00 to {fmt(d.points[d.points.length - 1]?.lead_h, 1)} h at 23:00.</p>
                )}
              </Panel>
            </div>

            <aside className="card">
              <div className="card-head">
                <h2>Buy for {dateLabel(d.delivery_day)}</h2>
                <p className="muted">as of {timeLabel(d.gate_closure)} gate closure</p>
              </div>
              <div className="card-rows">
                <div className="row big">
                  <div className="row-label">
                    Count on
                    <small>forecast − P90 error, whole day</small>
                  </div>
                  <div className="row-value good">{gwh(d.conservative_daily_mwh)}</div>
                </div>
                <div className="row">
                  <div className="row-label">
                    Point forecast
                    <small>{d.vintage_label} run</small>
                  </div>
                  <div className="row-value">{gwh(d.blocks_forecast.daily_mwh)}</div>
                </div>
                <div className="row">
                  <div className="row-label">
                    Extra cover per hour
                    <small>P90 over-forecast</small>
                  </div>
                  <div className="row-value warn">{fmtSigned(p90, 0, ' MW')}</div>
                </div>
                <div className="row">
                  <div className="row-label">Baseload 00–24</div>
                  <div className="row-value">{fmt(d.blocks_forecast.baseload_mw, 0, ' MW')}</div>
                </div>
                <div className="row">
                  <div className="row-label">Peak 07–19</div>
                  <div className="row-value">{fmt(d.blocks_forecast.peak_mw, 0, ' MW')}</div>
                </div>
                {d.actual_available ? (
                  <>
                    <div className="row">
                      <div className="row-label">
                        Actual delivered
                        <small>hindsight</small>
                      </div>
                      <div className="row-value">{gwh(d.blocks_actual.daily_mwh)}</div>
                    </div>
                    <div className="row">
                      <div className="row-label">
                        Mean miss
                        <small>forecast − actual</small>
                      </div>
                      <div className={`row-value ${(dayErr?.bias_mw ?? 0) > (p90 ?? Infinity) ? 'bad' : 'good'}`}>{fmtSigned(dayErr?.bias_mw ?? null, 0, ' MW')}</div>
                    </div>
                  </>
                ) : null}
              </div>
              <div className="card-foot">
                <span className={`badge ${d.forecast_age_min <= 60 ? 'ok' : 'warn'}`}>Run age {d.forecast_age_min} min</span>
                {d.fallback_used ? <span className="badge warn">Fallback run</span> : null}
                <button className="btn" style={{ marginLeft: 'auto' }} onClick={() => downloadCsv(`margin_${d.delivery_day}.csv`, d.margin_table)}>
                  CSV
                </button>
              </div>
            </aside>
          </div>

          <details className="panel" style={{ marginTop: '0.875rem' }}>
            <summary>
              <div>
                <h2>Hourly margin table</h2>
                <p className="muted">Wind to count on at P90 / P50 / P10 and the extra MW per hour. {m.assumptions.error_sign}</p>
              </div>
              <span className="chev">›</span>
            </summary>
            <div className="table-wrap">
              <table className="data">
                <thead>
                  <tr>
                    <th>Hour (UTC)</th>
                    <th>Lead</th>
                    <th>Forecast</th>
                    <th>Wind @P90</th>
                    <th>Wind @P50</th>
                    <th>Wind @P10</th>
                    <th>Extra to buy</th>
                    {d.actual_available ? <th>Actual</th> : null}
                    {d.actual_available ? <th>vs P90</th> : null}
                  </tr>
                </thead>
                <tbody>
                  {d.margin_table.map((r, i) => (
                    <tr key={r.hour}>
                      <td>{hourLabel(r.hour)}</td>
                      <td>{fmt(r.lead_h, 1)} h</td>
                      <td>{fmt(r.forecast_mw)}</td>
                      <td>{fmt(r.wind_p90_mw)}</td>
                      <td>{fmt(r.wind_p50_mw)}</td>
                      <td>{fmt(r.wind_p10_mw)}</td>
                      <td>{fmtSigned(r.extra_to_buy_mw)}</td>
                      {d.actual_available ? <td>{fmt(r.actual_mw)}</td> : null}
                      {d.actual_available ? <td className={shortHours[i] ? 'pos' : 'neg'}>{shortHours[i] ? 'short' : 'covered'}</td> : null}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </details>
        </div>
      ) : null}
    </div>
  )
}
