export const formatClock = (d: Date): string => {
  const h = d.getHours().toString().padStart(2, "0")
  const m = d.getMinutes().toString().padStart(2, "0")
  return `${h}:${m}`
}

export const formatTimeWindow = (start: Date, end: Date): string =>
  `${formatClock(start)}–${formatClock(end)}`

export const formatRoughClock = (d: Date): string => {
  const minutes = d.getMinutes()
  const rounded = Math.round(minutes / 10) * 10
  const adjusted = new Date(d)
  adjusted.setMinutes(rounded === 60 ? 0 : rounded, 0, 0)
  if (rounded === 60) adjusted.setHours(d.getHours() + 1)
  return formatClock(adjusted)
}

export const formatPercent = (fraction: number): string =>
  `${Math.round(fraction * 100)}%`
