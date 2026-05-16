import type { CafeResult, IntentRequest } from "./types"
import { formatTimeWindow } from "./format"

export const greet = (): string =>
  "Hey. I'm your shade scout for Split. Tell me where, when, and whether you want the sun on your face or a cool stone wall behind it — I'll go check the rooftops and walls for you."

export const acknowledging = (intent: IntentRequest): string => {
  const window = formatTimeWindow(intent.windowStart, intent.windowEnd)
  if (intent.preference === "sun") {
    return `Got it — somewhere with the sun on the terrace around ${intent.area.name}, between ${window}. Give me a minute, I'm going to actually watch the shadows move across the city for that window.`
  }
  return `Got it — looking for a properly shaded spot around ${intent.area.name} between ${window}. Let me trace the building shadows for that window and see which terraces stay cool.`
}

export const analyzingStart = (
  intent: IntentRequest,
  totalCafes: number,
  totalSteps: number
): string => {
  const window = formatTimeWindow(intent.windowStart, intent.windowEnd)
  return `Pulling building heights around ${intent.area.name}, then stepping the sun from ${window} in ${totalSteps} slices and sampling all ${totalCafes} candidate terraces. You'll see the shadow layer move in real time — hang tight.`
}

const pickTopMatches = (results: CafeResult[]): CafeResult[] =>
  results
    .filter((r) => r.matches)
    .sort((a, b) => Math.abs(b.sunFraction - 0.5) - Math.abs(a.sunFraction - 0.5))
    .slice(0, 3)

export const summarize = (
  intent: IntentRequest,
  results: CafeResult[]
): { intro: string; matches: CafeResult[]; outro: string } => {
  const top = pickTopMatches(results)
  const window = formatTimeWindow(intent.windowStart, intent.windowEnd)

  if (top.length === 0) {
    return {
      intro: `Honest answer: across ${intent.area.name} between ${window}, nothing scored cleanly for a ${intent.preference}-soaked terrace. Closest contenders below — pick the one whose nuance fits how long you'll actually stay.`,
      matches: results
        .slice()
        .sort((a, b) =>
          intent.preference === "sun"
            ? b.sunFraction - a.sunFraction
            : a.sunFraction - b.sunFraction
        )
        .slice(0, 3),
      outro:
        "If you want, narrow the window — a 45-minute slot usually opens up cleaner picks."
    }
  }

  const headline =
    intent.preference === "sun"
      ? `${top.length === 1 ? "One clean pick" : `${top.length} clean picks`} for sun on the terrace between ${window}:`
      : `${top.length === 1 ? "One properly shaded spot" : `${top.length} properly shaded spots`} between ${window}:`

  return {
    intro: `OK — ran the shadows. ${headline}`,
    matches: top,
    outro:
      "Tap any of them to fly the map over. The dim markers are places I checked but ruled out."
  }
}
