from __future__ import annotations

import json
import logging
import math
import re
import unicodedata
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Literal
from zoneinfo import ZoneInfo

from core.config import Settings
from services.geodata.overpass_client import OverpassClient
from services.places.google_places import GooglePlacesClient
from services.shadow.shadow_engine import (
    analyze_terrace_exposure,
    haversine_m,
)
from services.weather.open_meteo import OpenMeteoClient

log = logging.getLogger(__name__)

Preference = Literal["sun", "shade", "either"]
Period = Literal["morning", "lunch", "afternoon"]
Language = Literal["hr", "en", "it", "de", "sl", "fr"]
ZAGREB_TZ = ZoneInfo("Europe/Zagreb")


@dataclass(frozen=True)
class SplitArea:
    label: str
    aliases: tuple[str, ...]
    center: dict[str, float]


SPLIT_AREAS: tuple[SplitArea, ...] = (
    SplitArea("Riva, Split", ("riva", "old town", "central split"), {"lat": 43.5081, "lng": 16.4391}),
    SplitArea("Diocletian Palace, Split", ("diocletian", "palace", "pjaca", "peristil"), {"lat": 43.5086, "lng": 16.4409}),
    SplitArea("Marmontova, Split", ("marmontova",), {"lat": 43.5102, "lng": 16.4382}),
    SplitArea("Prokurative, Split", ("prokurative", "trg republike"), {"lat": 43.5095, "lng": 16.4370}),
    SplitArea("Matejuska, Split", ("matejuska",), {"lat": 43.5076, "lng": 16.4355}),
    SplitArea("Varos, Split", ("varos",), {"lat": 43.5094, "lng": 16.4336}),
    SplitArea("Bacvice, Split", ("bacvice", "bacvice beach"), {"lat": 43.5039, "lng": 16.4514}),
    SplitArea("Firule, Split", ("firule",), {"lat": 43.5019, "lng": 16.4592}),
    SplitArea("Znjan, Split", ("znjan",), {"lat": 43.5023, "lng": 16.4865}),
    SplitArea("West Coast, Split", ("west coast", "zapadna obala"), {"lat": 43.5063, "lng": 16.4323}),
    SplitArea("Sustipan, Split", ("sustipan",), {"lat": 43.5035, "lng": 16.4223}),
)


@dataclass(frozen=True)
class ParsedRequest:
    preference: Preference
    location_label: str
    center: dict[str, float]
    radius_m: int
    start: datetime | None
    end: datetime | None
    period: Period | None
    must_be_open: bool
    language: Language
    needs_clarification: bool = False
    clarification: str | None = None
    outside_split: bool = False


