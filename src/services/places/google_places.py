from __future__ import annotations

import asyncio
import logging
import math
from typing import Any

import httpx

log = logging.getLogger(__name__)

NEARBY_NEW_URL = "https://places.googleapis.com/v1/places:searchNearby"
NEARBY_LEGACY_URL = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
DEFAULT_VENUE_TYPES = ("cafe", "restaurant", "bar", "night_club")
SUPPORTED_VENUE_TYPES = set(DEFAULT_VENUE_TYPES)
GOOGLE_PRIMARY_TYPES_BY_VENUE_TYPE = {
    "cafe": ("cafe",),
    "restaurant": ("restaurant", "bistro"),
    "bar": ("bar", "bar_and_grill", "beer_garden", "brewery", "brewpub"),
    "night_club": ("night_club", "dance_hall", "live_music_venue"),
}
GOOGLE_TYPE_TO_VENUE_TYPE = {
    google_type: venue_type
    for venue_type, google_types in GOOGLE_PRIMARY_TYPES_BY_VENUE_TYPE.items()
    for google_type in google_types
}


class GooglePlacesClient:
    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    async def nearby_cafes(
        self,
        lat: float,
        lng: float,
        *,
        radius_m: int = 900,
        max_results: int = 12,
    ) -> list[dict[str, Any]]:
        return await self.nearby_venues(
            lat,
            lng,
            radius_m=radius_m,
            max_results=max_results,
            venue_types=("cafe",),
        )

    async def nearby_venues(
        self,
        lat: float,
        lng: float,
        *,
        radius_m: int = 900,
        max_results: int = 12,
        venue_types: tuple[str, ...] = DEFAULT_VENUE_TYPES,
    ) -> list[dict[str, Any]]:
        normalized_types = _normalize_venue_types(venue_types)
        venues = await self._nearby_venues_new(
            lat,
            lng,
            radius_m=radius_m,
            max_results=max_results,
            venue_types=normalized_types,
        )
        if venues is not None:
            return venues
        return await self._nearby_venues_legacy(
            lat,
            lng,
            radius_m=radius_m,
            max_results=max_results,
            venue_types=normalized_types,
        )

    async def _nearby_venues_new(
        self,
        lat: float,
        lng: float,
        *,
        radius_m: int,
        max_results: int,
        venue_types: tuple[str, ...],
    ) -> list[dict[str, Any]] | None:
        requested_groups = tuple((venue_type,) for venue_type in venue_types)
        per_group_limit = _per_group_limit(max_results, len(requested_groups))
        async with httpx.AsyncClient(timeout=20.0) as client:
            results = await asyncio.gather(
                *(
                    self._nearby_venues_new_request(
                        client,
                        lat,
                        lng,
                        radius_m=radius_m,
                        max_results=(
                            max_results
                            if len(requested_groups) == 1
                            else per_group_limit
                        ),
                        requested_types=requested_types,
                    )
                    for requested_types in requested_groups
                )
            )

        if any(result is None for result in results):
            return None
        return _merge_ranked_venue_groups(
            [result for result in results if result is not None],
            lat=lat,
            lng=lng,
            requested_types=venue_types,
            max_results=max_results,
        )

    async def _nearby_venues_new_request(
        self,
        client: httpx.AsyncClient,
        lat: float,
        lng: float,
        *,
        radius_m: int,
        max_results: int,
        requested_types: tuple[str, ...],
    ) -> list[dict[str, Any]] | None:
        google_primary_types = _google_primary_types_for(requested_types)
        payload = {
            "includedPrimaryTypes": list(google_primary_types),
            "maxResultCount": min(max(max_results, 1), 20),
            "rankPreference": "DISTANCE",
            "languageCode": "en",
            "regionCode": "HR",
            "locationRestriction": {
                "circle": {
                    "center": {"latitude": lat, "longitude": lng},
                    "radius": float(radius_m),
                }
            },
        }
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self.api_key,
            "X-Goog-FieldMask": (
                "places.id,places.displayName,places.formattedAddress,"
                "places.location,places.rating,places.userRatingCount,"
                "places.regularOpeningHours,places.googleMapsUri,places.businessStatus,"
                "places.outdoorSeating,places.photos,places.primaryType,places.types"
            ),
        }
        try:
            response = await client.post(
                NEARBY_NEW_URL,
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPStatusError as exc:
            response = exc.response
            status_code = response.status_code if response is not None else "unknown"
            detail = _response_detail(response)
            if response is not None and response.status_code in {401, 403, 404}:
                log.warning(
                    "Google Places New nearby venue search rejected (%s): %s. Falling back to legacy nearby search.",
                    status_code,
                    detail,
                )
                return None
            log.warning(
                "Google Places New nearby venue search failed (%s): %s",
                status_code,
                detail,
            )
            return []
        except httpx.HTTPError as exc:
            log.warning("Google Places New nearby venue search failed: %s", exc)
            return []

        venues = []
        for place in data.get("places", []):
            venue = _normalize_new_place(place, requested_types=requested_types)
            if venue is not None:
                venues.append(venue)
        return sorted(
            venues,
            key=lambda venue: _candidate_sort_key(
                venue,
                lat=lat,
                lng=lng,
                requested_types=requested_types,
            ),
        )

    async def _nearby_venues_legacy(
        self,
        lat: float,
        lng: float,
        *,
        radius_m: int,
        max_results: int,
        venue_types: tuple[str, ...],
    ) -> list[dict[str, Any]]:
        venues: list[dict[str, Any]] = []
        seen_ids: set[str] = set()
        async with httpx.AsyncClient(timeout=20.0) as client:
            for venue_type in venue_types:
                if len(venues) >= max_results:
                    break
                params = {
                    "location": f"{lat},{lng}",
                    "radius": str(radius_m),
                    "type": venue_type,
                    "key": self.api_key,
                }
                try:
                    response = await client.get(NEARBY_LEGACY_URL, params=params)
                    response.raise_for_status()
                    data = response.json()
                except httpx.HTTPStatusError as exc:
                    log.warning(
                        "Google Places legacy nearby venue search failed (%s): %s",
                        (
                            exc.response.status_code
                            if exc.response is not None
                            else "unknown"
                        ),
                        _response_detail(exc.response),
                    )
                    continue
                except httpx.HTTPError as exc:
                    log.warning(
                        "Google Places legacy nearby venue search failed: %s", exc
                    )
                    continue

                api_status = data.get("status")
                if api_status not in {"OK", "ZERO_RESULTS"}:
                    log.warning(
                        "Google Places legacy nearby venue search failed (%s): %s",
                        api_status,
                        data.get("error_message") or "No error message provided.",
                    )
                    continue

                for place in data.get("results", []):
                    venue = _normalize_legacy_place(place, venue_type)
                    if venue is None:
                        continue
                    venue_id = venue["id"]
                    if venue_id in seen_ids:
                        continue
                    venues.append(venue)
                    seen_ids.add(venue_id)
                    if len(venues) >= max_results:
                        break
        return venues


def _normalize_new_place(
    place: dict[str, Any],
    *,
    requested_types: tuple[str, ...] = DEFAULT_VENUE_TYPES,
) -> dict[str, Any] | None:
    business_status = place.get("businessStatus")
    if business_status in {"CLOSED_PERMANENTLY", "CLOSED_TEMPORARILY"}:
        return None

    location = place.get("location", {})
    lat_v = location.get("latitude")
    lng_v = location.get("longitude")
    if lat_v is None or lng_v is None:
        return None

    display = place.get("displayName", {})
    name = display.get("text") if isinstance(display, dict) else str(display)
    regular_hours = place.get("regularOpeningHours") or {}
    photos = place.get("photos") or []
    place_photo_name: str | None = None
    if photos and isinstance(photos, list) and isinstance(photos[0], dict):
        pn = photos[0].get("name")
        if isinstance(pn, str) and pn.strip():
            place_photo_name = pn.strip()

    venue_types = _normalize_place_types(
        [place.get("primaryType"), *(place.get("types") or [])]
    )
    if not set(venue_types).intersection(requested_types):
        return None
    venue_type = _primary_venue_type(venue_types, requested_types=requested_types)

    return {
        "id": f"google:{place.get('id', '')}",
        "name": name or "Venue",
        "provider": "google_places",
        "venue_type": venue_type,
        "venue_types": venue_types,
        "location": {"lat": lat_v, "lng": lng_v},
        "terrace_point": {"lat": lat_v, "lng": lng_v},
        "address": place.get("formattedAddress"),
        "rating": place.get("rating"),
        "user_rating_count": place.get("userRatingCount"),
        "google_maps_uri": place.get("googleMapsUri"),
        "place_photo_name": place_photo_name,
        "business_status": business_status,
        "is_open_for_window": regular_hours.get("openNow", True),
        "outdoor_seating": place.get("outdoorSeating"),
        "outdoor_seating_confidence": (
            "medium" if place.get("outdoorSeating") is True else "unknown"
        ),
    }


def _normalize_legacy_place(
    place: dict[str, Any], requested_type: str
) -> dict[str, Any] | None:
    business_status = place.get("business_status")
    if business_status in {"CLOSED_PERMANENTLY", "CLOSED_TEMPORARILY"}:
        return None

    location = place.get("geometry", {}).get("location", {})
    lat_v = location.get("lat")
    lng_v = location.get("lng")
    place_id = place.get("place_id")
    if lat_v is None or lng_v is None:
        return None

    google_maps_uri = (
        f"https://www.google.com/maps/place/?q=place_id:{place_id}"
        if place_id
        else None
    )
    photos = place.get("photos") or []
    photo_reference: str | None = None
    if photos and isinstance(photos, list) and isinstance(photos[0], dict):
        pr = photos[0].get("photo_reference")
        if isinstance(pr, str) and pr.strip():
            photo_reference = pr.strip()

    opening_hours = place.get("opening_hours") or {}
    venue_types = _normalize_place_types([requested_type, *(place.get("types") or [])])
    venue_type = _primary_venue_type(venue_types, requested_types=(requested_type,))

    return {
        "id": f"google:{place_id or ''}",
        "name": place.get("name") or "Venue",
        "provider": "google_places",
        "venue_type": venue_type,
        "venue_types": venue_types,
        "location": {"lat": lat_v, "lng": lng_v},
        "terrace_point": {"lat": lat_v, "lng": lng_v},
        "address": place.get("vicinity") or place.get("formatted_address"),
        "rating": place.get("rating"),
        "user_rating_count": place.get("user_ratings_total"),
        "google_maps_uri": google_maps_uri,
        "photo_reference": photo_reference,
        "business_status": business_status,
        "is_open_for_window": opening_hours.get("open_now", True),
        "outdoor_seating": None,
        "outdoor_seating_confidence": "unknown",
    }


def _normalize_venue_types(venue_types: tuple[str, ...]) -> tuple[str, ...]:
    normalized: list[str] = []
    for venue_type in venue_types or DEFAULT_VENUE_TYPES:
        mapped = "night_club" if venue_type == "nightclub" else venue_type
        if mapped not in SUPPORTED_VENUE_TYPES or mapped in normalized:
            continue
        normalized.append(mapped)
    return tuple(normalized or DEFAULT_VENUE_TYPES)


def _normalize_place_types(raw_types: list[Any]) -> list[str]:
    normalized = []
    for raw_type in raw_types:
        if not isinstance(raw_type, str):
            continue
        mapped = _venue_type_for_google_type(raw_type)
        if mapped is not None and mapped not in normalized:
            normalized.append(mapped)
    return normalized


def _primary_venue_type(
    venue_types: list[str],
    *,
    requested_types: tuple[str, ...] = DEFAULT_VENUE_TYPES,
) -> str:
    for venue_type in requested_types:
        if venue_type in venue_types:
            return venue_type
    for venue_type in venue_types:
        if venue_type in SUPPORTED_VENUE_TYPES:
            return venue_type
    return "venue"


def _venue_type_for_google_type(raw_type: str) -> str | None:
    mapped = "night_club" if raw_type == "nightclub" else raw_type
    if mapped in SUPPORTED_VENUE_TYPES:
        return mapped
    if mapped in GOOGLE_TYPE_TO_VENUE_TYPE:
        return GOOGLE_TYPE_TO_VENUE_TYPE[mapped]
    if mapped.endswith("_restaurant"):
        return "restaurant"
    return None


def _google_primary_types_for(venue_types: tuple[str, ...]) -> tuple[str, ...]:
    google_types: list[str] = []
    for venue_type in venue_types or DEFAULT_VENUE_TYPES:
        mapped = "night_club" if venue_type == "nightclub" else venue_type
        for google_type in GOOGLE_PRIMARY_TYPES_BY_VENUE_TYPE.get(mapped, (mapped,)):
            if google_type not in google_types:
                google_types.append(google_type)
    return tuple(google_types)


def _per_group_limit(max_results: int, group_count: int) -> int:
    if group_count <= 1:
        return min(max(max_results, 1), 20)
    return min(max(math.ceil(max_results / group_count) + 2, 4), 20)


def _merge_ranked_venue_groups(
    venue_groups: list[list[dict[str, Any]]],
    *,
    lat: float,
    lng: float,
    requested_types: tuple[str, ...],
    max_results: int,
) -> list[dict[str, Any]]:
    ranked_groups = [
        sorted(
            group,
            key=lambda venue: _candidate_sort_key(
                venue,
                lat=lat,
                lng=lng,
                requested_types=requested_types,
            ),
        )
        for group in venue_groups
    ]
    merged: list[dict[str, Any]] = []
    seen_keys: set[str] = set()

    while len(merged) < max_results:
        added_this_round = False
        for group in ranked_groups:
            while group:
                candidate = group.pop(0)
                key = _venue_dedupe_key(candidate)
                if key in seen_keys:
                    continue
                merged.append(candidate)
                seen_keys.add(key)
                added_this_round = True
                break
            if len(merged) >= max_results:
                break
        if not added_this_round:
            break
    return merged


def _candidate_sort_key(
    venue: dict[str, Any],
    *,
    lat: float,
    lng: float,
    requested_types: tuple[str, ...],
) -> tuple[int, int, float, float, float]:
    venue_types = tuple(venue.get("venue_types") or [venue.get("venue_type")])
    type_rank = min(
        (
            requested_types.index(venue_type)
            for venue_type in venue_types
            if venue_type in requested_types
        ),
        default=len(requested_types),
    )
    outdoor_rank = 0 if venue.get("outdoor_seating") is True else 1
    distance = _distance_m({"lat": lat, "lng": lng}, venue.get("location") or {})
    rating = float(venue.get("rating") or 0.0)
    user_rating_count = float(venue.get("user_rating_count") or 0.0)
    return (type_rank, outdoor_rank, distance, -rating, -user_rating_count)


def _venue_dedupe_key(venue: dict[str, Any]) -> str:
    venue_id = venue.get("id")
    if isinstance(venue_id, str) and venue_id.strip() and venue_id != "google:":
        return venue_id
    location = venue.get("location") or {}
    return "|".join(
        [
            str(venue.get("name", "")).casefold(),
            str(round(float(location.get("lat", 0.0)), 5)),
            str(round(float(location.get("lng", 0.0)), 5)),
        ]
    )


def _distance_m(a: dict[str, float], b: dict[str, Any]) -> float:
    if b.get("lat") is None or b.get("lng") is None:
        return float("inf")

    radius = 6371000.0
    d_lat = math.radians(float(b["lat"]) - float(a["lat"]))
    d_lng = math.radians(float(b["lng"]) - float(a["lng"]))
    lat_1 = math.radians(float(a["lat"]))
    lat_2 = math.radians(float(b["lat"]))
    haversine = (
        math.sin(d_lat / 2) ** 2
        + math.cos(lat_1) * math.cos(lat_2) * math.sin(d_lng / 2) ** 2
    )
    return 2 * radius * math.asin(math.sqrt(haversine))


def _response_detail(response: httpx.Response | None) -> str:
    if response is None:
        return "No response body."
    try:
        data = response.json()
    except ValueError:
        text = response.text.strip()
        return text[:200] if text else "No response body."

    error = data.get("error") if isinstance(data, dict) else None
    if isinstance(error, dict):
        message = error.get("message")
        status = error.get("status")
        if message and status:
            return f"{status}: {message}"
        if message:
            return str(message)
    if isinstance(data, dict):
        message = data.get("error_message") or data.get("message")
        if message:
            return str(message)
    return str(data)[:200]
