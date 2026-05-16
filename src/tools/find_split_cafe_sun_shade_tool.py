from __future__ import annotations

import json
import math
import re
import unicodedata
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Literal
from zoneinfo import ZoneInfo

from app.analysis_store import InMemoryAnalysisStore

Preference = Literal["sun", "shade", "either"]
ExposureState = Literal["sun", "shade"]
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


class FindSplitCafeSunShadeTool:
    name = "find_split_cafe_sun_shade"

    def __init__(
        self,
        *,
        analysis_store: InMemoryAnalysisStore,
        seed_path: str,
    ) -> None:
        self.analysis_store = analysis_store
        self.seed_path = Path(seed_path)
        self.seed_cafes = self._load_seed_cafes()

    async def arun(self, *, query: str, thread_id: str) -> dict[str, Any]:
        parsed = self.parse_request(query)

        if parsed.outside_split:
            return {
                "answer": (
                    "I'm focused on Split. Do you want something around Riva, "
                    "Bacvice, Marmontova, Varos, or another Split area?"
                ),
                "thread_id": thread_id,
                "analysis_id": None,
                "map_payload": None,
                "sources": [],
                "detected_language": parsed.language,
            }

        if parsed.needs_clarification or parsed.start is None or parsed.end is None:
            return {
                "answer": parsed.clarification
                or "What time window should I check?",
                "thread_id": thread_id,
                "analysis_id": None,
                "map_payload": None,
                "sources": [],
                "detected_language": parsed.language,
            }

        analysis_id = f"shade_{parsed.start:%Y%m%d}_{uuid.uuid4().hex[:8]}"
        map_payload = self._build_map_payload(
            analysis_id=analysis_id,
            parsed=parsed,
            query=query,
        )
        self.analysis_store.save(
            analysis_id=analysis_id,
            thread_id=thread_id,
            query=query,
            parsed_request=map_payload["request"],
            map_payload=map_payload,
        )

        best = map_payload["results"][:3]
        names = ", ".join(result["name"] for result in best)
        preference_label = "outdoor" if parsed.preference == "either" else parsed.preference
        answer = (
            f"Best {preference_label} matches near {parsed.location_label} for "
            f"{_short_time(parsed.start)}-{_short_time(parsed.end)}: {names}. "
            f"{best[0]['exposure']['summary']} "
            "This is an MVP estimate using seeded terrace points; real Google/OSM "
            "building-shadow analysis can replace the seed source behind the same contract."
        )

        return {
            "answer": answer,
            "thread_id": thread_id,
            "analysis_id": analysis_id,
            "map_payload": map_payload,
            "sources": map_payload["source_notes"],
            "detected_language": parsed.language,
        }

    def parse_request(self, query: str, now: datetime | None = None) -> ParsedRequest:
        normalized = _normalize(query)
        now_zagreb = (now or datetime.now(ZAGREB_TZ)).astimezone(ZAGREB_TZ)
        language = _detect_language(normalized)

        if re.search(r"\b(zagreb|tkalciceva|tkalca|dubrovnik|zadar|rijeka|pula)\b", normalized):
            area = SPLIT_AREAS[0]
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

    def _build_map_payload(
        self,
        *,
        analysis_id: str,
        parsed: ParsedRequest,
        query: str,
    ) -> dict[str, Any]:
        assert parsed.start is not None
        assert parsed.end is not None
        assert parsed.period is not None

        ranked = []
        for cafe in sorted(
            self.seed_cafes,
            key=lambda item: _distance_m(parsed.center, item["terrace_point"]),
        )[:6]:
            result = self._build_result(cafe, parsed)
            distance = _distance_m(parsed.center, cafe["terrace_point"])
            rank_score = (
                result["exposure"]["match_score"] * 0.60
                + _locality_score(distance, parsed.location_label, cafe["area"]) * 0.25
                + _area_match_score(parsed.location_label, cafe["area"]) * 0.15
            )
            ranked.append((rank_score, result))

        results = [result for _, result in sorted(ranked, key=lambda item: item[0], reverse=True)[:4]]

        return {
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
            "results": results,
            "source_notes": [
                "Demo cafe data from assets/split_cafe_seed.json.",
                "Terrace points are estimates for frontend/backend contract testing.",
                "Real backend should use Google Places, OpenStreetMap/Overpass, Astral/Shapely, and Open-Meteo.",
            ],
        }

    def _build_result(self, cafe: dict[str, Any], parsed: ParsedRequest) -> dict[str, Any]:
        assert parsed.start is not None
        assert parsed.end is not None
        assert parsed.period is not None

        pattern = cafe["patterns"][parsed.period]
        samples = _build_samples(parsed.start, parsed.end, pattern)
        sun_count = sum(1 for sample in samples if sample["state"] == "sun")
        sun_ratio = sun_count / len(samples)
        match_score = (
            sun_ratio
            if parsed.preference == "sun"
            else 1 - sun_ratio
            if parsed.preference == "shade"
            else 0.72 + min(sun_ratio, 1 - sun_ratio) * 0.20
        )
        rounded_score = round(match_score, 2)
        confidence = "low" if cafe["outdoor_seating_confidence"] == "low" else "medium"

        return {
            "id": cafe["id"],
            "name": cafe["name"],
            "provider": cafe["provider"],
            "location": cafe["location"],
            "terrace_point": cafe["terrace_point"],
            "address": cafe["address"],
            "rating": cafe.get("rating"),
            "user_rating_count": cafe.get("user_rating_count"),
            "is_open_for_window": True,
            "outdoor_seating": {
                "value": True,
                "source": cafe["provider"],
                "confidence": cafe["outdoor_seating_confidence"],
            },
            "exposure": {
                "preference": parsed.preference,
                "match_score": rounded_score,
                "label": "strong_match"
                if rounded_score >= 0.8
                else "good_match"
                if rounded_score >= 0.6
                else "ok_match",
                "summary": _summarize_exposure(samples),
                "sun_ratio": round(sun_ratio, 2),
                "samples": samples,
                "transition_notes": _transition_notes(samples),
                "confidence": confidence,
                "confidence_reasons": [
                    "demo seed exposure pattern",
                    "terrace point estimated"
                    if confidence == "low"
                    else "outdoor seating inferred from seed data",
                ],
            },
            "weather": {
                "cloud_cover_avg": None,
                "precipitation_probability_max": None,
            },
        }

    def _load_seed_cafes(self) -> list[dict[str, Any]]:
        path = self.seed_path
        if not path.is_absolute():
            path = Path.cwd() / path
        with path.open("r", encoding="utf-8") as seed_file:
            return json.load(seed_file)


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