class FollowTheShadePipeline:
    def __init__(self, settings: Settings, seed_path: str) -> None:
        self.settings = settings
        self.seed_cafes = self._load_seed_cafes(seed_path)
        self.overpass = OverpassClient(settings.OVERPASS_URL)
        self.meteo = OpenMeteoClient(settings.OPEN_METEO_BASE_URL)
        self.places = (
            GooglePlacesClient(settings.GOOGLE_MAPS_API_KEY)
            if settings.GOOGLE_MAPS_API_KEY
            else None
        )

    async def run(self, *, query: str, thread_id: str) -> dict[str, Any]:
        parsed = self.parse_request(query)

        if parsed.outside_split:
            return self._redirect_split(thread_id, parsed.language)

        if parsed.needs_clarification or parsed.start is None or parsed.end is None:
            return {
                "answer": parsed.clarification or "What time window should I check?",
                "thread_id": thread_id,
                "analysis_id": None,
                "map_payload": None,
                "sources": [],
                "detected_language": parsed.language,
            }

        assert parsed.start and parsed.end

        cafes = await self._discover_cafes(parsed)
        if not cafes:
            return {
                "answer": (
                    f"I could not find outdoor cafes near {parsed.location_label}. "
                    "Try another Split area like Riva, Bacvice, or Marmontova."
                ),
                "thread_id": thread_id,
                "analysis_id": None,
                "map_payload": None,
                "sources": [],
                "detected_language": parsed.language,
            }

        buildings = await self.overpass.fetch_buildings(parsed.center, radius_m=450.0)
        height_estimated = any(b.height_confidence != "exact_tag" for b in buildings)
        weather = await self.meteo.window_weather(
            parsed.center["lat"],
            parsed.center["lng"],
            parsed.start,
            parsed.end,
        )

        results = []
        for cafe in cafes[:12]:
            terrace = await self._resolve_terrace(cafe, parsed.center)
            exposure = analyze_terrace_exposure(
                terrace_lat=terrace["lat"],
                terrace_lng=terrace["lng"],
                start=parsed.start,
                end=parsed.end,
                preference=parsed.preference,
                buildings=buildings,
                terrace_confidence=terrace["confidence"],
                height_estimates_used=height_estimated,
            )
            results.append(self._build_result(cafe, terrace, exposure, parsed, weather))

        ranked = sorted(
            results,
            key=lambda item: (
                item["exposure"]["match_score"] * 0.65
                + _locality_score(parsed.center, item["terrace_point"], parsed.location_label, item.get("area", "")) * 0.20
                + (item.get("rating") or 0) / 5.0 * 0.15
            ),
            reverse=True,
        )[:4]

        analysis_id = f"shade_{parsed.start:%Y%m%d}_{uuid.uuid4().hex[:8]}"
        source_notes = self._source_notes(buildings, height_estimated)
        map_payload = {
            "analysis_id": analysis_id,
            "generated_at": datetime.now(ZAGREB_TZ).isoformat(timespec="seconds"),
            "request": {
                "preference": parsed.preference,
                "location_label": parsed.location_label,
                "start": parsed.start.isoformat(timespec="seconds"),
                "end": parsed.end.isoformat(timespec="seconds"),
                "query": query,
            },
            "map": {"center": parsed.center, "zoom": 16},
            "results": ranked,
            "source_notes": source_notes,
        }

        best = ranked[:3]
        names = ", ".join(r["name"] for r in best)
        preference_label = "outdoor" if parsed.preference == "either" else parsed.preference
        weather_note = ""
        if weather.get("cloud_cover_avg") and weather["cloud_cover_avg"] > 60:
            weather_note = " Forecast cloud cover is high, so direct sun may feel weaker than the geometric analysis."
        answer = (
            f"Best {preference_label} matches near {parsed.location_label} for "
            f"{_short_time(parsed.start)}-{_short_time(parsed.end)}: {names}. "
            f"{best[0]['exposure']['summary']}{weather_note}"
        )

        return {
            "answer": answer,
            "thread_id": thread_id,
            "analysis_id": analysis_id,
            "map_payload": map_payload,
            "sources": source_notes,
            "detected_language": parsed.language,
        }

    async def _discover_cafes(self, parsed: ParsedRequest) -> list[dict[str, Any]]:
        if self.places:
            google_cafes = await self.places.nearby_cafes(
                parsed.center["lat"],
                parsed.center["lng"],
                radius_m=parsed.radius_m,
            )
            if google_cafes:
                return self._merge_seed_overrides(google_cafes)

        seed_in_area = [
            cafe
            for cafe in self.seed_cafes
            if haversine_m(parsed.center, cafe["terrace_point"]) <= parsed.radius_m
        ]
        seed_in_area.sort(key=lambda c: haversine_m(parsed.center, c["terrace_point"]))
        return seed_in_area[:12]

    def _merge_seed_overrides(self, cafes: list[dict[str, Any]]) -> list[dict[str, Any]]:
        merged = []
        for cafe in cafes:
            override = self._find_seed_override(cafe["name"])
            if override:
                cafe = {
                    **cafe,
                    "terrace_point": override["terrace_point"],
                    "outdoor_seating_confidence": override.get(
                        "outdoor_seating_confidence", "high"
                    ),
                    "area": override.get("area"),
                }
            merged.append(cafe)
        return merged

    async def _resolve_terrace(
        self, cafe: dict[str, Any], search_center: dict[str, float]
    ) -> dict[str, Any]:
        if cafe.get("outdoor_seating_confidence") == "high":
            return {
                "lat": cafe["terrace_point"]["lat"],
                "lng": cafe["terrace_point"]["lng"],
                "confidence": "high",
            }

        seating = await self.overpass.fetch_outdoor_seating_near(
            cafe["location"], radius_m=35.0
        )
        if seating:
            closest = min(
                seating,
                key=lambda item: haversine_m(cafe["location"], item),
            )
            return {
                "lat": closest["lat"],
                "lng": closest["lng"],
                "confidence": "medium",
            }

        if cafe.get("outdoor_seating") is True or cafe.get("provider") == "demo_seed":
            ring = _ring_point(cafe["location"], bearing_deg=45.0, distance_m=8.0)
            return {**ring, "confidence": "medium"}

        return {
            "lat": cafe["terrace_point"]["lat"],
            "lng": cafe["terrace_point"]["lng"],
            "confidence": "low",
        }

    def _build_result(
        self,
        cafe: dict[str, Any],
        terrace: dict[str, Any],
        exposure: Any,
        parsed: ParsedRequest,
        weather: dict[str, Any],
    ) -> dict[str, Any]:
        score = exposure.match_score
        return {
            "id": cafe["id"],
            "name": cafe["name"],
            "provider": cafe.get("provider", "unknown"),
            "area": cafe.get("area"),
            "location": cafe["location"],
            "terrace_point": {"lat": terrace["lat"], "lng": terrace["lng"]},
            "address": cafe.get("address"),
            "google_maps_uri": cafe.get("google_maps_uri"),
            "rating": cafe.get("rating"),
            "user_rating_count": cafe.get("user_rating_count"),
            "is_open_for_window": True,
            "outdoor_seating": {
                "value": cafe.get("outdoor_seating", True)
                if cafe.get("outdoor_seating") is not False
                else False,
                "source": cafe.get("provider", "unknown"),
                "confidence": terrace["confidence"],
            },
            "exposure": {
                "preference": parsed.preference,
                "match_score": score,
                "label": "strong_match"
                if score >= 0.8
                else "good_match"
                if score >= 0.6
                else "ok_match",
                "summary": exposure.summary,
                "sun_ratio": exposure.sun_ratio,
                "samples": [
                    {"time": s.time.isoformat(timespec="seconds"), "state": s.state}
                    for s in exposure.samples
                ],
                "transition_notes": exposure.transition_notes,
                "confidence": exposure.confidence,
                "confidence_reasons": exposure.confidence_reasons,
            },
            "weather": weather,
        }

    def _source_notes(self, buildings: list[Any], height_estimated: bool) -> list[str]:
        notes = []
        if self.places:
            notes.append("Cafe data from Google Places.")
        else:
            notes.append("Cafe data from assets/split_cafe_seed.json.")
        if buildings:
            notes.append("Building geometry from OpenStreetMap/Overpass.")
            if height_estimated:
                notes.append("Building heights estimated where OSM height tags were missing.")
        else:
            notes.append("Limited building geometry; exposure uses sun position with low shadow confidence.")
        notes.append("Weather from Open-Meteo.")
        return notes

    def _redirect_split(self, thread_id: str, language: Language) -> dict[str, Any]:
        return {
            "answer": (
                "I'm focused on Split. Do you want something around Riva, "
                "Bacvice, Marmontova, Varos, or another Split area?"
            ),
            "thread_id": thread_id,
            "analysis_id": None,
            "map_payload": None,
            "sources": [],
            "detected_language": language,
        }

    def _load_seed_cafes(self, seed_path: str) -> list[dict[str, Any]]:
        path = Path(seed_path)
        if not path.is_absolute():
            path = Path.cwd() / path
        with path.open("r", encoding="utf-8") as seed_file:
            raw = json.load(seed_file)
        cafes = []
        for entry in raw:
            cafes.append(
                {
                    "id": entry["id"],
                    "name": entry["name"],
                    "area": entry.get("area"),
                    "provider": entry.get("provider", "demo_seed"),
                    "location": entry["location"],
                    "terrace_point": entry["terrace_point"],
                    "address": entry.get("address"),
                    "rating": entry.get("rating"),
                    "user_rating_count": entry.get("user_rating_count"),
                    "outdoor_seating": True,
                    "outdoor_seating_confidence": entry.get(
                        "outdoor_seating_confidence", "high"
                    ),
                    "google_maps_uri": entry.get("google_maps_uri"),
                }
            )
        return cafes

    def parse_request(self, query: str, now: datetime | None = None) -> ParsedRequest:
        normalized = self._normalize(query)
        now_zagreb = (now or datetime.now(ZAGREB_TZ)).astimezone(ZAGREB_TZ)
        language = _detect_language(normalized)

        if re.search(r"\b(zagreb|tkalciceva|tkalca|dubrovnik|zadar|rijeka|pula)\b", normalized):
            return ParsedRequest(
                preference=_parse_preference(normalized),
                location_label=SPLIT_AREAS[0].label,
                center=SPLIT_AREAS[0].center,
                radius_m=900,
                start=None,
                end=None,
                period=None,
                must_be_open=True,
                language=language,
                outside_split=True,
            )

        area = _find_area(normalized)
        time_window = _parse_time_window(normalized, now_zagreb)
        if time_window is None:
            return ParsedRequest(
                preference=_parse_preference(normalized),
                location_label=area.label,
                center=area.center,
                radius_m=900,
                start=None,
                end=None,
                period=None,
                must_be_open=True,
                language=language,
                needs_clarification=True,
                clarification=(
                    "What time window should I check? For example: today from "
                    "3 to 5pm, tomorrow morning, or this Saturday afternoon."
                ),
            )

        start, end, period = time_window
        return ParsedRequest(
            preference=_parse_preference(normalized),
            location_label=area.label,
            center=area.center,
            radius_m=900,
            start=start,
            end=end,
            period=period,
            must_be_open=True,
            language=language,
        )

    @staticmethod
    def _normalize(value: str) -> str:
        stripped = unicodedata.normalize("NFD", value.lower())
        return "".join(ch for ch in stripped if unicodedata.category(ch) != "Mn")

    @staticmethod
    def _normalize_name(value: str) -> str:
        return FollowTheShadePipeline._normalize(value)

    def _find_seed_override(self, name: str) -> dict[str, Any] | None:
        norm = self._normalize_name(name)
        for seed in self.seed_cafes:
            seed_norm = self._normalize_name(seed["name"])
            if seed_norm in norm or norm in seed_norm:
                return seed
        return None


