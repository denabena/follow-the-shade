"use client";

import type { CafeResult, IntentRequest } from "@/lib/types";
import { cn } from "@/lib/cn";
import { formatPercent } from "@/lib/format";
import SunTimelineBar from "./SunTimelineBar";

type Props = {
  result: CafeResult;
  intent: IntentRequest;
  onSelect: () => void;
  onShadeSampleTime?: (time: Date) => void;
};

const CafeResultCard = ({
  result,
  intent,
  onSelect,
  onShadeSampleTime,
}: Props) => {
  const { cafe, sunFraction, headline, nuance, matches, timeline } = result;
  const locationLine = cafe.venueType
    ? `${cafe.venueType} - ${cafe.neighborhood}`
    : cafe.neighborhood;

  const handleKeyDown = (e: React.KeyboardEvent<HTMLDivElement>) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      onSelect();
    }
  };

  return (
    <div
      role="button"
      tabIndex={0}
      aria-label={`Fly map to ${cafe.name} in ${cafe.neighborhood}`}
      onClick={onSelect}
      onKeyDown={handleKeyDown}
      className={cn(
        "group relative block w-full cursor-pointer rounded-md border bg-bone px-4 py-3.5 text-left transition-all",
        "fts-fade-up",
        matches
          ? "border-terracotta/40 hover:border-terracotta hover:-translate-y-0.5"
          : "border-ink/10 opacity-80 hover:opacity-100",
      )}
    >
      <div className="flex items-baseline justify-between gap-3">
        <div className="min-w-0">
          <h3 className="font-display text-[19px] leading-tight text-ink">
            {cafe.name}
          </h3>
          <p className="mt-0.5 text-[11px] font-medium uppercase tracking-[0.18em] text-ink/55">
            {locationLine}
          </p>
        </div>
        <div className="shrink-0 text-right">
          <p
            className={cn(
              "font-display text-[15px] leading-none",
              intent.preference === "sun" ? "text-terracotta" : "text-ink-soft",
            )}
          >
            {headline}
          </p>
          <p className="mt-1 font-mono text-[10px] tracking-[0.12em] text-ink/55">
            {formatPercent(sunFraction)} sun
          </p>
        </div>
      </div>

      <p className="mt-3 text-[13px] leading-snug text-ink/75">{cafe.blurb}</p>

      <div className="mt-3">
        <SunTimelineBar
          timeline={timeline}
          windowStart={intent.windowStart}
          windowEnd={intent.windowEnd}
          onSampleSelect={onShadeSampleTime}
        />
      </div>

      {nuance && (
        <p className="mt-2.5 text-[12.5px] italic text-terracotta-deep">
          {nuance}
        </p>
      )}
    </div>
  );
};

export default CafeResultCard;
