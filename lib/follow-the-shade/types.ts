export type ExposurePreference = "sun" | "shade" | "either";
export type ExposureState = "sun" | "shade";
export type DetectedLanguage = string;
export type OutdoorSeatingConfidence = "high" | "medium" | "low" | "unknown";
export type VenueType = "cafe" | "restaurant" | "bar" | "night_club" | "venue";

export type ChatAudio = {
  mime_type: string;
  data: string;
};

export type LatLng = {
  lat: number;
  lng: number;
};

export type ChatRequest = {
  message: string;
  thread_id?: string;
  include_audio?: boolean;
};

export type ExposureSample = {
  time: string;
  state: ExposureState;
};

export type MapPayloadResult = {
  id: string;
  name: string;
  provider: string;
  venue_type?: VenueType;
  venue_types?: VenueType[];
  /** Neighborhood / micro-area when street-only address is unavailable. */
  area?: string;
  location: LatLng;
  terrace_point: LatLng;
  address: string;
  google_maps_uri?: string;
  place_photo_p?: string;
  rating?: number;
  user_rating_count?: number;
  is_open_for_window: boolean;
  outdoor_seating: {
    value: boolean | null;
    source: string;
    confidence: OutdoorSeatingConfidence;
  };
  exposure: {
    preference: ExposurePreference;
    match_score: number;
    label: "strong_match" | "good_match" | "ok_match";
    summary: string;
    sun_ratio: number;
    samples: ExposureSample[];
    transition_notes: string[];
    confidence: "high" | "medium" | "low";
    confidence_reasons: string[];
  };
  weather: {
    cloud_cover_avg: number | null;
    precipitation_probability_max: number | null;
    precipitation_mm_max?: number | null;
  };
};

export type MapPayload = {
  analysis_id: string;
  generated_at: string;
  request: {
    preference: ExposurePreference;
    venue_types?: VenueType[];
    location_label: string;
    start: string;
    end: string;
  };
  map: {
    center: LatLng;
    zoom: number;
  };
  results: MapPayloadResult[];
  source_notes: string[];
};

export type ChatResponse = {
  answer: string;
  thread_id: string;
  analysis_id: string | null;
  map_payload: MapPayload | null;
  sources: string[];
  audio: ChatAudio | null;
  detected_language: DetectedLanguage | null;
};

export type AnalysisRecord = {
  analysis_id: string;
  thread_id: string;
  created_at: string;
  expires_at: string;
  query: string;
  parsed_request: MapPayload["request"] | null;
  map_payload: MapPayload;
};

export type SeedCafe = {
  id: string;
  name: string;
  area: string;
  venue_type?: VenueType;
  venue_types?: VenueType[];
  provider: string;
  location: LatLng;
  terrace_point: LatLng;
  address: string;
  rating: number;
  user_rating_count: number;
  outdoor_seating_confidence: OutdoorSeatingConfidence;
  patterns: Record<"morning" | "lunch" | "afternoon", ExposureState[]>;
};