def _ring_point(center: dict[str, float], bearing_deg: float, distance_m: float) -> dict[str, float]:
    bearing = math.radians(bearing_deg)
    lat_rad = math.radians(center["lat"])
    lng_rad = math.radians(center["lng"])
    angular = distance_m / 6371000.0
    lat2 = math.asin(
        math.sin(lat_rad) * math.cos(angular)
        + math.cos(lat_rad) * math.sin(angular) * math.cos(bearing)
    )
    lng2 = lng_rad + math.atan2(
        math.sin(bearing) * math.sin(angular) * math.cos(lat_rad),
        math.cos(angular) - math.sin(lat_rad) * math.sin(lat2),
    )
    return {"lat": math.degrees(lat2), "lng": math.degrees(lng2)}


def _locality_score(
    center: dict[str, float],
    terrace: dict[str, float],
    requested_area: str,
    cafe_area: str,
) -> float:
    distance = haversine_m(center, terrace)
    proximity = max(0.0, 1.0 - distance / 900.0)
    area_bonus = 0.25 if cafe_area and cafe_area.lower() in requested_area.lower() else 0.0
    return min(1.0, proximity + area_bonus)


def _parse_preference(query: str) -> Preference:
    if re.search(r"\b(shade|shady|shadow|cool|hlad|sjena|senka)\b", query):
        return "shade"
    if re.search(r"\b(sun|sunny|sunlight|direct sun|sunce|suncano)\b", query):
        return "sun"
    return "either"


