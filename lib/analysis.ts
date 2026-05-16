import type { MapPanelHandle } from "@/components/MapPanel";
import type {
  AnalysisProgress,
  Cafe,
  CafeResult,
  IntentRequest,
  SunPreference,
  TimelinePoint,
} from "./types";
import { formatRoughClock } from "./format";

const STEP_MINUTES = 10;

const distanceMeters = (a: [number, number], b: [number, number]): number => {
  const R = 6371000;
  const toRad = (d: number) => (d * Math.PI) / 180;
  const dLat = toRad(b[1] - a[1]);
  const dLng = toRad(b[0] - a[0]);
  const lat1 = toRad(a[1]);
  const lat2 = toRad(b[1]);
  const h =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLng / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(h));
};

export const candidateCafes = (cafes: Cafe[], intent: IntentRequest): Cafe[] =>
  cafes.filter(
    (c) =>
      distanceMeters([c.lng, c.lat], intent.area.center) <= intent.area.radiusM,
  );

export const buildTimeSteps = (intent: IntentRequest): Date[] => {
  const steps: Date[] = [];
  const stepMs = STEP_MINUTES * 60 * 1000;
  for (
    let t = intent.windowStart.getTime();
    t <= intent.windowEnd.getTime();
    t += stepMs
  ) {
    steps.push(new Date(t));
  }
  return steps;
};

const buildNuance = (
  timeline: TimelinePoint[],
  sunFraction: number,
  preference: SunPreference,
): string => {
  if (timeline.length < 2) return "";

  if (sunFraction >= 0.92) {
    return preference === "sun"
      ? "blazing sun the entire window"
      : "no shade at all — bring a hat";
  }
  if (sunFraction <= 0.08) {
    return preference === "shade"
      ? "deep shade the entire window"
      : "fully shaded — won't see the sun";
  }

  let firstFlipIdx = -1;
  for (let i = 1; i < timeline.length; i++) {
    if (timeline[i].inSun !== timeline[i - 1].inSun) {
      firstFlipIdx = i;
      break;
    }
  }

  if (firstFlipIdx === -1) {
    return sunFraction > 0.5 ? "sunny throughout" : "shaded throughout";
  }

  const flipPoint = timeline[firstFlipIdx];
  const flippingInto = flipPoint.inSun ? "sun" : "shade";
  return `${flippingInto === "sun" ? "shaded" : "sunny"} until around ${formatRoughClock(flipPoint.t)}, then ${flippingInto}`;
};

const buildHeadline = (sunFraction: number): string => {
  if (sunFraction >= 0.85) return "full sun";
  if (sunFraction >= 0.6) return "mostly sun";
  if (sunFraction >= 0.4) return "split sun & shade";
  if (sunFraction >= 0.15) return "mostly shade";
  return "deep shade";
};

const matchesPreference = (
  sunFraction: number,
  preference: SunPreference,
): boolean =>
  preference === "sun"
    ? sunFraction >= 0.7
    : preference === "shade"
      ? sunFraction <= 0.3
      : true;

export type AnalysisArgs = {
  map: MapPanelHandle;
  intent: IntentRequest;
  cafes: Cafe[];
  onProgress: (progress: AnalysisProgress) => void;
};

export const runShadowAnalysis = async ({
  map,
  intent,
  cafes,
  onProgress,
}: AnalysisArgs): Promise<CafeResult[]> => {
  const steps = buildTimeSteps(intent);
  const candidates = candidateCafes(cafes, intent);

  const timelines = new Map<string, TimelinePoint[]>();
  candidates.forEach((c) => timelines.set(c.id, []));

  for (let s = 0; s < steps.length; s++) {
    const t = steps[s];
    await map.setShadeDate(t);
    await new Promise<void>((r) => requestAnimationFrame(() => r()));

    let sampled = 0;
    for (const cafe of candidates) {
      const inSun = await map.sampleSun(cafe.lng, cafe.lat);
      timelines.get(cafe.id)?.push({ t, inSun });
      sampled++;
      onProgress({
        stepIndex: s,
        totalSteps: steps.length,
        currentTime: t,
        cafesSampled: sampled,
        totalCafes: candidates.length,
      });
    }
  }

  const results: CafeResult[] = candidates.map((cafe) => {
    const timeline = timelines.get(cafe.id) ?? [];
    const sunCount = timeline.filter((p) => p.inSun).length;
    const sunFraction = timeline.length ? sunCount / timeline.length : 0;
    return {
      cafe,
      timeline,
      sunFraction,
      matches: matchesPreference(sunFraction, intent.preference),
      nuance: buildNuance(timeline, sunFraction, intent.preference),
      headline: buildHeadline(sunFraction),
    };
  });

  return results;
};
