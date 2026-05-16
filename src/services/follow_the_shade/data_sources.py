from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

from services.follow_the_shade.address_display import format_address_for_display
from services.follow_the_shade.cache import TtlCache

DataMode = Literal["mock", "actual"]

log = logging.getLogger(__name__)


@dataclass
class VenueCandidateBundle:
    venues: list[dict[str, Any]]
    source_notes: list[str] = field(default_factory=list)
    uncertainty_notes: list[str] = field(default_factory=list)

    @property
    def cafes(self) -> list[dict[str, Any]]:
        return self.venues


CafeCandidateBundle = VenueCandidateBundle


@dataclass
class BuildingSummary:
    buildings: list[Any] = field(default_factory=list)
    building_count: int | None = None
    height_tag_count: int | None = None
    default_height_m: float = 9.0
    source_notes: list[str] = field(default_factory=list)
    uncertainty_notes: list[str] = field(default_factory=list)

    @property
    def height_estimates_used(self) -> bool:
        return any(
            getattr(building, "height_confidence", None) != "exact_tag"
            for building in self.buildings
        )


@dataclass
class WeatherSummary:
    cloud_cover_avg: int | None = None
    precipitation_probability_max: int | None = None
    precipitation_mm_max: float | None = None
    source_notes: list[str] = field(default_factory=list)
    uncertainty_notes: list[str] = field(default_factory=list)

    def to_result_weather(self) -> dict[str, int | float | None]:
        return {
            "cloud_cover_avg": self.cloud_cover_avg,
            "precipitation_probability_max": self.precipitation_probability_max,
            "precipitation_mm_max": self.precipitation_mm_max,
        }


@dataclass
class OutdoorSeatingSummary:
    points: list[dict[str, Any]] = field(default_factory=list)
    source_notes: list[str] = field(default_factory=list)
    uncertainty_notes: list[str] = field(default_factory=list)


