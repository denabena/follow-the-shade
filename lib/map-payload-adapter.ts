import type { MapPayload, MapPayloadResult } from "@/lib/follow-the-shade/types"
import type { Cafe, CafeResult, IntentRequest, TimelinePoint } from "./types"

const parseDate = (value: string): Date => {
  const parsed = new Date(value)
  if (!Number.isNaN(parsed.getTime())) return parsed
  return new Date()
}

const toCafe = (result: MapPayloadResult): Cafe => ({
  id: result.id,
  name: result.name,
  neighborhood: result.address,
  blurb: result.exposure.summary,
  lng: result.terrace_point.lng,
  lat: result.terrace_point.lat
})

const toTimeline = (result: MapPayloadResult): TimelinePoint[] =>
  result.exposure.samples.map((sample) => ({
    t: parseDate(sample.time),
    inSun: sample.state === "sun"
  }))

const toHeadline = (result: MapPayloadResult): string =>
  result.exposure.label.replaceAll("_", " ")

const toNuance = (result: MapPayloadResult): string => {
  if (result.exposure.transition_notes.length > 0) {
    return result.exposure.transition_notes.join(", ")
  }
  return result.exposure.summary
}

export const intentFromMapPayload = (payload: MapPayload): IntentRequest => {
  const preference =
    payload.request.preference === "shade" ? "shade" : "sun"

  return {
    id: payload.analysis_id,
    utterance: payload.request.location_label,
    preference,
    windowStart: parseDate(payload.request.start),
    windowEnd: parseDate(payload.request.end),
    area: {
      name: payload.request.location_label,
      center: [payload.map.center.lng, payload.map.center.lat],
      radiusM: 500,
      zoom: payload.map.zoom
    }
  }
}

export const resultsFromMapPayload = (payload: MapPayload): CafeResult[] =>
  payload.results.map((result) => ({
    cafe: toCafe(result),
    timeline: toTimeline(result),
    sunFraction: result.exposure.sun_ratio,
    matches: result.exposure.match_score >= 0.6,
    nuance: toNuance(result),
    headline: toHeadline(result)
  }))
