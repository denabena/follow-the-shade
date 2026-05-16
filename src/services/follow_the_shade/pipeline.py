from __future__ import annotations

import json
import logging
import math
import re
import unicodedata
import uuid
import asyncio
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from pathlib import Path
from threading import Lock
from typing import Any, Literal
from zoneinfo import ZoneInfo

from core.config import Settings
from services.follow_the_shade.address_display import format_address_for_display
from services.follow_the_shade.cache import TtlCache
from services.follow_the_shade.data_sources import (
    BuildingSummary,
    CafeCandidateBundle,
    FollowTheShadeDataSources,
    WeatherSummary,
)
from services.geodata.overpass_client import OverpassClient
from services.places.google_places import GooglePlacesClient
from services.places.photo_token import place_photo_p_from_cafe
from services.shadow.shadow_engine import (
    ExposureResult,
    ExposureSample,
    analyze_terrace_exposure,
    haversine_m,
)
from services.weather.open_meteo import OpenMeteoClient

log = logging.getLogger(__name__)

Preference = Literal["sun", "shade", "either"]
Period = Literal["morning", "lunch", "afternoon"]
Language = Literal["en"]
ZAGREB_TZ = ZoneInfo("Europe/Zagreb")


@dataclass(frozen=True)
class SplitArea:
    label: str
    aliases: tuple[str, ...]
    center: dict[str, float]


