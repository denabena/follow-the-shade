import seedCafeData from "@/assets/split_cafe_seed.json";
import type {
  AnalysisRecord,
  ChatRequest,
  ChatResponse,
  ExposurePreference,
  ExposureSample,
  ExposureState,
  LatLng,
  MapPayload,
  MapPayloadResult,
  SeedCafe,
} from "./types";

const seedCafes = seedCafeData as SeedCafe[];
const ZAGREB_TIME_ZONE = "Europe/Zagreb";

const SPLIT_AREAS: Array<{ label: string; aliases: string[]; center: LatLng }> =
  [
    {
      label: "Riva, Split",
      aliases: [
        "riva",
        "old town",
        "central split",
        "city center",
        "city centre",
        "center split",
        "centre split",
        "center",
        "centre",
      ],
      center: { lat: 43.5081, lng: 16.4391 },
    },
    {
      label: "Diocletian Palace, Split",
      aliases: ["diocletian", "palace", "pjaca", "peristil"],
      center: { lat: 43.5086, lng: 16.4409 },
    },
    {
      label: "Grad, Split",
      aliases: ["split grad"],
      center: { lat: 43.5088, lng: 16.4405 },
    },
    {
      label: "Marmontova, Split",
      aliases: ["marmontova"],
      center: { lat: 43.5102, lng: 16.4382 },
    },
    {
      label: "Prokurative, Split",
      aliases: ["prokurative", "trg republike"],
      center: { lat: 43.5095, lng: 16.437 },
    },
    {
      label: "Matejuska, Split",
      aliases: ["matejuska"],
      center: { lat: 43.5076, lng: 16.4355 },
    },
    {
      label: "Varos, Split",
      aliases: ["varos", "veli varos"],
      center: { lat: 43.5094, lng: 16.4336 },
    },
    {
      label: "Lučac-Manuš, Split",
      aliases: ["lucac-manus", "lucac manus", "lucac", "manus"],
      center: { lat: 43.5064, lng: 16.4368 },
    },
    {
      label: "West Coast, Split",
      aliases: ["west coast", "zapadna obala"],
      center: { lat: 43.5063, lng: 16.4323 },
    },
    {
      label: "Marjan, Split",
      aliases: ["marjan", "vidilica", "telegrin"],
      center: { lat: 43.5142, lng: 16.4275 },
    },
    {
      label: "Kasjuni, Split",
      aliases: ["kasjuni"],
      center: { lat: 43.5088, lng: 16.4187 },
    },
    {
      label: "Poljud, Split",
      aliases: ["poljud"],
      center: { lat: 43.51944, lng: 16.43167 },
    },
    {
      label: "Spinut, Split",
      aliases: ["spinut"],
      center: { lat: 43.5175, lng: 16.4178 },
    },
    {
      label: "Meje, Split",
      aliases: ["meje"],
      center: { lat: 43.5138, lng: 16.4078 },
    },
    {
      label: "Sustipan, Split",
      aliases: ["sustipan"],
      center: { lat: 43.5035, lng: 16.4223 },
    },
    {
      label: "Bol, Split",
      aliases: ["bol"],
      center: { lat: 43.5032, lng: 16.4265 },
    },
    {
      label: "Bacvice, Split",
      aliases: ["bacvice", "bacvice beach"],
      center: { lat: 43.5039, lng: 16.4514 },
    },
    {
      label: "Firule, Split",
      aliases: ["firule"],
      center: { lat: 43.5019, lng: 16.4592 },
    },
    {
      label: "Lovret, Split",
      aliases: ["lovret"],
      center: { lat: 43.5048, lng: 16.4478 },
    },
    {
      label: "Znjan, Split",
      aliases: ["znjan"],
      center: { lat: 43.5023, lng: 16.4865 },
    },
    {
      label: "Trstenik, Split",
      aliases: ["trstenik"],
      center: { lat: 43.5078, lng: 16.4635 },
    },
    {
      label: "Mertojak, Split",
      aliases: ["mertojak"],
      center: { lat: 43.5076, lng: 16.4545 },
    },
    {
      label: "Blatine-Škrape, Split",
      aliases: ["blatine-skrape", "blatine skrape", "blatine", "skrape"],
      center: { lat: 43.5132, lng: 16.4668 },
    },
    {
      label: "Split 3, Split",
      aliases: ["split 3", "treca cetvrt", "third district"],
      center: { lat: 43.5112, lng: 16.4705 },
    },
    {
      label: "Pujanke, Split",
      aliases: ["pujanke"],
      center: { lat: 43.5163, lng: 16.4737 },
    },
    {
      label: "Sućidar, Split",
      aliases: ["sucidar"],
      center: { lat: 43.5196, lng: 16.4675 },
    },
    {
      label: "Visoka, Split",
      aliases: ["visoka"],
      center: { lat: 43.5216, lng: 16.4578 },
    },
    {
      label: "Lokve, Split",
      aliases: ["lokve"],
      center: { lat: 43.5178, lng: 16.4488 },
    },
    {
      label: "Gripe, Split",
      aliases: ["gripe"],
      center: { lat: 43.5195, lng: 16.4412 },
    },
    {
      label: "Plokite, Split",
      aliases: ["plokite"],
      center: { lat: 43.5146, lng: 16.4395 },
    },
    {
      label: "Kopilica, Split",
      aliases: ["kopilica"],
      center: { lat: 43.5238, lng: 16.4328 },
    },
    {
      label: "Kman, Split",
      aliases: ["kman"],
      center: { lat: 43.5248, lng: 16.4468 },
    },
    {
      label: "Ravne njive, Split",
      aliases: ["ravne njive", "ravne"],
      center: { lat: 43.5295, lng: 16.4638 },
    },
    {
      label: "Brda, Split",
      aliases: ["brda"],
      center: { lat: 43.5348, lng: 16.4725 },
    },
    {
      label: "Kocunar, Split",
      aliases: ["kocunar"],
      center: { lat: 43.5148, lng: 16.4798 },
    },
    {
      label: "Neslanovac, Split",
      aliases: ["neslanovac"],
      center: { lat: 43.5395, lng: 16.4878 },
    },
    {
      label: "Mejaši, Split",
      aliases: ["mejasi"],
      center: { lat: 43.5428, lng: 16.4978 },
    },
    {
      label: "Sirobuja, Split",
      aliases: ["sirobuja"],
      center: { lat: 43.5078, lng: 16.5028 },
    },
    {
      label: "Šine, Split",
      aliases: ["sine"],
      center: { lat: 43.5298, lng: 16.4395 },
    },
    {
      label: "Brodarica, Split",
      aliases: ["brodarica"],
      center: { lat: 43.4998, lng: 16.4688 },
    },
    {
      label: "Stobreč, Split",
      aliases: ["stobrec"],
      center: { lat: 43.5036, lng: 16.5748 },
    },
    {
      label: "Podstrana, Split",
      aliases: ["podstrana"],
      center: { lat: 43.4888, lng: 16.5585 },
    },
    {
      label: "Solin, Split",
      aliases: ["solin"],
      center: { lat: 43.5442, lng: 16.4928 },
    },
    {
      label: "Klis, Split",
      aliases: ["klis"],
      center: { lat: 43.5588, lng: 16.5228 },
    },
  ];

