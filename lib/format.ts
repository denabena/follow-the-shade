/** Explicit locale + timezone so SSR and browser produce the same string (avoids hydration mismatch). */
export const formatZagrebDayTimeLabel = (d: Date): string =>
  new Intl.DateTimeFormat("en-GB", {
    weekday: "long",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
    timeZone: "Europe/Zagreb",
  }).format(d)

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