class FollowTheShadeDataSources:
    def __init__(
        self,
        *,
        settings: Any,
        seed_cafes: list[dict[str, Any]],
        cache: TtlCache,
    ) -> None:
        self.settings = settings
        self.seed_cafes = seed_cafes
        self.cache = cache

    @property
    def data_mode(self) -> DataMode:
        configured = str(getattr(self.settings, "FOLLOW_THE_SHADE_DATA_MODE", "mock"))
        return "actual" if configured.lower() in {"actual", "api", "live"} else "mock"

    async def cafe_candidates(
        self,
        *,
        center: dict[str, float],
        radius_m: int,
        limit: int,
    ) -> VenueCandidateBundle:
        return await self.venue_candidates(
            center=center,
            radius_m=radius_m,
            limit=limit,
            venue_types=("cafe",),
        )

    async def venue_candidates(
        self,
        *,
        center: dict[str, float],
        radius_m: int,
        limit: int,
        venue_types: tuple[str, ...],
    ) -> VenueCandidateBundle:
        cache_key = TtlCache.make_key(
            "places",
            {
                "mode": self.data_mode,
                "center": _rounded_center(center),
                "radius_m": _radius_bucket(radius_m),
                "limit": limit,
                "venue_types": list(venue_types),
            },
        )
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached

        if self.data_mode == "mock":
            venues = [
                venue
                for venue in self.seed_cafes
                if _venue_matches(venue, venue_types)
                and _distance_m(center, venue["terrace_point"]) <= radius_m
            ]
            venues.sort(key=lambda venue: _distance_m(center, venue["terrace_point"]))
            bundle = VenueCandidateBundle(
                venues=venues[:limit],
                source_notes=[
                    "Venue data from mock seed file assets/split_cafe_seed.json."
                ],
                uncertainty_notes=[
                    "Venue locations and outdoor seating are seed data for frontend development."
                ],
            )
            self.cache.set(cache_key, bundle)
            return bundle

        bundle = await self._google_places_candidates(
            center=center,
            radius_m=radius_m,
            limit=limit,
            venue_types=venue_types,
        )
        self.cache.set(cache_key, bundle)
        return bundle

    async def building_summary(
        self,
        *,
        center: dict[str, float],
        radius_m: int,
    ) -> BuildingSummary:
        cache_key = TtlCache.make_key(
            "buildings",
            {
                "mode": self.data_mode,
                "center": _rounded_center(center),
                "radius_m": _radius_bucket(radius_m),
            },
        )
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached

        if self.data_mode == "mock":
            summary = BuildingSummary(
                source_notes=["Building geometry is not fetched in mock mode."],
                uncertainty_notes=[
                    "Seed exposure patterns stand in for real building-shadow geometry."
                ],
            )
            self.cache.set(cache_key, summary)
            return summary

        summary = await self._overpass_building_summary(
            center=center,
            radius_m=radius_m,
        )
        self.cache.set(cache_key, summary)
        return summary

    async def weather_summary(
        self,
        *,
        center: dict[str, float],
        start: datetime,
        end: datetime,
    ) -> WeatherSummary:
        cache_key = TtlCache.make_key(
            "weather",
            {
                "mode": self.data_mode,
                "center": _rounded_center(center),
                "start_bucket": _time_bucket(start),
                "end_bucket": _time_bucket(end),
            },
        )
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached

        if self.data_mode == "mock":
            summary = WeatherSummary(
                source_notes=["Weather is not fetched in mock mode."],
                uncertainty_notes=["Cloud cover is unknown in mock mode."],
            )
            self.cache.set(cache_key, summary)
            return summary

        summary = await self._open_meteo_weather_summary(
            center=center,
            start=start,
            end=end,
        )
        self.cache.set(cache_key, summary)
        return summary

    async def outdoor_seating_summary(
        self,
        *,
        center: dict[str, float],
        radius_m: int,
    ) -> OutdoorSeatingSummary:
        cache_key = TtlCache.make_key(
            "outdoor_seating",
            {
                "mode": self.data_mode,
                "center": _rounded_center(center),
                "radius_m": _radius_bucket(radius_m),
            },
        )
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached

        if self.data_mode == "mock":
            summary = OutdoorSeatingSummary(
                uncertainty_notes=["Outdoor seating is not fetched in mock mode."],
            )
            self.cache.set(cache_key, summary)
            return summary

        summary = await self._overpass_outdoor_seating_summary(
            center=center,
            radius_m=radius_m,
        )
        self.cache.set(cache_key, summary)
        return summary

    async def _google_places_candidates(
        self,
        *,
        center: dict[str, float],
        radius_m: int,
        limit: int,
        venue_types: tuple[str, ...],
    ) -> VenueCandidateBundle:
        api_key = getattr(self.settings, "GOOGLE_PLACES_API_KEY", None) or getattr(
            self.settings, "GOOGLE_MAPS_API_KEY", None
        )
        if not api_key:
            return self._seed_fallback_bundle(
                "Google Places is not configured; using mock venue data.",
                venue_types=venue_types,
            )

        from services.places.google_places import GooglePlacesClient

        raw_venues = await GooglePlacesClient(api_key).nearby_venues(
            center["lat"],
            center["lng"],
            radius_m=radius_m,
            max_results=limit,
            venue_types=venue_types,
        )
        if not raw_venues:
            return self._seed_fallback_bundle(
                "Google Places returned no venue candidates; using mock venue data.",
                venue_types=venue_types,
            )

        venues = [self._normalize_provider_cafe(venue) for venue in raw_venues]
        notes = ["Venue metadata from Google Places API."]
        uncertainty = [
            "Outdoor seating evidence is not guaranteed by Places, so low-evidence results are supplemented."
        ]

        if len(venues) < 3:
            uncertainty.append(
                "Fewer than three Google venue candidates returned; curated seed pins "
                "may fill remaining slots (illustrative demo locales are never added)."
            )
        supplemented = _merge_seed_supplements(
            venues,
            self.seed_cafes,
            center,
            limit,
            venue_types,
        )
        if len(supplemented) > len(venues):
            notes.append(
                "Seed venue data supplements missing or low-evidence API results."
            )
        return VenueCandidateBundle(
            venues=supplemented,
            source_notes=notes,
            uncertainty_notes=uncertainty,
        )

    async def _overpass_building_summary(
        self,
        *,
        center: dict[str, float],
        radius_m: int,
    ) -> BuildingSummary:
        from services.geodata.overpass_client import OverpassClient

        buildings = await OverpassClient(
            getattr(self.settings, "OVERPASS_URL")
        ).fetch_buildings(
            center,
            radius_m=min(radius_m, 700),
        )
        if not buildings:
            return BuildingSummary(
                building_count=0,
                height_tag_count=0,
                source_notes=["No nearby building geometry returned from Overpass."],
                uncertainty_notes=[
                    "Exposure falls back to seed patterns when buildings are missing."
                ],
            )

        height_tag_count = sum(
            1 for building in buildings if building.height_confidence == "exact_tag"
        )
        uncertainty = []
        if height_tag_count < len(buildings):
            uncertainty.append(
                "Some OSM buildings lack heights; missing heights use the 9m MVP default."
            )
        return BuildingSummary(
            buildings=buildings,
            building_count=len(buildings),
            height_tag_count=height_tag_count,
            source_notes=[
                f"Building geometry from OpenStreetMap/Overpass ({len(buildings)} polygons, {height_tag_count} with exact height tags)."
            ],
            uncertainty_notes=uncertainty,
        )

    async def _open_meteo_weather_summary(
        self,
        *,
        center: dict[str, float],
        start: datetime,
        end: datetime,
    ) -> WeatherSummary:
        from services.weather.open_meteo import OpenMeteoClient

        weather = await OpenMeteoClient(
            str(getattr(self.settings, "OPEN_METEO_BASE_URL"))
        ).window_weather(
            center["lat"],
            center["lng"],
            start,
            end,
        )
        cloud_cover = weather.get("cloud_cover_avg")
        precipitation = weather.get("precipitation_probability_max")
        precipitation_mm = weather.get("precipitation_mm_max")

        if cloud_cover is None and precipitation is None and precipitation_mm is None:
            return WeatherSummary(
                source_notes=[
                    "Open-Meteo returned no hourly weather samples for the requested window."
                ],
                uncertainty_notes=[
                    "Cloud-cover nuance is unavailable for this answer."
                ],
            )

        return WeatherSummary(
            cloud_cover_avg=int(cloud_cover) if cloud_cover is not None else None,
            precipitation_probability_max=(
                int(precipitation) if precipitation is not None else None
            ),
            precipitation_mm_max=(
                float(precipitation_mm) if precipitation_mm is not None else None
            ),
            source_notes=["Weather context from Open-Meteo hourly forecast."],
        )

    async def _overpass_outdoor_seating_summary(
        self,
        *,
        center: dict[str, float],
        radius_m: int,
    ) -> OutdoorSeatingSummary:
        from services.geodata.overpass_client import OverpassClient

        points = await OverpassClient(
            getattr(self.settings, "OVERPASS_URL")
        ).fetch_outdoor_seating(
            center,
            radius_m=min(radius_m, 900),
        )
        if not points:
            return OutdoorSeatingSummary(
                source_notes=["No mapped OSM outdoor-seating points returned nearby."],
                uncertainty_notes=[
                    "Terrace points without mapped outdoor seating are estimated."
                ],
            )

        return OutdoorSeatingSummary(
            points=points,
            source_notes=[
                f"Outdoor seating hints from OpenStreetMap/Overpass ({len(points)} nearby points)."
            ],
            uncertainty_notes=[
                "Terrace matching uses nearby mapped outdoor-seating points when available."
            ],
        )

    def _seed_fallback_bundle(
        self,
        reason: str,
        *,
        venue_types: tuple[str, ...],
    ) -> VenueCandidateBundle:
        venues: list[dict[str, Any]] = [
            venue for venue in self.seed_cafes if _venue_matches(venue, venue_types)
        ]
        notes = ["Venue data from mock seed file assets/split_cafe_seed.json."]
        uncertainty = [reason]
        if self.data_mode == "actual":
            verified = [
                venue for venue in venues if not _is_illustrative_demo_seed(venue)
            ]
            if verified:
                venues = verified
                notes.append(
                    "Illustrative demo:* seed locales omitted when APIs are unavailable."
                )
        return VenueCandidateBundle(
            venues=venues,
            source_notes=notes,
            uncertainty_notes=uncertainty,
        )

    def _normalize_provider_cafe(self, cafe: dict[str, Any]) -> dict[str, Any]:
        point = {
            "lat": float(cafe["location"]["lat"]),
            "lng": float(cafe["location"]["lng"]),
        }
        seed_template = _nearest_seed(self.seed_cafes, point)
        raw_address = cafe.get("address")
        if isinstance(raw_address, str) and raw_address.strip():
            normalized_addr = format_address_for_display(raw_address)
            display_address = (
                normalized_addr
                if normalized_addr
                else (cafe.get("area") or seed_template.get("area", "Riva"))
            )
        else:
            display_address = None
        return {
            **cafe,
            "area": cafe.get("area") or seed_template.get("area", "Riva"),
            "venue_type": cafe.get("venue_type")
            or seed_template.get("venue_type")
            or "venue",
            "venue_types": cafe.get("venue_types")
            or seed_template.get("venue_types")
            or [cafe.get("venue_type") or seed_template.get("venue_type") or "venue"],
            "location": point,
            "terrace_point": cafe.get("terrace_point") or point,
            "patterns": cafe.get("patterns") or seed_template["patterns"],
            "outdoor_seating_confidence": cafe.get("outdoor_seating_confidence")
            or "unknown",
            "is_open_for_window": cafe.get("is_open_for_window", True),
            "address": display_address
            or cafe.get("area")
            or seed_template.get("area", "Riva"),
            "rating": cafe.get("rating"),
            "user_rating_count": cafe.get("user_rating_count"),
            "google_maps_uri": cafe.get("google_maps_uri"),
            "provider": cafe.get("provider", "unknown"),
        }