const globalStore = globalThis as typeof globalThis & {
  followTheShadeAnalyses?: Map<string, AnalysisRecord>;
};

const analysisStore =
  globalStore.followTheShadeAnalyses ?? new Map<string, AnalysisRecord>();
globalStore.followTheShadeAnalyses = analysisStore;

export function getAnalysis(analysisId: string): AnalysisRecord | null {
  const record = analysisStore.get(analysisId);
  if (!record) {
    return null;
  }

  if (new Date(record.expires_at).getTime() < Date.now()) {
    analysisStore.delete(analysisId);
    return null;
  }

  return record;
}

export async function buildDemoChatResponse(
  request: ChatRequest,
): Promise<ChatResponse> {
  const threadId = request.thread_id || crypto.randomUUID();
  const message = request.message?.trim();

  if (!message) {
    return {
      answer:
        "Tell me where in Split you want to sit and what time window to check.",
      thread_id: threadId,
      analysis_id: null,
      map_payload: null,
      sources: [],
      audio: null,
      detected_language: "en",
    };
  }

  const normalized = normalize(message);
  const detectedLanguage = "en";

  if (isOutsideSplit(normalized)) {
    return {
      answer:
        "I'm focused on Split. Do you want something around Riva, Bacvice, Marmontova, Varos, or another Split area?",
      thread_id: threadId,
      analysis_id: null,
      map_payload: null,
      sources: [],
      audio: null,
      detected_language: detectedLanguage,
    };
  }

  const timeWindow = parseTimeWindow(normalized);
  if (!timeWindow) {
    return {
      answer:
        "What time window should I check? For example: today from 3 to 5pm, tomorrow morning, or this Saturday afternoon.",
      thread_id: threadId,
      analysis_id: null,
      map_payload: null,
      sources: [],
      audio: null,
      detected_language: detectedLanguage,
    };
  }

  const preference = parsePreference(normalized);
  const area = findArea(normalized);
  const analysisId = `shade_${compactDate(timeWindow.start)}_${crypto
    .randomUUID()
    .slice(0, 8)}`;
  const generatedAt = formatZagrebIso(new Date());
  const mapPayload = buildMapPayload({
    analysisId,
    generatedAt,
    preference,
    area,
    period: timeWindow.period,
    start: timeWindow.start,
    end: timeWindow.end,
  });

  const record: AnalysisRecord = {
    analysis_id: analysisId,
    thread_id: threadId,
    created_at: generatedAt,
    expires_at: new Date(Date.now() + 60 * 60 * 1000).toISOString(),
    query: message,
    parsed_request: mapPayload.request,
    map_payload: mapPayload,
  };
  analysisStore.set(analysisId, record);

  const timeLabel = `${shortTime(mapPayload.request.start)}-${shortTime(
    mapPayload.request.end,
  )}`;
  const preferenceLabel =
    preference === "either"
      ? "outdoor"
      : preference === "shade"
        ? "shade-friendly"
        : "sunny";
  const answer = [
    `I found ${mapPayload.results.length} ${preferenceLabel} options near ${area.label} for ${timeLabel}.`,
    "Terrace points and exposure patterns are demo estimates, so treat timing as approximate.",
  ]
    .filter(Boolean)
    .join(" ");

  return {
    answer,
    thread_id: threadId,
    analysis_id: analysisId,
    map_payload: mapPayload,
    sources: mapPayload.source_notes,
    audio: null,
    detected_language: detectedLanguage,
  };
}

