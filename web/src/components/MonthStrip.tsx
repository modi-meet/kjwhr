import type { DayRow } from '../api/client'
import { dateLabel, fmtSigned } from '../lib/format'

/**
 * One cell per decision day, tinted by the size of that day's miss.
 * Wayfinding for the month: where am I, where were the bad days, click to go there.
 */
export function MonthStrip({
  days,
  selected,
  onSelect,
}: {
  days: DayRow[]
  selected?: string | null
  onSelect: (decisionDay: string) => void
}) {
  const max = Math.max(1, ...days.map((d) => Math.abs(d.error_mwh ?? 0)))
  return (
    <div className="strip" role="listbox" aria-label="Decision days">
      {days.map((d) => {
        const e = d.error_mwh ?? 0
        const t = Math.min(1, Math.abs(e) / max)
        const tone = e > 0 ? 'var(--bad)' : 'var(--good)'
        const isSel = d.decision_day === selected
        return (
          <button
            key={d.delivery_day}
            type="button"
            role="option"
            aria-selected={isSel}
            className={`strip-cell ${isSel ? 'sel' : ''}`}
            style={{ ['--tint' as string]: `color-mix(in srgb, ${tone} ${Math.round(12 + 70 * t)}%, transparent)` }}
            title={`Decide ${d.decision_day ? dateLabel(d.decision_day) : ''} → deliver ${dateLabel(d.delivery_day)}: ${fmtSigned(e / 1000, 1, ' GWh')}`}
            onPointerDown={() => d.decision_day && onSelect(d.decision_day)}
            onClick={() => d.decision_day && onSelect(d.decision_day)}
          >
            <span className="strip-day">{d.delivery_day.slice(8)}</span>
          </button>
        )
      })}
    </div>
  )
}
