import type { IntentRequest } from "@/lib/types"
import { formatTimeWindow } from "@/lib/format"
import { cn } from "@/lib/cn"

type Props = {
  intent: IntentRequest
}

const IntentCard = ({ intent }: Props) => {
  const isSun = intent.preference === "sun"
  return (
    <div
      className={cn(
        "inline-flex flex-wrap items-center gap-2 rounded-full border border-ink/15 bg-bone-soft/70 py-1.5 pl-1.5 pr-4 text-sm",
        "fts-fade-up"
      )}
    >
      <span
        className={cn(
          "flex h-6 w-6 items-center justify-center rounded-full text-bone",
          isSun ? "bg-gold-sun text-ink" : "bg-ink"
        )}
        aria-hidden="true"
      >
        {isSun ? (
          <SunMark />
        ) : (
          <ShadeMark />
        )}
      </span>
      <span className="font-display text-[15px] tracking-tight">
        {isSun ? "Sun" : "Shade"}
      </span>
      <span className="text-ink/30">·</span>
      <span className="font-mono text-[12px] tracking-[0.1em] text-ink/80">
        {formatTimeWindow(intent.windowStart, intent.windowEnd)}
      </span>
      <span className="text-ink/30">·</span>
      <span className="text-[13px] text-ink/80">near {intent.area.name}</span>
    </div>
  )
}

const SunMark = () => (
  <svg viewBox="0 0 16 16" className="h-3.5 w-3.5" aria-hidden="true">
    <circle cx="8" cy="8" r="3" fill="currentColor" />
    {[...Array(8)].map((_, i) => {
      const a = (i * Math.PI) / 4
      return (
        <line
          key={i}
          x1={8 + Math.cos(a) * 4.5}
          y1={8 + Math.sin(a) * 4.5}
          x2={8 + Math.cos(a) * 7}
          y2={8 + Math.sin(a) * 7}
          stroke="currentColor"
          strokeWidth={1.4}
          strokeLinecap="round"
        />
      )
    })}
  </svg>
)

const ShadeMark = () => (
  <svg viewBox="0 0 16 16" className="h-3.5 w-3.5" aria-hidden="true">
    <path
      d="M11.5 9.6A4.5 4.5 0 1 1 6.4 4.5 5.4 5.4 0 0 0 11.5 9.6Z"
      fill="#f4efe6"
    />
  </svg>
)

export default IntentCard
