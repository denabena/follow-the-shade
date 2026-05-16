"use client"

import type { AnalysisProgress, IntentRequest } from "@/lib/types"
import { formatClock, formatTimeWindow } from "@/lib/format"

type Props = {
  progress: AnalysisProgress | null
  intent: IntentRequest
}

const AnalysisOverlay = ({ progress, intent }: Props) => {
  const pct = progress
    ? Math.min(100, ((progress.stepIndex + progress.cafesSampled / progress.totalCafes) /
        progress.totalSteps) * 100)
    : 0
  const clock = progress ? formatClock(progress.currentTime) : formatClock(intent.windowStart)

  return (
    <div
      className="pointer-events-none absolute right-5 top-5 z-20 w-[260px] origin-top-right select-none"
      role="status"
      aria-live="polite"
    >
      <div className="grain relative border border-ink/15 bg-bone/95 px-4 py-3.5 shadow-[0_10px_30px_-12px_rgba(14,42,61,0.35)] backdrop-blur">
        <div className="flex items-baseline justify-between">
          <p className="font-mono text-[10px] uppercase tracking-[0.22em] text-terracotta-deep">
            tracing shadows
          </p>
          <p className="font-display text-[15px] tabular-nums text-ink">
            {clock}
          </p>
        </div>
        <div className="mt-3 h-1 w-full overflow-hidden rounded-full bg-ink/10">
          <div
            className="h-full rounded-full bg-terracotta transition-[width] duration-200"
            style={{ width: `${pct}%` }}
          />
        </div>
        <div className="mt-2.5 flex items-center justify-between text-[11px] text-ink/65">
          <span className="font-mono tracking-[0.1em]">
            {formatTimeWindow(intent.windowStart, intent.windowEnd)}
          </span>
          {progress && (
            <span className="font-mono tracking-[0.1em]">
              {progress.cafesSampled}/{progress.totalCafes} sampled
            </span>
          )}
        </div>
      </div>
    </div>
  )
}

export default AnalysisOverlay