def _merge_seed_supplements(
    venues: list[dict[str, Any]],
    seed_venues: list[dict[str, Any]],
    center: dict[str, float],
    limit: int,
    venue_types: tuple[str, ...],
) -> list[dict[str, Any]]:
    merged = list(venues)
    known_ids = {venue["id"] for venue in merged}
    for seed in sorted(
        seed_venues, key=lambda venue: _distance_m(center, venue["terrace_point"])
    ):
        if len(merged) >= limit:
            break
        if seed["id"] in known_ids:
            continue
        if not _venue_matches(seed, venue_types):
            continue
        if _is_illustrative_demo_seed(seed):
            continue
        merged.append(seed)
        known_ids.add(seed["id"])
    return merged


def _venue_matches(venue: dict[str, Any], requested_types: tuple[str, ...]) -> bool:
    if not requested_types:
        return True
    venue_types = venue.get("venue_types") or [venue.get("venue_type")]
    normalized = {
        "night_club" if venue_type == "nightclub" else venue_type
        for venue_type in venue_types
        if isinstance(venue_type, str)
    }
    return bool(normalized.intersection(requested_types))


def _is_illustrative_demo_seed(seed: dict[str, Any]) -> bool:
    """Synthetic geometry-only seeds; never mix into Google Places results."""
    return str(seed.get("id", "")).startswith("demo:")