SPLIT_AREAS: tuple[SplitArea, ...] = (
    SplitArea(
        "Riva, Split",
        (
            "riva",
            "old town",
            "central split",
            "city center",
            "city centre",
            "center split",
            "centre split",
            "center",
            "centre",
        ),
        {"lat": 43.5081, "lng": 16.4391},
    ),
    SplitArea(
        "Diocletian Palace, Split",
        ("diocletian", "palace", "pjaca", "peristil"),
        {"lat": 43.5086, "lng": 16.4409},
    ),
    SplitArea("Grad, Split", ("split grad",), {"lat": 43.5088, "lng": 16.4405}),
    SplitArea("Marmontova, Split", ("marmontova",), {"lat": 43.5102, "lng": 16.4382}),
    SplitArea(
        "Prokurative, Split",
        ("prokurative", "trg republike"),
        {"lat": 43.5095, "lng": 16.4370},
    ),
    SplitArea("Matejuska, Split", ("matejuska",), {"lat": 43.5076, "lng": 16.4355}),
    SplitArea(
        "Varos, Split",
        ("varos", "veli varos"),
        {"lat": 43.5094, "lng": 16.4336},
    ),
    SplitArea(
        "Lučac-Manuš, Split",
        ("lucac-manus", "lucac manus", "lucac", "manus"),
        {"lat": 43.5064, "lng": 16.4368},
    ),
    SplitArea(
        "West Coast, Split",
        ("west coast", "zapadna obala"),
        {"lat": 43.5063, "lng": 16.4323},
    ),
    SplitArea(
        "Marjan, Split",
        ("marjan", "vidilica", "telegrin"),
        {"lat": 43.5142, "lng": 16.4275},
    ),
    SplitArea("Kasjuni, Split", ("kasjuni",), {"lat": 43.5088, "lng": 16.4187}),
    SplitArea(
        "Poljud, Split",
        ("poljud",),
        {"lat": 43.51944, "lng": 16.43167},
    ),
    SplitArea("Spinut, Split", ("spinut",), {"lat": 43.5175, "lng": 16.4178}),
    SplitArea("Meje, Split", ("meje",), {"lat": 43.5138, "lng": 16.4078}),
    SplitArea("Sustipan, Split", ("sustipan",), {"lat": 43.5035, "lng": 16.4223}),
    SplitArea(
        "Bol, Split",
        ("bol",),
        {"lat": 43.5032, "lng": 16.4265},
    ),
    SplitArea(
        "Bacvice, Split",
        ("bacvice", "bacvice beach"),
        {"lat": 43.5039, "lng": 16.4514},
    ),
    SplitArea("Firule, Split", ("firule",), {"lat": 43.5019, "lng": 16.4592}),
    SplitArea("Lovret, Split", ("lovret",), {"lat": 43.5048, "lng": 16.4478}),
    SplitArea("Znjan, Split", ("znjan",), {"lat": 43.5023, "lng": 16.4865}),
    SplitArea("Trstenik, Split", ("trstenik",), {"lat": 43.5078, "lng": 16.4635}),
    SplitArea("Mertojak, Split", ("mertojak",), {"lat": 43.5076, "lng": 16.4545}),
    SplitArea(
        "Blatine-Škrape, Split",
        ("blatine-skrape", "blatine skrape", "blatine", "skrape"),
        {"lat": 43.5132, "lng": 16.4668},
    ),
    SplitArea(
        "Split 3, Split",
        ("split 3", "treca cetvrt", "third district"),
        {"lat": 43.5112, "lng": 16.4705},
    ),
    SplitArea("Pujanke, Split", ("pujanke",), {"lat": 43.5163, "lng": 16.4737}),
    SplitArea("Sućidar, Split", ("sucidar",), {"lat": 43.5196, "lng": 16.4675}),
    SplitArea("Visoka, Split", ("visoka",), {"lat": 43.5216, "lng": 16.4578}),
    SplitArea("Lokve, Split", ("lokve",), {"lat": 43.5178, "lng": 16.4488}),
    SplitArea("Gripe, Split", ("gripe",), {"lat": 43.5195, "lng": 16.4412}),
    SplitArea("Plokite, Split", ("plokite",), {"lat": 43.5146, "lng": 16.4395}),
    SplitArea("Kopilica, Split", ("kopilica",), {"lat": 43.5238, "lng": 16.4328}),
    SplitArea("Kman, Split", ("kman",), {"lat": 43.5248, "lng": 16.4468}),
    SplitArea(
        "Ravne njive, Split",
        ("ravne njive", "ravne"),
        {"lat": 43.5295, "lng": 16.4638},
    ),
    SplitArea("Brda, Split", ("brda",), {"lat": 43.5348, "lng": 16.4725}),
    SplitArea("Kocunar, Split", ("kocunar",), {"lat": 43.5148, "lng": 16.4798}),
    SplitArea("Neslanovac, Split", ("neslanovac",), {"lat": 43.5395, "lng": 16.4878}),
    SplitArea("Mejaši, Split", ("mejasi",), {"lat": 43.5428, "lng": 16.4978}),
    SplitArea("Sirobuja, Split", ("sirobuja",), {"lat": 43.5078, "lng": 16.5028}),
    SplitArea("Šine, Split", ("sine",), {"lat": 43.5298, "lng": 16.4395}),
    SplitArea("Brodarica, Split", ("brodarica",), {"lat": 43.4998, "lng": 16.4688}),
    SplitArea("Stobreč, Split", ("stobrec",), {"lat": 43.5036, "lng": 16.5748}),
    SplitArea("Podstrana, Split", ("podstrana",), {"lat": 43.4888, "lng": 16.5585}),
    SplitArea("Solin, Split", ("solin",), {"lat": 43.5442, "lng": 16.4928}),
    SplitArea("Klis, Split", ("klis",), {"lat": 43.5588, "lng": 16.5228}),
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
    date_anchor: datetime | None = None
    needs_clarification: bool = False
    clarification: str | None = None
    outside_split: bool = False
    preference_explicit: bool = False
    location_explicit: bool = False
    time_explicit: bool = False
    date_explicit: bool = False


class FollowTheShadePipeline:
    def __init__(
        self,
        settings: Settings,
        seed_path: str,
        *,
        cache: TtlCache | None = None,
        data_sources: FollowTheShadeDataSources | None = None,
    ) -> None:
        self.settings = settings
        self.seed_cafes = self._load_seed_cafes(seed_path)
        self.overpass = OverpassClient(settings.OVERPASS_URL)
        self.meteo = OpenMeteoClient(settings.OPEN_METEO_BASE_URL)
        places_api_key = settings.GOOGLE_PLACES_API_KEY or settings.GOOGLE_MAPS_API_KEY
        self.places = (
            GooglePlacesClient(places_api_key) if places_api_key is not None else None
        )
        self.data_sources = data_sources or FollowTheShadeDataSources(
            settings=settings,
            seed_cafes=self.seed_cafes,
            cache=cache
            or TtlCache(ttl_seconds=settings.FOLLOW_THE_SHADE_CACHE_TTL_SECONDS),
        )
        self._thread_context: dict[str, ParsedRequest] = {}
        self._thread_context_lock = Lock()

    async def run(self, *, query: str, thread_id: str) -> dict[str, Any]:
        parsed = self.parse_request(query)

        if not parsed.outside_split:
            parsed = self._merge_with_thread_context(thread_id, parsed)

        if parsed.outside_split:
            return self._redirect_split(thread_id, parsed.language)

        if parsed.needs_clarification or parsed.start is None or parsed.end is None:
            self._remember_thread_context(thread_id, parsed)
            return {
                "answer": parsed.clarification or "What time window should I check?",
                "thread_id": thread_id,
                "analysis_id": None,
                "map_payload": None,
                "sources": [],
                "detected_language": parsed.language,
            }

        assert parsed.start and parsed.end

        cafe_bundle = await self.data_sources.cafe_candidates(
            center=parsed.center,
            radius_m=parsed.radius_m,
            limit=12,
        )
        cafes = cafe_bundle.cafes
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

        building_task = self.data_sources.building_summary(
            center=parsed.center,
            radius_m=450,
        )
        weather_task = self.data_sources.weather_summary(
            center=parsed.center,
            start=parsed.start,
            end=parsed.end,
        )
        outdoor_seating_task = self.data_sources.outdoor_seating_summary(
            center=parsed.center,
            radius_m=parsed.radius_m,
        )
        building_summary, weather_summary, outdoor_seating_summary = (
            await asyncio.gather(
                building_task,
                weather_task,
                outdoor_seating_task,
            )
        )
        buildings = building_summary.buildings
        height_estimated = building_summary.height_estimates_used
        weather = weather_summary.to_result_weather()

        results = []
        for cafe in cafes[:12]:
            terrace = self._resolve_terrace(
                cafe,
                parsed.center,
                outdoor_seating_summary.points,
            )
            exposure = self._analyze_cafe_exposure(
                cafe=cafe,
                terrace=terrace,
                parsed=parsed,
                buildings=buildings,
                height_estimated=height_estimated,
            )
            exposure = _weather_adjusted_exposure(exposure, parsed, weather)
            results.append(self._build_result(cafe, terrace, exposure, parsed, weather))

        ranked = sorted(
            results,
            key=lambda item: (
                item["exposure"]["match_score"] * 0.65
                + _locality_score(
                    parsed.center,
                    item["terrace_point"],
                    parsed.location_label,
                    item.get("area", ""),
                )
                * 0.20
                + (item.get("rating") or 0) / 5.0 * 0.15
            ),
            reverse=True,
        )[:4]

        analysis_id = f"shade_{parsed.start:%Y%m%d}_{uuid.uuid4().hex[:8]}"
        source_notes = self._source_notes(
            cafe_bundle,
            building_summary,
            weather_summary,
            outdoor_seating_summary,
        )
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
        answer_facts = _build_answer_facts(
            parsed=parsed,
            ranked=ranked,
            weather=weather,
            source_notes=source_notes,
        )
        self._remember_thread_context(thread_id, parsed)

        weather_blocks_direct_sun = _weather_blocks_direct_sun(weather)
        preference_label = (
            "outdoor"
            if parsed.preference == "either"
            or (parsed.preference == "sun" and weather_blocks_direct_sun)
            else parsed.preference
        )
        weather_note = _weather_answer_note(weather)
        answer = (
            f"I found {len(ranked)} {preference_label} options near "
            f"{parsed.location_label} for "
            f"{_short_time(parsed.start)}-{_short_time(parsed.end)}."
            f"{weather_note}"
        )

        return {
            "answer": answer,
            "thread_id": thread_id,
            "analysis_id": analysis_id,
            "answer_facts": answer_facts,
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

    def _merge_seed_overrides(
        self, cafes: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
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

    def _resolve_terrace(
        self,
        cafe: dict[str, Any],
        search_center: dict[str, float],
        outdoor_seating_points: list[dict[str, Any]],
    ) -> dict[str, Any]:
        if cafe.get("outdoor_seating_confidence") == "high":
            return {
                "lat": cafe["terrace_point"]["lat"],
                "lng": cafe["terrace_point"]["lng"],
                "confidence": "high",
            }

        if self.data_sources.data_mode == "mock":
            confidence = cafe.get("outdoor_seating_confidence") or "medium"
            return {
                "lat": cafe["terrace_point"]["lat"],
                "lng": cafe["terrace_point"]["lng"],
                "confidence": (
                    confidence if confidence in {"high", "medium", "low"} else "medium"
                ),
            }

        seating = [
            point
            for point in outdoor_seating_points
            if haversine_m(cafe["location"], point) <= 35.0
        ]
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

        if cafe.get("provider") == "google_places":
            ring = _ring_point(cafe["location"], bearing_deg=45.0, distance_m=8.0)
            return {**ring, "confidence": "low"}

        return {
            "lat": cafe["terrace_point"]["lat"],
            "lng": cafe["terrace_point"]["lng"],
            "confidence": "low",
        }

    def _analyze_cafe_exposure(
        self,
        *,
        cafe: dict[str, Any],
        terrace: dict[str, Any],
        parsed: ParsedRequest,
        buildings: list[Any],
        height_estimated: bool,
    ) -> ExposureResult:
        if _should_use_seed_pattern(self.data_sources.data_mode, cafe, buildings):
            return _pattern_exposure(cafe, parsed, terrace["confidence"])

        assert parsed.start and parsed.end
        return analyze_terrace_exposure(
            terrace_lat=terrace["lat"],
            terrace_lng=terrace["lng"],
            start=parsed.start,
            end=parsed.end,
            preference=parsed.preference,
            buildings=buildings,
            terrace_confidence=terrace["confidence"],
            height_estimates_used=height_estimated,
        )

    def _build_result(
        self,
        cafe: dict[str, Any],
        terrace: dict[str, Any],
        exposure: Any,
        parsed: ParsedRequest,
        weather: dict[str, Any],
    ) -> dict[str, Any]:
        score = exposure.match_score
        raw_addr = cafe.get("address")
        if isinstance(raw_addr, str) and raw_addr.strip():
            normalized_addr = format_address_for_display(raw_addr)
            display_address = (
                normalized_addr if normalized_addr else (cafe.get("area") or "")
            )
        else:
            display_address = raw_addr
        return {
            "id": cafe["id"],
            "name": cafe["name"],
            "provider": cafe.get("provider", "unknown"),
            "area": cafe.get("area"),
            "location": cafe["location"],
            "terrace_point": {"lat": terrace["lat"], "lng": terrace["lng"]},
            "address": display_address,
            "google_maps_uri": cafe.get("google_maps_uri"),
            "place_photo_p": place_photo_p_from_cafe(cafe),
            "rating": cafe.get("rating"),
            "user_rating_count": cafe.get("user_rating_count"),
            "is_open_for_window": cafe.get("is_open_for_window", True),
            "outdoor_seating": {
                "value": (
                    cafe.get("outdoor_seating", True)
                    if cafe.get("outdoor_seating") is not False
                    else False
                ),
                "source": cafe.get("provider", "unknown"),
                "confidence": terrace["confidence"],
            },
            "exposure": {
                "preference": parsed.preference,
                "match_score": score,
                "label": (
                    "strong_match"
                    if score >= 0.8
                    else "good_match" if score >= 0.6 else "ok_match"
                ),
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

    def _source_notes(
        self,
        cafe_bundle: CafeCandidateBundle,
        building_summary: BuildingSummary,
        weather_summary: WeatherSummary,
        outdoor_seating_summary: Any,
    ) -> list[str]:
        notes = [
            *cafe_bundle.source_notes,
            *building_summary.source_notes,
            *weather_summary.source_notes,
            *outdoor_seating_summary.source_notes,
            *cafe_bundle.uncertainty_notes,
            *building_summary.uncertainty_notes,
            *weather_summary.uncertainty_notes,
            *outdoor_seating_summary.uncertainty_notes,
        ]
        unique_notes = []
        for note in notes:
            if note and note not in unique_notes:
                unique_notes.append(note)
        return unique_notes or [
            "Cafe and exposure data from Follow the Shade seed data."
        ]

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
                    "place_photo_p": entry.get("place_photo_p"),
                    "patterns": entry.get("patterns", {}),
                }
            )
        return cafes

    def _merge_with_thread_context(
        self,
        thread_id: str,
        parsed: ParsedRequest,
    ) -> ParsedRequest:
        previous = self._get_thread_context(thread_id)
        if previous is None or previous.outside_split:
            return parsed

        updates: dict[str, Any] = {}
        if not parsed.preference_explicit and previous.preference != "either":
            updates["preference"] = previous.preference
            updates["preference_explicit"] = previous.preference_explicit

        if not parsed.location_explicit:
            updates["location_label"] = previous.location_label
            updates["center"] = previous.center
            updates["radius_m"] = previous.radius_m
            updates["location_explicit"] = previous.location_explicit

        if (
            parsed.time_explicit
            and not parsed.date_explicit
            and previous.date_explicit
            and previous.date_anchor is not None
        ):
            updates["date_anchor"] = previous.date_anchor
            updates["date_explicit"] = previous.date_explicit
            if parsed.start is not None and parsed.end is not None:
                updates["start"] = _move_time_window_to_date(
                    parsed.start,
                    previous.date_anchor,
                )
                updates["end"] = _move_time_window_to_date(
                    parsed.end,
                    previous.date_anchor,
                )

        if (
            not parsed.time_explicit
            and previous.start is not None
            and previous.end is not None
        ):
            if parsed.date_explicit and parsed.date_anchor is not None:
                updates["start"] = _move_time_window_to_date(
                    previous.start,
                    parsed.date_anchor,
                )
                updates["end"] = _move_time_window_to_date(
                    previous.end,
                    parsed.date_anchor,
                )
            else:
                updates["start"] = previous.start
                updates["end"] = previous.end
            updates["period"] = previous.period
            updates["time_explicit"] = previous.time_explicit

        if updates.get("start") is not None and updates.get("end") is not None:
            updates["needs_clarification"] = False
            updates["clarification"] = None

        if not updates:
            return parsed
        return replace(parsed, **updates)

    def _get_thread_context(self, thread_id: str) -> ParsedRequest | None:
        with self._thread_context_lock:
            return self._thread_context.get(thread_id)

    def _remember_thread_context(self, thread_id: str, parsed: ParsedRequest) -> None:
        if parsed.outside_split:
            return
        has_user_signal = (
            parsed.preference_explicit
            or parsed.location_explicit
            or parsed.time_explicit
            or parsed.start is not None
            or parsed.end is not None
        )
        if not has_user_signal:
            return
        with self._thread_context_lock:
            self._thread_context[thread_id] = parsed

    def parse_request(self, query: str, now: datetime | None = None) -> ParsedRequest:
        normalized = self._normalize(query)
        now_zagreb = (now or datetime.now(ZAGREB_TZ)).astimezone(ZAGREB_TZ)
        language: Language = "en"
        preference, preference_explicit = _parse_preference(normalized)
        area, location_explicit = _find_area(normalized)
        date_anchor, date_explicit = _parse_date(normalized, now_zagreb)

        if re.search(
            r"\b(zagreb|tkalciceva|tkalca|dubrovnik|zadar|rijeka|pula)\b", normalized
        ):
            return ParsedRequest(
                preference=preference,
                location_label=SPLIT_AREAS[0].label,
                center=SPLIT_AREAS[0].center,
                radius_m=900,
                start=None,
                end=None,
                period=None,
                date_anchor=date_anchor,
                must_be_open=True,
                language=language,
                outside_split=True,
                preference_explicit=preference_explicit,
                location_explicit=location_explicit,
                date_explicit=date_explicit,
            )

        time_window = _parse_time_window(normalized, date_anchor)
        if time_window is None:
            return ParsedRequest(
                preference=preference,
                location_label=area.label,
                center=area.center,
                radius_m=900,
                start=None,
                end=None,
                period=None,
                date_anchor=date_anchor,
                must_be_open=True,
                language=language,
                needs_clarification=True,
                clarification=(
                    "What time window should I check? For example: today from "
                    "3 to 5pm, tomorrow morning, or this Saturday afternoon."
                ),
                preference_explicit=preference_explicit,
                location_explicit=location_explicit,
                date_explicit=date_explicit,
            )

        start, end, period = time_window
        return ParsedRequest(
            preference=preference,
            location_label=area.label,
            center=area.center,
            radius_m=900,
            start=start,
            end=end,
            period=period,
            date_anchor=date_anchor,
            must_be_open=True,
            language=language,
            preference_explicit=preference_explicit,
            location_explicit=location_explicit,
            time_explicit=True,
            date_explicit=date_explicit,
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


def _ring_point(
    center: dict[str, float], bearing_deg: float, distance_m: float
) -> dict[str, float]:
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
    area_bonus = (
        0.25 if cafe_area and cafe_area.lower() in requested_area.lower() else 0.0
    )
    return min(1.0, proximity + area_bonus)


def _build_answer_facts(
    *,
    parsed: ParsedRequest,
    ranked: list[dict[str, Any]],
    weather: dict[str, Any],
    source_notes: list[str],
) -> dict[str, Any]:
    assert parsed.start and parsed.end
    return {
        "request": {
            "preference": parsed.preference,
            "location": parsed.location_label,
            "time_window": {
                "start": parsed.start.isoformat(timespec="seconds"),
                "end": parsed.end.isoformat(timespec="seconds"),
                "label": f"{_short_time(parsed.start)}-{_short_time(parsed.end)}",
            },
        },
        "weather": _weather_answer_context(weather),
        "best_matches": [_answer_match_fact(result) for result in ranked],
        "source_context": {
            "uses_google_places": any(
                result.get("provider") == "google_places" for result in ranked
            ),
            "uses_open_meteo": any(value is not None for value in weather.values()),
            "notes": source_notes,
        },
        "response_guidance": (
            "Use these facts to recommend the strongest cafe by name and optionally "
            "one backup. Mention weather only when it changes how sun or shade will "
            "feel. Do not mention provider names, internal tools, estimated geometry, "
            "or implementation caveats unless the user asks."
        ),
    }


def _answer_match_fact(result: dict[str, Any]) -> dict[str, Any]:
    exposure = result.get("exposure") or {}
    outdoor_seating = result.get("outdoor_seating") or {}
    return {
        "name": result.get("name"),
        "area": result.get("area"),
        "address": result.get("address"),
        "provider": result.get("provider"),
        "rating": result.get("rating"),
        "user_rating_count": result.get("user_rating_count"),
        "open_for_window": result.get("is_open_for_window"),
        "outdoor_seating_confidence": outdoor_seating.get("confidence"),
        "match_score": exposure.get("match_score"),
        "sun_ratio": exposure.get("sun_ratio"),
        "exposure_summary": exposure.get("summary"),
        "transition_notes": exposure.get("transition_notes") or [],
        "samples": _compact_answer_samples(exposure.get("samples") or []),
    }


def _compact_answer_samples(samples: list[Any]) -> list[dict[str, str]]:
    compact = []
    for sample in samples[:8]:
        if not isinstance(sample, dict):
            continue
        time_value = sample.get("time")
        state = sample.get("state")
        if not isinstance(time_value, str) or state not in {"sun", "shade"}:
            continue
        compact.append({"time": _sample_time_label(time_value), "state": state})
    return compact


def _sample_time_label(value: str) -> str:
    try:
        return datetime.fromisoformat(value).strftime("%H:%M")
    except ValueError:
        return value


def _weather_answer_context(weather: dict[str, Any]) -> dict[str, Any]:
    cloud_cover = weather.get("cloud_cover_avg")
    precipitation_probability = weather.get("precipitation_probability_max")
    precipitation_mm = weather.get("precipitation_mm_max")

    if all(
        value is None
        for value in (cloud_cover, precipitation_probability, precipitation_mm)
    ):
        impact = "unknown"
        user_summary = "Weather detail is unavailable; rely on geometric sun and shade."
    elif _weather_blocks_direct_sun(weather):
        impact = "direct_sun_blocked"
        user_summary = (
            "Rain or heavy cloud is expected, so direct sun will not feel reliable."
        )
    elif cloud_cover is not None and float(cloud_cover) > 60:
        impact = "sun_muted"
        user_summary = "Cloud cover may mute direct sun during the requested window."
    else:
        impact = "sun_feels_reliable"
        user_summary = "No major weather issue is expected for direct sun."

    return {
        "cloud_cover_avg": cloud_cover,
        "precipitation_probability_max": precipitation_probability,
        "precipitation_mm_max": precipitation_mm,
        "impact": impact,
        "user_summary": user_summary,
    }


def _should_use_seed_pattern(
    data_mode: str,
    cafe: dict[str, Any],
    buildings: list[Any],
) -> bool:
    return bool(cafe.get("patterns")) and (
        data_mode == "mock" or (not buildings and cafe.get("provider") == "demo_seed")
    )


def _pattern_exposure(
    cafe: dict[str, Any],
    parsed: ParsedRequest,
    terrace_confidence: str,
) -> ExposureResult:
    assert parsed.start and parsed.end
    patterns = cafe.get("patterns") or {}
    raw_states = (
        patterns.get(parsed.period or "afternoon")
        or patterns.get("afternoon")
        or ["sun"]
    )
    states = [state if state in {"sun", "shade"} else "sun" for state in raw_states]
    times = _even_sample_times(parsed.start, parsed.end, len(states))
    samples = [
        ExposureSample(time=sample_time, state="shade" if state == "shade" else "sun")
        for sample_time, state in zip(times, states)
    ]
    sun_count = sum(1 for sample in samples if sample.state == "sun")
    sun_ratio = sun_count / len(samples) if samples else 0.0
    if parsed.preference == "sun":
        match_score = sun_ratio
    elif parsed.preference == "shade":
        match_score = 1.0 - sun_ratio
    else:
        match_score = 0.72 + min(sun_ratio, 1.0 - sun_ratio) * 0.20

    transitions = []
    for index in range(1, len(samples)):
        if samples[index - 1].state != samples[index].state:
            transitions.append(
                f"{samples[index].state} around {samples[index].time.strftime('%H:%M')}"
            )

    return ExposureResult(
        samples=samples,
        sun_ratio=round(sun_ratio, 2),
        match_score=round(match_score, 2),
        summary=_pattern_summary(samples),
        transition_notes=transitions,
        confidence=(
            terrace_confidence
            if terrace_confidence in {"high", "medium", "low"}
            else "medium"
        ),
        confidence_reasons=["seed exposure pattern for mock mode"],
    )


def _even_sample_times(start: datetime, end: datetime, count: int) -> list[datetime]:
    if count <= 1 or end <= start:
        return [start]
    step = (end - start) / (count - 1)
    return [start + step * index for index in range(count)]


def _pattern_summary(samples: list[ExposureSample]) -> str:
    sun_count = sum(1 for sample in samples if sample.state == "sun")
    shade_count = len(samples) - sun_count
    start = samples[0].time.strftime("%H:%M")
    end = samples[-1].time.strftime("%H:%M")
    if shade_count == len(samples):
        return f"Mostly shaded from {start} to {end}."
    if sun_count == len(samples):
        return f"Mostly sunny from {start} to {end}."
    if shade_count > sun_count:
        return f"Mostly shaded from {start} to {end}, with a short sunny patch."
    return f"Mostly sunny from {start} to {end}, with a short shaded patch."


def _parse_preference(query: str) -> tuple[Preference, bool]:
    if re.search(r"\b(shade|shady|shadow|cool|hlad|sjena|senka)\b", query):
        return "shade", True
    if re.search(r"\b(sun|sunny|sunlight|direct sun|sunce|suncano)\b", query):
        return "sun", True
    return "either", False


def _alias_matches(normalized_query: str, alias: str) -> bool:
    stripped = alias.strip()
    if not stripped:
        return False
    if " " in stripped:
        return stripped in normalized_query
    if any(ch.isdigit() for ch in stripped):
        return stripped in normalized_query
    return (
        re.search(
            rf"(?<![a-z0-9]){re.escape(stripped)}(?![a-z0-9])",
            normalized_query,
        )
        is not None
    )


def _find_area(query: str) -> tuple[SplitArea, bool]:
    for area in SPLIT_AREAS:
        if any(_alias_matches(query, alias) for alias in area.aliases):
            return area, True
    return SPLIT_AREAS[0], False


def _parse_time_window(
    query: str,
    date: datetime,
) -> tuple[datetime, datetime, Period] | None:
    explicit = re.search(
        r"(?<![\d-])(?:from\s*)?(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\s*(?:-|to|until|and)\s*(\d{1,2})(?::(\d{2}))?\s*(am|pm)?(?![\d-])",
        query,
    )
    if explicit:
        (
            raw_start_hour,
            raw_start_minute,
            start_meridiem,
            raw_end_hour,
            raw_end_minute,
            end_meridiem,
        ) = explicit.groups()
        start_meridiem = start_meridiem or end_meridiem
        start_hour = _to_hour_24(int(raw_start_hour), start_meridiem)
        end_hour = _to_hour_24(int(raw_end_hour), end_meridiem)
        start_minute = int(raw_start_minute or 0)
        end_minute = int(raw_end_minute or 0)
        if not (
            _is_valid_clock_time(start_hour, start_minute)
            and _is_valid_clock_time(end_hour, end_minute)
        ):
            return None
        start = datetime(
            date.year,
            date.month,
            date.day,
            start_hour,
            start_minute,
            tzinfo=ZAGREB_TZ,
        )
        end = datetime(
            date.year,
            date.month,
            date.day,
            end_hour,
            end_minute,
            tzinfo=ZAGREB_TZ,
        )
        period: Period = (
            "morning"
            if start_hour < 12
            else "lunch" if start_hour < 14 else "afternoon"
        )
        return start, end, period

    point = re.search(
        r"\b(?:around|about|at|near)\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b",
        query,
    ) or re.search(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)\b", query)
    if point:
        raw_hour, raw_minute, meridiem = point.groups()
        hour = _to_daytime_hour_24(int(raw_hour), meridiem)
        minute = int(raw_minute or 0)
        if not _is_valid_clock_time(hour, minute):
            return None
        center = datetime(
            date.year,
            date.month,
            date.day,
            hour,
            minute,
            tzinfo=ZAGREB_TZ,
        )
        period = _period_for_hour(hour)
        return center - timedelta(minutes=30), center + timedelta(minutes=30), period

    if "morning" in query:
        return _window(date, 9, 12, "morning")
    if "lunch" in query:
        return _window(date, 12, 14, "lunch")
    if "afternoon" in query:
        return _window(date, 14, 18, "afternoon")
    return None


def _parse_date(query: str, now: datetime) -> tuple[datetime, bool]:
    date = now
    explicit = False
    if "tomorrow" in query or "tommorow" in query:
        date = date + timedelta(days=1)
        explicit = True
    weekday_match = re.search(
        r"\b(this\s+)?(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
        query,
    )
    if weekday_match:
        explicit = True
        target = _weekday_number(weekday_match.group(2))
        diff = (target - date.weekday()) % 7
        if diff == 0 and now.hour >= 18:
            diff = 7
        date = now + timedelta(days=diff)
    if "today" in query:
        explicit = True
    return date, explicit


def _window(date: datetime, start_hour: int, end_hour: int, period: Period):
    return (
        datetime(date.year, date.month, date.day, start_hour, tzinfo=ZAGREB_TZ),
        datetime(date.year, date.month, date.day, end_hour, tzinfo=ZAGREB_TZ),
        period,
    )


def _move_time_window_to_date(value: datetime, date_anchor: datetime) -> datetime:
    return datetime(
        date_anchor.year,
        date_anchor.month,
        date_anchor.day,
        value.hour,
        value.minute,
        value.second,
        value.microsecond,
        tzinfo=ZAGREB_TZ,
    )


def _period_for_hour(hour: int) -> Period:
    if hour < 12:
        return "morning"
    if hour < 14:
        return "lunch"
    return "afternoon"


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


def _to_daytime_hour_24(hour: int, meridiem: str | None) -> int:
    if meridiem:
        return _to_hour_24(hour, meridiem)
    if 1 <= hour <= 7:
        return hour + 12
    return hour


def _is_valid_clock_time(hour: int, minute: int) -> bool:
    return 0 <= hour <= 23 and 0 <= minute <= 59


def _weather_adjusted_exposure(
    exposure: ExposureResult,
    parsed: ParsedRequest,
    weather: dict[str, Any],
) -> ExposureResult:
    if not _weather_blocks_direct_sun(weather):
        return exposure

    samples = [replace(sample, state="shade") for sample in exposure.samples]
    if parsed.preference == "sun":
        match_score = 0.0
    elif parsed.preference == "shade":
        match_score = 1.0
    else:
        match_score = 0.72

    confidence_reasons = list(exposure.confidence_reasons)
    reason = _weather_block_reason(weather)
    if reason not in confidence_reasons:
        confidence_reasons.append(reason)

    return ExposureResult(
        samples=samples,
        sun_ratio=0.0,
        match_score=round(match_score, 2),
        summary="No usable direct sun expected during this window because of the forecast.",
        transition_notes=[],
        confidence=exposure.confidence,
        confidence_reasons=confidence_reasons,
    )


def _weather_blocks_direct_sun(weather: dict[str, Any]) -> bool:
    precipitation_mm = weather.get("precipitation_mm_max")
    precipitation_probability = weather.get("precipitation_probability_max")
    cloud_cover = weather.get("cloud_cover_avg")
    if precipitation_mm is not None and float(precipitation_mm) > 0:
        return True
    if precipitation_probability is not None and float(precipitation_probability) >= 70:
        return True
    if cloud_cover is not None and float(cloud_cover) >= 85:
        return True
    return False


def _weather_block_reason(weather: dict[str, Any]) -> str:
    precipitation_mm = weather.get("precipitation_mm_max")
    precipitation_probability = weather.get("precipitation_probability_max")
    cloud_cover = weather.get("cloud_cover_avg")
    if precipitation_mm is not None and float(precipitation_mm) > 0:
        return "precipitation during the window"
    if precipitation_probability is not None and float(precipitation_probability) >= 70:
        return "high precipitation probability during the window"
    if cloud_cover is not None and float(cloud_cover) >= 85:
        return "heavy cloud cover during the window"
    return "weather blocks direct sun during the window"


def _weather_answer_note(weather: dict[str, Any]) -> str:
    if _weather_blocks_direct_sun(weather):
        return (
            " Rain or heavy cloud keeps direct sun off the terrace during that window."
        )
    cloud_cover = weather.get("cloud_cover_avg")
    if cloud_cover is not None and float(cloud_cover) > 60:
        return " Cloud cover keeps the sun muted during that window."
    return ""


def _short_time(value: datetime) -> str:
    return value.strftime("%H:%M")