def _find_area(query: str) -> SplitArea:
    for area in SPLIT_AREAS:
        if any(alias in query for alias in area.aliases):
            return area
    return SPLIT_AREAS[0]


def _parse_time_window(
    query: str,
    now: datetime,
) -> tuple[datetime, datetime, Period] | None:
    date = _parse_date(query, now)
    explicit = re.search(
        r"(?:from\s*)?(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\s*(?:-|to|until)\s*(\d{1,2})(?::(\d{2}))?\s*(am|pm)?",
        query,
    )
    if explicit:
        raw_start_hour, raw_start_minute, start_meridiem, raw_end_hour, raw_end_minute, end_meridiem = explicit.groups()
        start_meridiem = start_meridiem or end_meridiem
        start_hour = _to_hour_24(int(raw_start_hour), start_meridiem)
        end_hour = _to_hour_24(int(raw_end_hour), end_meridiem)
        start = datetime(
            date.year,
            date.month,
            date.day,
            start_hour,
            int(raw_start_minute or 0),
            tzinfo=ZAGREB_TZ,
        )
        end = datetime(
            date.year,
            date.month,
            date.day,
            end_hour,
            int(raw_end_minute or 0),
            tzinfo=ZAGREB_TZ,
        )
        period: Period = "morning" if start_hour < 12 else "lunch" if start_hour < 14 else "afternoon"
        return start, end, period

    if "morning" in query:
        return _window(date, 9, 12, "morning")
    if "lunch" in query:
        return _window(date, 12, 14, "lunch")
    if "afternoon" in query:
        return _window(date, 14, 18, "afternoon")
    return None