function buildMapPayload(input: {
  analysisId: string;
  generatedAt: string;
  preference: ExposurePreference;
  area: { label: string; center: LatLng };
  period: "morning" | "lunch" | "afternoon";
  start: string;
  end: string;
}): MapPayload {
  const ranked = seedCafes
    .map((cafe) => ({
      cafe,
      distance: distanceMeters(input.area.center, cafe.terrace_point),
    }))
    .sort((a, b) => a.distance - b.distance)
    .slice(0, 6)
    .map(({ cafe, distance }) => {
      const result = buildResult(
        cafe,
        input.preference,
        input.period,
        input.start,
        input.end,
      );
      return {
        result,
        rankScore:
          result.exposure.match_score * 0.6 +
          buildLocalityScore(distance, input.area.label, cafe.area) * 0.25 +
          buildAreaMatchScore(input.area.label, cafe.area) * 0.15,
      };
    })
    .sort((a, b) => b.rankScore - a.rankScore)
    .slice(0, 4)
    .map((item) => item.result);

  return {
    analysis_id: input.analysisId,
    generated_at: input.generatedAt,
    request: {
      preference: input.preference,
      location_label: input.area.label,
      start: input.start,
      end: input.end,
    },
    map: {
      center: input.area.center,
      zoom: 16,
    },
    results: ranked,
    source_notes: [
      "Demo cafe data from assets/split_cafe_seed.json.",
      "Terrace points are estimates for frontend/backend contract testing.",
      "Real backend should use Google Places, OpenStreetMap/Overpass, Astral/Shapely, and Open-Meteo.",
    ],
  };
}

