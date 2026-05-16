import { cn } from "@/lib/cn"

/** Decorative sun — loading states and brand flair. */
export function SunGlyph({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 48 48"
      className={cn("h-full w-full", className)}
      aria-hidden={true}
    >
      <circle cx="24" cy="24" r="7" fill="#e8b547" />
      {[...Array(8)].map((_, i) => {
        const a = (i * Math.PI) / 4
        const x1 = 24 + Math.cos(a) * 12
        const y1 = 24 + Math.sin(a) * 12
        const x2 = 24 + Math.cos(a) * 20
        const y2 = 24 + Math.sin(a) * 20
        return (
          <line
            key={i}
            x1={x1}
            y1={y1}
            x2={x2}
            y2={y2}
            stroke="#c76b45"
            strokeWidth={2.2}
            strokeLinecap="round"
          />
        )
      })}
    </svg>
  )
}
