import type {
  DetectedLanguage,
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

const answerCopy: Record<
  DetectedLanguage,
  {
    preferences: Record<MapPayload["request"]["preference"], string>;
    found: string;
    none: string;
    one: string;
    many: string;
    weatherBlock: string;
    weatherCloud: string;
    uncertainty: string;
  }
> = {
  en: {
    preferences: {
      sun: "sunny",
      shade: "shade-friendly",
      either: "outdoor",
    },
    found:
      "I found {count} {preference} {options} near {location} for {window}.",
    none: "I could not find a solid {preference} match near {location} for {window}.",
    one: "option",
    many: "options",
    weatherBlock:
      "Open-Meteo shows rain or heavy cloud, so direct sun is not expected.",
    weatherCloud:
      "Cloud cover is high, so direct sun may feel weaker than the geometric shade model.",
    uncertainty:
      "Some terrace points or building heights are estimated, so treat the timing as approximate.",
  },
  hr: {
    preferences: { sun: "suncanih", shade: "sjenovitih", either: "vanjskih" },
    found:
      "Pronasao sam {count} {preference} opcija blizu {location} za {window}.",
    none: "Nisam nasao pouzdanu {preference} opciju blizu {location} za {window}.",
    one: "opcija",
    many: "opcija",
    weatherBlock:
      "Open-Meteo pokazuje kisu ili gustu naoblaku, pa izravno sunce nije ocekivano.",
    weatherCloud:
      "Naoblaka je visoka, pa ce izravno sunce biti slabije od same geometrije.",
    uncertainty:
      "Neke terase ili visine zgrada su procijenjene, pa vrijeme sjene uzmi kao priblizno.",
  },
  it: {
    preferences: { sun: "al sole", shade: "all'ombra", either: "all'aperto" },
    found:
      "Ho trovato {count} opzioni {preference} vicino a {location} per {window}.",
    none: "Non ho trovato una buona opzione {preference} vicino a {location} per {window}.",
    one: "opzione",
    many: "opzioni",
    weatherBlock:
      "Open-Meteo indica pioggia o molte nuvole, quindi il sole diretto non e previsto.",
    weatherCloud:
      "La copertura nuvolosa e alta, quindi il sole diretto puo sembrare piu debole del modello geometrico.",
    uncertainty:
      "Alcuni punti terrazza o altezze degli edifici sono stimati, quindi gli orari sono approssimativi.",
  },
  de: {
    preferences: { sun: "sonnige", shade: "schattige", either: "Outdoor-" },
    found:
      "Ich habe {count} {preference} Optionen nahe {location} fuer {window} gefunden.",
    none: "Ich habe keine solide {preference} Option nahe {location} fuer {window} gefunden.",
    one: "Option",
    many: "Optionen",
    weatherBlock:
      "Open-Meteo zeigt Regen oder dichte Bewoelkung, daher ist keine direkte Sonne zu erwarten.",
    weatherCloud:
      "Die Bewoelkung ist hoch, daher kann direkte Sonne schwaecher wirken als im geometrischen Modell.",
    uncertainty:
      "Einige Terrassenpunkte oder Gebaeudehoehen sind geschaetzt, daher sind die Zeiten ungefaehr.",
  },
  sl: {
    preferences: { sun: "soncnih", shade: "sencnih", either: "zunanjih" },
    found:
      "Nasel sem {count} {preference} moznosti blizu {location} za {window}.",
    none: "Nisem nasel zanesljive {preference} moznosti blizu {location} za {window}.",
    one: "moznost",
    many: "moznosti",
    weatherBlock:
      "Open-Meteo kaze dez ali gosto oblacnost, zato neposrednega sonca ni pricakovati.",
    weatherCloud:
      "Oblacnost je visoka, zato je neposredno sonce lahko sibkejse od geometrijskega modela.",
    uncertainty:
      "Nekatere terase ali visine stavb so ocenjene, zato so casi priblizni.",
  },
  fr: {
    preferences: {
      sun: "ensoleillees",
      shade: "ombragees",
      either: "en terrasse",
    },
    found:
      "J'ai trouve {count} options {preference} pres de {location} pour {window}.",
    none: "Je n'ai pas trouve de bonne option {preference} pres de {location} pour {window}.",
    one: "option",
    many: "options",
    weatherBlock:
      "Open-Meteo indique de la pluie ou une forte couverture nuageuse, donc le soleil direct n'est pas attendu.",
    weatherCloud:
      "La couverture nuageuse est elevee, donc le soleil direct peut sembler plus faible que dans le modele geometrique.",
    uncertainty:
      "Certains points de terrasse ou hauteurs de batiments sont estimes, donc les horaires restent approximatifs.",
  },
};

export const answerFromMapPayload = (
  payload: MapPayload,
  language: DetectedLanguage | null = "en",
): string => {
  const copy = answerCopy[language ?? "en"] ?? answerCopy.en;
  const preference = copy.preferences[payload.request.preference];
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

  const weather = weatherSentence(payload, copy);
  if (weather) sentences.push(weather);
  if (hasEstimatedGeometry(payload)) sentences.push(copy.uncertainty);

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

const weatherSentence = (
  payload: MapPayload,
  copy: (typeof answerCopy)[DetectedLanguage],
): string | null => {
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
    return copy.weatherBlock;
  }
  if (cloudCover !== null && cloudCover > 60) return copy.weatherCloud;
  return null;
};

const hasEstimatedGeometry = (payload: MapPayload): boolean => {
  const text = [
    ...payload.source_notes,
    ...payload.results.flatMap((result) => result.exposure.confidence_reasons),
  ]
    .join(" ")
    .toLowerCase();

  return [
    "estimated",
    "missing building",
    "default height",
    "approx",
    "fallback",
  ].some((token) => text.includes(token));
};