function buildAreaMatchScore(requestedArea: string, cafeArea: string): number {
  return normalize(requestedArea).includes(normalize(cafeArea)) ? 1 : 0;
}

function buildLocalityScore(
  distance: number,
  requestedArea: string,
  cafeArea: string,
): number {
  const proximity = Math.max(0, 1 - distance / 900);
  const directAreaMatch = buildAreaMatchScore(requestedArea, cafeArea) * 0.25;
  return Math.min(1, proximity + directAreaMatch);
}

function buildResult(
  cafe: SeedCafe,
  preference: ExposurePreference,
  period: "morning" | "lunch" | "afternoon",
  start: string,
  end: string,
): MapPayloadResult {
  const pattern = cafe.patterns[period];
  const samples = buildSamples(start, end, pattern);
  const sunRatio =
    samples.filter((sample) => sample.state === "sun").length / samples.length;
  const matchScore =
    preference === "sun"
      ? sunRatio
      : preference === "shade"
        ? 1 - sunRatio
        : 0.72 + Math.min(sunRatio, 1 - sunRatio) * 0.2;
  const roundedScore = Number(matchScore.toFixed(2));
  const confidenceReasons = [
    "demo seed exposure pattern",
    cafe.outdoor_seating_confidence === "low"
      ? "terrace point estimated"
      : "outdoor seating inferred from seed data",
  ];

  return {
    id: cafe.id,
    name: cafe.name,
    provider: cafe.provider,
    location: cafe.location,
    terrace_point: cafe.terrace_point,
    address: cafe.address,
    google_maps_uri: `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(`${cafe.name} ${cafe.address}`)}`,
    rating: cafe.rating,
    user_rating_count: cafe.user_rating_count,
    is_open_for_window: true,
    outdoor_seating: {
      value: true,
      source: cafe.provider,
      confidence: cafe.outdoor_seating_confidence,
    },
    exposure: {
      preference,
      match_score: roundedScore,
      label:
        roundedScore >= 0.8
          ? "strong_match"
          : roundedScore >= 0.6
            ? "good_match"
            : "ok_match",
      summary: summarizeExposure(samples),
      sun_ratio: Number(sunRatio.toFixed(2)),
      samples,
      transition_notes: transitionNotes(samples),
      confidence: cafe.outdoor_seating_confidence === "low" ? "low" : "medium",
      confidence_reasons: confidenceReasons,
    },
    weather: {
      cloud_cover_avg: null,
      precipitation_probability_max: null,
    },
  };
}

function buildSamples(
  startIso: string,
  endIso: string,
  pattern: ExposureState[],
): ExposureSample[] {
  const start = parseLocalIso(startIso);
  const end = parseLocalIso(endIso);
  const count = Math.max(pattern.length, 2);
  const step = (end.getTime() - start.getTime()) / (count - 1);

  return Array.from({ length: count }, (_, index) => {
    const time = new Date(start.getTime() + step * index);
    return {
      time: formatZagrebIso(time),
      state: pattern[index % pattern.length],
    };
  });
}

