from __future__ import annotations

import logging
from typing import Any

import httpx

log = logging.getLogger(__name__)

NEARBY_NEW_URL = "https://places.googleapis.com/v1/places:searchNearby"
NEARBY_LEGACY_URL = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
DEFAULT_VENUE_TYPES = ("cafe", "restaurant", "bar", "night_club")
SUPPORTED_VENUE_TYPES = set(DEFAULT_VENUE_TYPES)


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
        payload = {
            "includedTypes": list(venue_types),
            "maxResultCount": max_results,
            "rankPreference": "POPULARITY",
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
                "places.regularOpeningHours,places.googleMapsUri,places.outdoorSeating,"
                "places.photos,places.primaryType,places.types"
            ),
        }
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
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
            venue = _normalize_new_place(place)
            if venue is not None:
                venues.append(venue)
        return venues

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


def _normalize_new_place(place: dict[str, Any]) -> dict[str, Any] | None:
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
    venue_type = _primary_venue_type(venue_types)

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
        "is_open_for_window": regular_hours.get("openNow", True),
        "outdoor_seating": place.get("outdoorSeating"),
        "outdoor_seating_confidence": (
            "medium" if place.get("outdoorSeating") is True else "unknown"
        ),
    }


def _normalize_legacy_place(
    place: dict[str, Any], requested_type: str
) -> dict[str, Any] | None:
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
    venue_type = _primary_venue_type(venue_types)

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
        mapped = "night_club" if raw_type == "nightclub" else raw_type
        if mapped in SUPPORTED_VENUE_TYPES and mapped not in normalized:
            normalized.append(mapped)
    return normalized


def _primary_venue_type(venue_types: list[str]) -> str:
    for venue_type in venue_types:
        if venue_type in SUPPORTED_VENUE_TYPES:
            return venue_type
    return "venue"


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