def _window(date: datetime, start_hour: int, end_hour: int, period: Period) -> tuple[datetime, datetime, Period]:
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


def _build_samples(start: datetime, end: datetime, pattern: list[ExposureState]) -> list[dict[str, str]]:
    count = max(len(pattern), 2)
    step_seconds = (end - start).total_seconds() / (count - 1)
    samples = []
    for index in range(count):
        sample_time = start + timedelta(seconds=step_seconds * index)
        samples.append(
            {
                "time": sample_time.isoformat(timespec="seconds"),
                "state": pattern[index % len(pattern)],
            }
        )
    return samples


def _summarize_exposure(samples: list[dict[str, str]]) -> str:
    sun_count = sum(1 for sample in samples if sample["state"] == "sun")
    shade_count = len(samples) - sun_count
    start = samples[0]["time"][11:16]
    end = samples[-1]["time"][11:16]
    if shade_count == len(samples):
        return f"Mostly shaded from {start} to {end}."
    if sun_count == len(samples):
        return f"Mostly sunny from {start} to {end}."
    if shade_count > sun_count:
        return f"Mostly shaded from {start} to {end}, with a short sunny patch."
    return f"Mostly sunny from {start} to {end}, with a short shaded patch."


def _transition_notes(samples: list[dict[str, str]]) -> list[str]:
    notes = []
    for index in range(1, len(samples)):
        previous = samples[index - 1]
        current = samples[index]
        if previous["state"] != current["state"]:
            notes.append(f"{current['state']} around {current['time'][11:16]}")
    return notes


def _detect_language(query: str) -> Language:
    if re.search(r"\b(ciao|ombra|sole|terrazza)\b", query):
        return "it"
    if re.search(r"\b(schatten|sonne|kaffee)\b", query):
        return "de"
    if re.search(r"\b(hlad|sunce|kava|terasa)\b", query):
        return "hr"
    return "en"


def _normalize(value: str) -> str:
    stripped = unicodedata.normalize("NFD", value.lower())
    return "".join(ch for ch in stripped if unicodedata.category(ch) != "Mn")


def _short_time(value: datetime) -> str:
    return value.strftime("%H:%M")


def _area_match_score(requested_area: str, cafe_area: str) -> float:
    return 1.0 if _normalize(cafe_area) in _normalize(requested_area) else 0.0


def _locality_score(distance: float, requested_area: str, cafe_area: str) -> float:
    proximity = max(0.0, 1.0 - distance / 900.0)
    return min(1.0, proximity + _area_match_score(requested_area, cafe_area) * 0.25)


def _distance_m(a: dict[str, float], b: dict[str, float]) -> float:
    radius = 6371000.0
    d_lat = math.radians(b["lat"] - a["lat"])
    d_lng = math.radians(b["lng"] - a["lng"])
    lat_1 = math.radians(a["lat"])
    lat_2 = math.radians(b["lat"])
    h = (
        math.sin(d_lat / 2) ** 2
        + math.cos(lat_1) * math.cos(lat_2) * math.sin(d_lng / 2) ** 2
    )
    return 2 * radius * math.asin(math.sqrt(h))