function summarizeExposure(samples: ExposureSample[]): string {
  const sunCount = samples.filter((sample) => sample.state === "sun").length;
  const shadeCount = samples.length - sunCount;
  const start = shortTime(samples[0].time);
  const end = shortTime(samples[samples.length - 1].time);

  if (shadeCount === samples.length) {
    return `Mostly shaded from ${start} to ${end}.`;
  }

  if (sunCount === samples.length) {
    return `Mostly sunny from ${start} to ${end}.`;
  }

  if (shadeCount > sunCount) {
    return `Mostly shaded from ${start} to ${end}, with a short sunny patch.`;
  }

  return `Mostly sunny from ${start} to ${end}, with a short shaded patch.`;
}

function transitionNotes(samples: ExposureSample[]): string[] {
  const notes: string[] = [];
  for (let index = 1; index < samples.length; index += 1) {
    const previous = samples[index - 1];
    const current = samples[index];
    if (previous.state !== current.state) {
      notes.push(`${current.state} around ${shortTime(current.time)}`);
    }
  }
  return notes;
}

function parsePreference(query: string): ExposurePreference {
  if (/\b(shade|shady|shadow|cool|hlad|sjena|senka)\b/.test(query)) {
    return "shade";
  }

  if (/\b(sun|sunny|sunlight|direct sun|sunce|suncano)\b/.test(query)) {
    return "sun";
  }

  return "either";
}

function aliasMatches(query: string, alias: string): boolean {
  const s = alias.trim();
  if (!s) return false;
  if (s.includes(" ")) return query.includes(s);
  if (/\d/.test(s)) return query.includes(s);
  const escaped = s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  return new RegExp(`(?<![a-z0-9])${escaped}(?![a-z0-9])`).test(query);
}

function findArea(query: string): { label: string; center: LatLng } {
  return (
    SPLIT_AREAS.find((area) =>
      area.aliases.some((alias) => aliasMatches(query, alias)),
    ) ?? SPLIT_AREAS[0]
  );
}

function isOutsideSplit(query: string): boolean {
  return /\b(zagreb|tkalciceva|tkalca|dubrovnik|zadar|rijeka|pula)\b/.test(
    query,
  );
}

