import type { TimelinePoint } from "@/lib/types"
import { cn } from "@/lib/cn"
import { formatClock } from "@/lib/format"
type Props = {
  timeline: TimelinePoint[]
  windowStart: Date
  windowEnd: Date
  onSampleSelect?: (time: Date) => void
}

const SunTimelineBar = ({
  timeline,
  windowStart,
  windowEnd,
  onSampleSelect,
}: Props) => {
  if (timeline.length === 0) return null

  const totalMs = windowEnd.getTime() - windowStart.getTime()
  const cellWidth = 100 / timeline.length

  return (
    <div className="w-full">
      <div className="flex h-2.5 w-full overflow-hidden rounded-full border border-ink/10 bg-bone-deep/60">
        {timeline.map((p, i) => (
          <button
            key={i}
            type="button"
            className={cn(
              "h-full min-w-0 shrink-0 border-0 p-0 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-terracotta focus-visible:ring-offset-1 focus-visible:ring-offset-bone",
              p.inSun ? "bg-gold-sun" : "bg-ink/85",
            )}
            style={{ width: `${cellWidth}%` }}
            title={`${formatClock(p.t)} — ${p.inSun ? "sun" : "shade"} · click to preview on map`}
            aria-label={`Preview map shadows at ${formatClock(p.t)}, ${p.inSun ? "sun" : "shade"}`}
            onClick={(e) => {
              e.stopPropagation()
              onSampleSelect?.(p.t)
            }}
          />
        ))}
      </div>
      <div className="mt-1 flex justify-between font-mono text-[10px] uppercase tracking-[0.12em] text-ink/55">
        <span>{formatClock(windowStart)}</span>
        <span>{formatClock(windowEnd)}</span>
      </div>
      <span className="sr-only">
        Sun timeline over {Math.round(totalMs / 60000)} minutes
      </span>
    </div>
  )
}

export default SunTimelineBar