def _parse_date(query: str, now: datetime) -> datetime:
    date = now
    if "tomorrow" in query:
        date = date + timedelta(days=1)
    weekday_match = re.search(
        r"\b(this\s+)?(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
        query,
    )
    if weekday_match:
        target = _weekday_number(weekday_match.group(2))
        diff = (target - date.weekday()) % 7
        if diff == 0 and now.hour >= 18:
            diff = 7
        date = now + timedelta(days=diff)
    return date


def _window(date: datetime, start_hour: int, end_hour: int, period: Period):
    return (
        datetime(date.year, date.month, date.day, start_hour, tzinfo=ZAGREB_TZ),
        datetime(date.year, date.month, date.day, end_hour, tzinfo=ZAGREB_TZ),
        period,
    )


def _weekday_number(day: str) -> int:
    return {
        "monday": 0,
        "tuesday": 1,
        "wednesday": 2,
        "thursday": 3,
        "friday": 4,
        "saturday": 5,
        "sunday": 6,
    }[day]


def _to_hour_24(hour: int, meridiem: str | None) -> int:
    if meridiem == "pm" and hour < 12:
        return hour + 12
    if meridiem == "am" and hour == 12:
        return 0
    return hour


def _detect_language(query: str) -> Language:
    if re.search(r"\b(ciao|ombra|sole|terrazza)\b", query):
        return "it"
    if re.search(r"\b(schatten|sonne|kaffee)\b", query):
        return "de"
    if re.search(r"\b(hlad|sunce|kava|terasa)\b", query):
        return "hr"
    return "en"


def _short_time(value: datetime) -> str:
    return value.strftime("%H:%M")