function parseTimeWindow(query: string): {
  start: string;
  end: string;
  period: "morning" | "lunch" | "afternoon";
} | null {
  const date = parseDateLabel(query);
  const explicit = query.match(
    /(?:from\s*)?(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\s*(?:-|to|until)\s*(\d{1,2})(?::(\d{2}))?\s*(am|pm)?/,
  );

  if (explicit) {
    const [
      ,
      rawStartHour,
      rawStartMinute,
      rawStartMeridiem,
      rawEndHour,
      rawEndMinute,
      rawEndMeridiem,
    ] = explicit;
    const endMeridiem = rawEndMeridiem as "am" | "pm" | undefined;
    const startMeridiem =
      (rawStartMeridiem as "am" | "pm" | undefined) ?? endMeridiem;
    const startHour = toHour24(Number(rawStartHour), startMeridiem);
    const endHour = toHour24(Number(rawEndHour), endMeridiem);
    const startMinute = Number(rawStartMinute ?? "0");
    const endMinute = Number(rawEndMinute ?? "0");
    const period =
      startHour < 12 ? "morning" : startHour < 14 ? "lunch" : "afternoon";

    return {
      start: localIso(date, startHour, startMinute),
      end: localIso(date, endHour, endMinute),
      period,
    };
  }

  if (query.includes("morning")) {
    return {
      start: localIso(date, 9, 0),
      end: localIso(date, 12, 0),
      period: "morning",
    };
  }

  if (query.includes("lunch")) {
    return {
      start: localIso(date, 12, 0),
      end: localIso(date, 14, 0),
      period: "lunch",
    };
  }

  if (query.includes("afternoon")) {
    return {
      start: localIso(date, 14, 0),
      end: localIso(date, 18, 0),
      period: "afternoon",
    };
  }

  return null;
}

function parseDateLabel(query: string): string {
  const today = zagrebDateParts(new Date());
  let date = new Date(Date.UTC(today.year, today.month - 1, today.day, 12));

  if (query.includes("tomorrow")) {
    date = addDays(date, 1);
  }

  const weekdayMatch = query.match(
    /\b(this\s+)?(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b/,
  );
  if (weekdayMatch) {
    const target = weekdayNumber(weekdayMatch[2]);
    const current = weekdayNumber(
      new Intl.DateTimeFormat("en-US", {
        timeZone: ZAGREB_TIME_ZONE,
        weekday: "long",
      })
        .format(new Date())
        .toLowerCase(),
    );
    let diff = (target - current + 7) % 7;
    const currentHour = zagrebDateParts(new Date()).hour;
    if (diff === 0 && currentHour >= 18) {
      diff = 7;
    }
    date = addDays(date, diff);
  }

  return date.toISOString().slice(0, 10);
}

function normalize(value: string): string {
  return value
    .toLowerCase()
    .normalize("NFD")
    .replace(/\p{Diacritic}/gu, "");
}

function localIso(date: string, hour: number, minute: number): string {
  return `${date}T${String(hour).padStart(2, "0")}:${String(minute).padStart(
    2,
    "0",
  )}:00${offsetForDate(date)}`;
}

function offsetForDate(date: string): string {
  const probe = new Date(`${date}T12:00:00Z`);
  const part = new Intl.DateTimeFormat("en-US", {
    timeZone: ZAGREB_TIME_ZONE,
    timeZoneName: "shortOffset",
  })
    .formatToParts(probe)
    .find((item) => item.type === "timeZoneName")?.value;
  const match = part?.match(/GMT([+-])(\d{1,2})(?::(\d{2}))?/);
  if (!match) {
    return "+01:00";
  }

  const [, sign, hour, minute = "00"] = match;
  return `${sign}${hour.padStart(2, "0")}:${minute.padStart(2, "0")}`;
}

function parseLocalIso(value: string): Date {
  return new Date(value);
}

function formatZagrebIso(date: Date): string {
  const parts = zagrebDateParts(date);
  const datePart = `${parts.year}-${String(parts.month).padStart(2, "0")}-${String(
    parts.day,
  ).padStart(2, "0")}`;
  return `${datePart}T${String(parts.hour).padStart(2, "0")}:${String(
    parts.minute,
  ).padStart(2, "0")}:00${offsetForDate(datePart)}`;
}

function zagrebDateParts(date: Date): {
  year: number;
  month: number;
  day: number;
  hour: number;
  minute: number;
} {
  const parts = new Intl.DateTimeFormat("en-GB", {
    timeZone: ZAGREB_TIME_ZONE,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  }).formatToParts(date);
  const get = (type: string) =>
    Number(parts.find((part) => part.type === type)?.value ?? "0");

  return {
    year: get("year"),
    month: get("month"),
    day: get("day"),
    hour: get("hour"),
    minute: get("minute"),
  };
}

function toHour24(hour: number, meridiem?: "am" | "pm"): number {
  if (!meridiem) {
    return hour;
  }

  if (meridiem === "pm" && hour < 12) {
    return hour + 12;
  }

  if (meridiem === "am" && hour === 12) {
    return 0;
  }

  return hour;
}

function weekdayNumber(day: string): number {
  return [
    "sunday",
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
  ].indexOf(day);
}

function addDays(date: Date, days: number): Date {
  const copy = new Date(date);
  copy.setUTCDate(copy.getUTCDate() + days);
  return copy;
}

function shortTime(iso: string): string {
  return iso.slice(11, 16);
}

function compactDate(iso: string): string {
  return iso.slice(0, 10).replaceAll("-", "");
}

function distanceMeters(a: LatLng, b: LatLng): number {
  const radius = 6371000;
  const dLat = toRad(b.lat - a.lat);
  const dLng = toRad(b.lng - a.lng);
  const lat1 = toRad(a.lat);
  const lat2 = toRad(b.lat);
  const h =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLng / 2) ** 2;
  return 2 * radius * Math.asin(Math.sqrt(h));
}

function toRad(value: number): number {
  return (value * Math.PI) / 180;
}
