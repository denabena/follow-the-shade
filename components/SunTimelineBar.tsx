import type { TimelinePoint } from "@/lib/types"
import { formatClock } from "@/lib/format"

type Props = {
  timeline: TimelinePoint[]
  windowStart: Date
  windowEnd: Date
}

const SunTimelineBar = ({ timeline, windowStart, windowEnd }: Props) => {
  if (timeline.length === 0) return null

  const totalMs = windowEnd.getTime() - windowStart.getTime()
  const cellWidth = 100 / timeline.length

  return (
    <div className="w-full">
      <div className="flex h-2.5 w-full overflow-hidden rounded-full border border-ink/10 bg-bone-deep/60">
        {timeline.map((p, i) => (
          <span
            key={i}
            className={p.inSun ? "h-full bg-gold-sun" : "h-full bg-ink/85"}
            style={{ width: `${cellWidth}%` }}
            title={`${formatClock(p.t)} — ${p.inSun ? "sun" : "shade"}`}
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
