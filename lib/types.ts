export type LngLat = [number, number];

export type Cafe = {
  id: string;
  name: string;
  neighborhood: string;
  blurb: string;
  lng: number;
  lat: number;
  google_maps_uri?: string;
  place_photo_p?: string;
};

export type SunPreference = "sun" | "shade" | "either";

export type IntentArea = {
  name: string;
  center: LngLat;
  radiusM: number;
  zoom: number;
};

export type IntentRequest = {
  id: string;
  utterance: string;
  preference: SunPreference;
  windowStart: Date;
  windowEnd: Date;
  area: IntentArea;
};

export type TimelinePoint = {
  t: Date;
  inSun: boolean;
};

export type CafeResult = {
  cafe: Cafe;
  timeline: TimelinePoint[];
  sunFraction: number;
  matches: boolean;
  nuance: string;
  headline: string;
};

export type AnalysisProgress = {
  stepIndex: number;
  totalSteps: number;
  currentTime: Date;
  cafesSampled: number;
  totalCafes: number;
};
