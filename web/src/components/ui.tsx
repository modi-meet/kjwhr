import type { ReactNode } from 'react'

export function Panel({ title, sub, right, children }: { title: string; sub?: string; right?: ReactNode; children: ReactNode }) {
  return (
    <section className="panel">
      <header className="panel-head">
        <div>
          <h2>{title}</h2>
          {sub ? <p className="muted">{sub}</p> : null}
        </div>
        {right}
      </header>
      {children}
    </section>
  )
}

export function Kpi({ label, value, hint, tone, hero }: { label: string; value: string; hint?: string; tone?: 'good' | 'bad' | 'warn'; hero?: boolean }) {
  return (
    <div className={`kpi ${tone ?? ''} ${hero ? 'hero' : ''}`}>
      <div className="kpi-label">{label}</div>
      <div className="kpi-value">{value}</div>
      {hint ? <div className="kpi-hint">{hint}</div> : null}
    </div>
  )
}

/** Apple-style segmented control: one choice, every option visible, instant press feedback. */
export function Segmented<T extends string>({
  value,
  options,
  onChange,
  ariaLabel,
}: {
  value: T
  options: { value: T; label: string; hint?: string }[]
  onChange: (v: T) => void
  ariaLabel: string
}) {
  return (
    <div className="seg" role="group" aria-label={ariaLabel}>
      {options.map((o) => (
        <button key={o.value} type="button" aria-pressed={o.value === value} onPointerDown={() => onChange(o.value)} onClick={() => onChange(o.value)}>
          {o.label}
          {o.hint ? <small>{o.hint}</small> : null}
        </button>
      ))}
    </div>
  )
}

export function Loading({ text = 'Loading…' }: { text?: string }) {
  return <div className="state">{text}</div>
}

export function ErrorBox({ error }: { error: unknown }) {
  return <div className="state error">Could not load data: {error instanceof Error ? error.message : String(error)}</div>
}
