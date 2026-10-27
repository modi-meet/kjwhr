export const fmt = (v: number | null | undefined, digits = 0, unit = '') =>
  v === null || v === undefined || Number.isNaN(v)
    ? '–'
    : `${v.toLocaleString('en-GB', { maximumFractionDigits: digits, minimumFractionDigits: digits })}${unit}`

export const fmtSigned = (v: number | null | undefined, digits = 0, unit = '') =>
  v === null || v === undefined ? '–' : `${v > 0 ? '+' : ''}${fmt(v, digits, unit)}`

export const gwh = (mwh: number | null | undefined) => fmt(mwh === null || mwh === undefined ? null : mwh / 1000, 1, ' GWh')

export const hourLabel = (iso: string) => iso.slice(11, 16)

export const dateLabel = (iso: string) =>
  new Date(iso + (iso.length === 10 ? 'T00:00:00Z' : '')).toLocaleDateString('en-GB', {
    weekday: 'short',
    day: 'numeric',
    month: 'short',
    timeZone: 'UTC',
  })

export const timeLabel = (iso: string) =>
  new Date(iso).toLocaleString('en-GB', {
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
    timeZone: 'UTC',
  }) + ' UTC'

export function downloadCsv(name: string, rows: Record<string, unknown>[]) {
  if (!rows.length) return
  const cols = Object.keys(rows[0])
  const esc = (v: unknown) => (v === null || v === undefined ? '' : String(v).includes(',') ? `"${v}"` : String(v))
  const body = [cols.join(','), ...rows.map((r) => cols.map((c) => esc(r[c])).join(','))].join('\n')
  const a = document.createElement('a')
  a.href = URL.createObjectURL(new Blob([body], { type: 'text/csv' }))
  a.download = name
  a.click()
  URL.revokeObjectURL(a.href)
}

export const addDays = (iso: string, n: number) => {
  const d = new Date(iso + 'T00:00:00Z')
  d.setUTCDate(d.getUTCDate() + n)
  return d.toISOString().slice(0, 10)
}
