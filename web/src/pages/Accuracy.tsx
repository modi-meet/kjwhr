import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Bar, BarChart, CartesianGrid, ComposedChart, Legend, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { useAccuracy, useMeta } from '../api/client'
import { ChartTip } from '../components/ChartTip'
import { MonthStrip } from '../components/MonthStrip'
import { ErrorBox, Loading, Panel, Segmented } from '../components/ui'
import { dateLabel, downloadCsv, fmt, fmtSigned, gwh, hourLabel } from '../lib/format'
import { chartMotion, useReducedMotion } from '../lib/motion'

type View = 'hour' | 'vintage' | 'level'

export default function Accuracy() {
  const meta = useMeta()
  const navigate = useNavigate()
  const reduced = useReducedMotion()
  const motion = chartMotion(reduced)
  const [from, setFrom] = useState('')
  const [to, setTo] = useState('')
  const [cutoff, setCutoff] = useState('')
  const [view, setView] = useState<View>('hour')
  useEffect(() => {
    if (meta.data && !from) {
      setFrom(meta.data.decision_from)
      setTo(meta.data.decision_to)
      setCutoff(meta.data.cutoff_default)
    }
  }, [meta.data, from])

  const q = useAccuracy(from, to, cutoff)
  const a = q.data

  const hist = useMemo(
    () => (a ? a.histogram.counts.map((c, i) => ({ label: fmtSigned(a.histogram.edges[i] / 1000, 1), count: c })) : []),
    [a],
  )
  const byHour = useMemo(() => a?.by_hour ?? [], [a])
  const series = useMemo(
    () => a?.series.map((p) => ({ label: `${dateLabel(p.hour.slice(0, 10))} ${hourLabel(p.hour)}`, forecast: p.forecast_mw, actual: p.actual_mw })) ?? [],
    [a],
  )
  const byLevel = useMemo(
    () => a?.by_forecast_level.map((b) => ({ ...b, label: `${fmt(b.forecast_min_mw / 1000, 1)}–${fmt(b.forecast_max_mw / 1000, 1)} GW` })) ?? [],
    [a],
  )

  if (meta.isLoading) return <Loading />
  if (meta.error) return <ErrorBox error={meta.error} />
  const m = meta.data!
  const s = a?.summary
  const bt = a?.backtest
  const w = a?.worst_day

  const axis = { tick: { fill: 'var(--muted)', fontSize: 11 }, axisLine: false, tickLine: false } as const

  return (
    <div className="enter">
      <div className="page-head">
        <div>
          <h1>Forecast accuracy</h1>
          <p>How wrong the decision-time forecast was, hour by hour, across every delivery day in the window. Error = forecast − actual: positive means the desk would have been short.</p>
        </div>
        <div className="controls">
          <label>
            <span className="eyebrow">Decision days from</span>
            <input type="date" min={m.decision_from} max={m.decision_to} value={from} onChange={(e) => e.target.value && setFrom(e.target.value)} />
          </label>
          <label>
            <span className="eyebrow">to</span>
            <input type="date" min={m.decision_from} max={m.decision_to} value={to} onChange={(e) => e.target.value && setTo(e.target.value)} />
          </label>
          <label>
            <span className="eyebrow">Gate closure (UTC)</span>
            <Segmented ariaLabel="Gate closure" value={cutoff || m.cutoff_default} onChange={setCutoff} options={m.cutoff_presets.map((c) => ({ value: c, label: c }))} />
          </label>
        </div>
      </div>

      {q.isLoading ? <Loading /> : null}
      {q.error ? <ErrorBox error={q.error} /> : null}
      {a && s && bt ? (
        <div className={`fade ${q.isFetching ? 'pending' : ''}`} aria-busy={q.isFetching}>
          <div className="hero">
            <div className="answer">
              <div className="eyebrow">Extra cover to buy, per hour</div>
              <div className="answer-value">{fmtSigned(s.p90_mw, 0, ' MW')}</div>
              <p className="answer-lead">
                The {a.cutoff === '09:50' ? '09:30' : 'decision-time'} run over-forecast wind by <b>{fmtSigned(s.bias_mw, 0, ' MW')}</b> on a typical hour. Budgeting{' '}
                <b>{fmt(s.p90_mw, 0, ' MW')}</b> of extra cover would have been enough in <b>9 hours out of 10</b>, and the whole day would still have fallen short on{' '}
                <b>
                  {bt.days_short} of {bt.days_total} days
                </b>
                .
              </p>
              <div className="stats">
                <div className="stat">
                  <div className="eyebrow">Mean bias</div>
                  <div className={`stat-value ${(s.bias_mw ?? 0) > 0 ? 'bad' : 'good'}`}>{fmtSigned(s.bias_mw, 0, ' MW')}</div>
                </div>
                <div className="stat">
                  <div className="eyebrow">MAE</div>
                  <div className="stat-value">{fmt(s.mae_mw, 0, ' MW')}</div>
                </div>
                <div className="stat">
                  <div className="eyebrow">nMAE</div>
                  <div className="stat-value">{fmt(s.nmae_pct, 1, ' %')}</div>
                </div>
                <div className="stat">
                  <div className="eyebrow">RMSE</div>
                  <div className="stat-value">{fmt(s.rmse_mw, 0, ' MW')}</div>
                </div>
                <div className="stat">
                  <div className="eyebrow">In P10–P90</div>
                  <div className="stat-value">{fmt(bt.hours_in_band_pct, 0, ' %')}</div>
                </div>
                <div className="stat">
                  <div className="eyebrow">Days short</div>
                  <div className={`stat-value ${(bt.days_short ?? 0) > 3 ? 'bad' : 'good'}`}>
                    {bt.days_short} / {bt.days_total}
                  </div>
                </div>
              </div>
              {w ? (
                <p className="muted">
                  Worst day {dateLabel(w.delivery_day)}: expected {gwh(w.forecast_mwh)}, got {gwh(w.actual_mwh)}.{' '}
                  <Link to={`/decision?day=${w.decision_day}`}>Open →</Link>
                </p>
              ) : null}
            </div>

            <Panel title="Where the misses fall" sub="Hourly forecast − actual, GW. Dashed markers: signed P10 / P50 / P90 of the window.">
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={hist} margin={{ top: 18, right: 12, bottom: 0, left: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="label" {...axis} interval={3} />
                  <YAxis {...axis} width={40} />
                  <Tooltip content={<ChartTip unit=" h" title={(l) => `bin from ${l} GW`} />} isAnimationActive={false} cursor={{ fill: 'var(--fill)' }} />
                  <Bar dataKey="count" name="hours" fill="var(--forecast)" radius={[3, 3, 0, 0]} {...motion} />
                  {(
                    [
                      ['P10', a.band.p10],
                      ['P50', a.band.p50],
                      ['P90', a.band.p90],
                    ] as const
                  ).map(([k, v]) => {
                    if (v === null) return null
                    const idx = hist.findIndex((_h, i) => v < (a.histogram.edges[i + 1] ?? Infinity))
                    return idx < 0 ? null : (
                      <ReferenceLine key={k} x={hist[idx].label} stroke="var(--warn)" strokeDasharray="4 3" label={{ value: `${k} ${fmtSigned(v)}`, fill: 'var(--warn)', fontSize: 11, position: 'top' }} />
                    )
                  })}
                </BarChart>
              </ResponsiveContainer>
            </Panel>
          </div>

          <Panel
            title="When and why it misses"
            sub={
              view === 'hour'
                ? 'By delivery hour. Bars: MAE. Lines: bias and P90. Lead time from the decision run grows through the day.'
                : view === 'vintage'
                  ? 'By publication time on D-1, same delivery days. Only runs before gate closure are actionable; later ones are shown for context.'
                  : 'By forecast level (terciles). A flat MW margin over-covers calm days and under-covers windy ones.'
            }
            right={
              <Segmented<View>
                ariaLabel="Breakdown"
                value={view}
                onChange={setView}
                options={[
                  { value: 'hour', label: 'By hour' },
                  { value: 'vintage', label: 'By run time' },
                  { value: 'level', label: 'By wind level' },
                ]}
              />
            }
          >
            <ResponsiveContainer width="100%" height={280}>
              {view === 'hour' ? (
                <ComposedChart data={byHour} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="hour" {...axis} interval={1} tickFormatter={(v: number) => `${String(v).padStart(2, '0')}h`} />
                  <YAxis {...axis} width={52} tickFormatter={(v) => fmt(v)} />
                  <Tooltip
                    isAnimationActive={false}
                    cursor={{ fill: 'var(--fill)' }}
                    content={<ChartTip title={(l, p) => `${String(l).padStart(2, '0')}:00 · lead +${fmt((p[0] as unknown as { payload: { lead_h: number } }).payload.lead_h, 1)} h`} />}
                  />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  <Bar dataKey="mae_mw" name="MAE" fill="var(--forecast)" radius={[3, 3, 0, 0]} {...motion} />
                  <Line type="monotone" dataKey="bias_mw" name="Bias" stroke="var(--warn)" dot={false} strokeWidth={2} {...motion} />
                  <Line type="monotone" dataKey="p90_mw" name="P90" stroke="var(--p90)" dot={false} strokeDasharray="4 3" {...motion} />
                </ComposedChart>
              ) : view === 'vintage' ? (
                <BarChart data={a.by_vintage} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="vintage" {...axis} tickFormatter={(v: string) => v.replace('D-1 ', '')} />
                  <YAxis {...axis} width={52} tickFormatter={(v) => fmt(v)} />
                  <Tooltip isAnimationActive={false} cursor={{ fill: 'var(--fill)' }} content={<ChartTip title={(l, p) => `${l} · ${(p[0] as unknown as { payload: { n_days: number } }).payload.n_days} days`} />} />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  <ReferenceLine x={`D-1 ${a.cutoff === '09:50' ? '09:30' : '11:30'}`} stroke="var(--accent)" strokeDasharray="4 3" label={{ value: 'decision run', fill: 'var(--accent)', fontSize: 11, position: 'top' }} />
                  <Bar dataKey="mae_mw" name="MAE" fill="var(--forecast)" radius={[3, 3, 0, 0]} {...motion} />
                  <Bar dataKey="bias_mw" name="Bias" fill="var(--warn)" radius={[3, 3, 0, 0]} {...motion} />
                </BarChart>
              ) : (
                <BarChart data={byLevel} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="label" {...axis} />
                  <YAxis {...axis} width={52} tickFormatter={(v) => fmt(v)} />
                  <Tooltip isAnimationActive={false} cursor={{ fill: 'var(--fill)' }} content={<ChartTip />} />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  <Bar dataKey="mae_mw" name="MAE" fill="var(--forecast)" radius={[3, 3, 0, 0]} {...motion} />
                  <Bar dataKey="p90_mw" name="P90 over-forecast" fill="var(--p90)" radius={[3, 3, 0, 0]} {...motion} />
                </BarChart>
              )}
            </ResponsiveContainer>
            {view === 'level' ? (
              <p className="legend-note">P90 as % of forecast: {byLevel.map((b) => `${b.label}: ${fmt(b.p90_pct_of_forecast, 0, ' %')}`).join(' · ')}</p>
            ) : null}
          </Panel>

          <Panel title="The month, day by day" sub="Tint: size of each day's miss (red = over-forecast). Click a day to open its decision view." right={<button className="btn" onClick={() => downloadCsv(`accuracy_${a.from_day}_${a.to_day}.csv`, a.by_day)}>CSV</button>}>
            <MonthStrip days={a.by_day} onSelect={(d) => navigate(`/decision?day=${d}`)} />
            <ResponsiveContainer width="100%" height={240}>
              <LineChart data={series} margin={{ top: 16, right: 12, bottom: 0, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="label" {...axis} interval={71} tickFormatter={(v: string) => v.replace(/^\w+ /, '').replace(/ \d\d:\d\d$/, '')} />
                <YAxis {...axis} width={52} tickFormatter={(v) => fmt(v)} />
                <Tooltip content={<ChartTip />} isAnimationActive={false} cursor={{ stroke: 'var(--line-strong)' }} />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                <Line type="monotone" dataKey="forecast" name="Forecast" stroke="var(--forecast)" dot={false} strokeWidth={1.5} {...motion} />
                <Line type="monotone" dataKey="actual" name="Actual" stroke="var(--actual)" dot={false} strokeWidth={1.5} {...motion} />
              </LineChart>
            </ResponsiveContainer>
            <details style={{ marginTop: '0.5rem' }}>
              <summary className="muted" style={{ cursor: 'pointer' }}>
                Daily scorecard ({a.by_day.length} days)
              </summary>
              <div className="table-wrap" style={{ marginTop: '0.5rem' }}>
                <table className="data">
                  <thead>
                    <tr>
                      <th>Delivery day</th>
                      <th>Decided</th>
                      <th>Run</th>
                      <th>Forecast</th>
                      <th>Actual</th>
                      <th>Error</th>
                      <th>MAE</th>
                      <th>Worst hour</th>
                      <th>Worst miss</th>
                    </tr>
                  </thead>
                  <tbody>
                    {a.by_day.map((r) => (
                      <tr key={r.delivery_day}>
                        <td>
                          <Link to={`/decision?day=${r.decision_day}`}>{dateLabel(r.delivery_day)}</Link>
                        </td>
                        <td>{r.decision_day ? dateLabel(r.decision_day) : '–'}</td>
                        <td>{hourLabel(r.publish)}</td>
                        <td>{gwh(r.forecast_mwh)}</td>
                        <td>{gwh(r.actual_mwh)}</td>
                        <td className={(r.error_mwh ?? 0) > 0 ? 'pos' : 'neg'}>{fmtSigned(r.error_mwh === null ? null : r.error_mwh / 1000, 1, ' GWh')}</td>
                        <td>{fmt(r.mae_mw, 0, ' MW')}</td>
                        <td>{r.worst_hour ? hourLabel(r.worst_hour) : '–'}</td>
                        <td className={(r.worst_error_mw ?? 0) > 0 ? 'pos' : 'neg'}>{fmtSigned(r.worst_error_mw, 0, ' MW')}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </details>
          </Panel>

          <details className="panel">
            <summary>
              <div>
                <h2>Assumptions behind these numbers</h2>
              </div>
              <span className="chev">›</span>
            </summary>
            <ul className="muted" style={{ margin: 0, paddingLeft: 18, lineHeight: 1.7 }}>
              {Object.values(m.assumptions).map((t) => (
                <li key={t}>{t}</li>
              ))}
              <li>MAPE is not shown: calm hours with near-zero actual generation make it meaningless.</li>
            </ul>
          </details>
        </div>
      ) : null}
    </div>
  )
}
