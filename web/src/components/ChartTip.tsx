import { fmt } from '../lib/format'

type Item = { name?: string; value?: number | string | (number | string)[]; color?: string; dataKey?: string | number }

export function ChartTip({
  active,
  payload,
  label,
  unit = ' MW',
  title,
}: {
  active?: boolean
  payload?: Item[]
  label?: string | number
  unit?: string
  title?: (label: string | number | undefined, payload: Item[]) => string
}) {
  if (!active || !payload?.length) return null
  return (
    <div className="tip">
      <b>{title ? title(label, payload) : label}</b>
      {payload
        .filter((p) => p.value !== undefined && p.value !== null)
        .map((p, i) => (
          <div key={i}>
            <span style={{ color: p.color }}>{p.name}</span>
            <span>
              {Array.isArray(p.value)
                ? `${fmt(Number(p.value[0]))} – ${fmt(Number(p.value[1]))}${unit}`
                : `${fmt(Number(p.value))}${unit}`}
            </span>
          </div>
        ))}
    </div>
  )
}