def _nearest_seed(
    seed_cafes: list[dict[str, Any]],
    point: dict[str, float],
) -> dict[str, Any]:
    templates = list(seed_cafes)
    return min(templates, key=lambda cafe: _distance_m(point, cafe["terrace_point"]))


def _rounded_center(center: dict[str, float]) -> dict[str, float]:
    return {"lat": round(center["lat"], 3), "lng": round(center["lng"], 3)}


def _radius_bucket(radius_m: int) -> int:
    return int(round(radius_m / 100) * 100)


def _time_bucket(value: datetime) -> str:
    minute_bucket = 30 if value.minute >= 30 else 0
    return value.replace(minute=minute_bucket, second=0, microsecond=0).isoformat()


def _distance_m(a: dict[str, float], b: dict[str, float]) -> float:
    import math

    radius = 6371000.0
    d_lat = math.radians(b["lat"] - a["lat"])
    d_lng = math.radians(b["lng"] - a["lng"])
    lat_1 = math.radians(a["lat"])
    lat_2 = math.radians(b["lat"])
    haversine = (
        math.sin(d_lat / 2) ** 2
        + math.cos(lat_1) * math.cos(lat_2) * math.sin(d_lng / 2) ** 2
    )
    return 2 * radius * math.asin(math.sqrt(haversine))
