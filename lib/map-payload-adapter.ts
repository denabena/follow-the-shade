import type {
  MapPayload,
  MapPayloadResult,
} from "@/lib/follow-the-shade/types";
import type { Cafe, CafeResult, IntentRequest, TimelinePoint } from "./types";

const parseDate = (value: string): Date => {
  const parsed = new Date(value);
  if (!Number.isNaN(parsed.getTime())) return parsed;
  return new Date();
};

const toCafe = (result: MapPayloadResult): Cafe => ({
  id: result.id,
  name: result.name,
  neighborhood: result.address,
  blurb: result.exposure.summary,
  lng: result.terrace_point.lng,
  lat: result.terrace_point.lat,
});

const toTimeline = (result: MapPayloadResult): TimelinePoint[] =>
  result.exposure.samples.map((sample) => ({
    t: parseDate(sample.time),
    inSun: sample.state === "sun",
  }));

const toHeadline = (result: MapPayloadResult): string =>
  result.exposure.label.replaceAll("_", " ");

const toNuance = (result: MapPayloadResult): string => {
  if (result.exposure.transition_notes.length > 0) {
    return result.exposure.transition_notes.join(", ");
  }
  return result.exposure.summary;
};

export const intentFromMapPayload = (payload: MapPayload): IntentRequest => {
  return {
    id: payload.analysis_id,
    utterance: payload.request.location_label,
    preference: payload.request.preference,
    windowStart: parseDate(payload.request.start),
    windowEnd: parseDate(payload.request.end),
    area: {
      name: payload.request.location_label,
      center: [payload.map.center.lng, payload.map.center.lat],
      radiusM: 500,
      zoom: payload.map.zoom,
    },
  };
};

export const resultsFromMapPayload = (payload: MapPayload): CafeResult[] =>
  payload.results.map((result) => ({
    cafe: toCafe(result),
    timeline: toTimeline(result),
    sunFraction: result.exposure.sun_ratio,
    matches: result.exposure.match_score >= 0.6,
    nuance: toNuance(result),
    headline: toHeadline(result),
  }));

const answerCopy: {
  preferences: Record<MapPayload["request"]["preference"], string>;
  found: string;
  none: string;
  one: string;
  many: string;
  weatherBlock: string;
  weatherCloud: string;
} = {
  preferences: {
    sun: "sunny",
    shade: "shade-friendly",
    either: "outdoor",
  },
  found: "I found {count} {preference} {options} near {location} for {window}.",
  none: "I could not find a solid {preference} match near {location} for {window}.",
  one: "option",
  many: "options",
  weatherBlock:
    "Rain or heavy cloud keeps direct sun off the terrace during that window.",
  weatherCloud: "Cloud cover keeps the sun muted during that window.",
};

export const answerFromMapPayload = (payload: MapPayload): string => {
  const copy = answerCopy;
  const weatherState = getWeatherState(payload);
  const preferenceKey =
    payload.request.preference === "sun" && weatherState === "blocked"
      ? "either"
      : payload.request.preference;
  const preference = copy.preferences[preferenceKey];
  const location = payload.request.location_label || "Split";
  const window = formatWindow(payload.request.start, payload.request.end);
  const count = payload.results.length;

  const sentences = [
    count === 0
      ? fillTemplate(copy.none, { preference, location, window })
      : fillTemplate(copy.found, {
          count: String(count),
          preference,
          options: count === 1 ? copy.one : copy.many,
          location,
          window,
        }),
  ];

  const weather = weatherSentence(weatherState, copy);
  if (weather) sentences.push(weather);

  return sentences.join(" ");
};

const fillTemplate = (
  template: string,
  values: Record<string, string>,
): string =>
  Object.entries(values).reduce(
    (text, [key, value]) => text.replaceAll(`{${key}}`, value),
    template,
  );

const formatWindow = (start: string, end: string): string => {
  const startLabel = formatTime(start);
  const endLabel = formatTime(end);
  return startLabel && endLabel
    ? `${startLabel}-${endLabel}`
    : "the requested window";
};

const formatTime = (value: string): string | null => {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return null;
  return new Intl.DateTimeFormat(undefined, {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(parsed);
};

const maxNumber = (
  payload: MapPayload,
  key:
    | "cloud_cover_avg"
    | "precipitation_probability_max"
    | "precipitation_mm_max",
): number | null => {
  const values = payload.results
    .map((result) => result.weather[key])
    .filter((value): value is number => typeof value === "number");
  return values.length > 0 ? Math.max(...values) : null;
};

const getWeatherState = (payload: MapPayload): "blocked" | "cloudy" | null => {
  const precipitationMm = maxNumber(payload, "precipitation_mm_max");
  const precipitationProbability = maxNumber(
    payload,
    "precipitation_probability_max",
  );
  const cloudCover = maxNumber(payload, "cloud_cover_avg");

  if (
    (precipitationMm !== null && precipitationMm > 0) ||
    (precipitationProbability !== null && precipitationProbability >= 70) ||
    (cloudCover !== null && cloudCover >= 85)
  ) {
    return "blocked";
  }
  if (cloudCover !== null && cloudCover > 60) return "cloudy";
  return null;
};

const weatherSentence = (
  weatherState: "blocked" | "cloudy" | null,
  copy: typeof answerCopy,
): string | null => {
  if (weatherState === "blocked") return copy.weatherBlock;
  if (weatherState === "cloudy") return copy.weatherCloud;
  return null;
};
