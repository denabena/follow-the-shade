from __future__ import annotations

import logging
from typing import Any

import httpx

log = logging.getLogger(__name__)

NEARBY_NEW_URL = "https://places.googleapis.com/v1/places:searchNearby"
NEARBY_LEGACY_URL = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"


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
        cafes = await self._nearby_cafes_new(
            lat,
            lng,
            radius_m=radius_m,
            max_results=max_results,
        )
        if cafes is not None:
            return cafes
        return await self._nearby_cafes_legacy(
            lat,
            lng,
            radius_m=radius_m,
            max_results=max_results,
        )

    async def _nearby_cafes_new(
        self,
        lat: float,
        lng: float,
        *,
        radius_m: int,
        max_results: int,
    ) -> list[dict[str, Any]] | None:
        payload = {
            "includedTypes": ["cafe"],
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
                "places.photos"
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
                    "Google Places New nearby search rejected (%s): %s. Falling back to legacy nearby search.",
                    status_code,
                    detail,
                )
                return None
            log.warning(
                "Google Places New nearby search failed (%s): %s",
                status_code,
                detail,
            )
            return []
        except httpx.HTTPError as exc:
            log.warning("Google Places New nearby search failed: %s", exc)
            return []

        cafes = []
        for place in data.get("places", []):
            cafe = _normalize_new_place(place)
            if cafe is not None:
                cafes.append(cafe)
        return cafes

    async def _nearby_cafes_legacy(
        self,
        lat: float,
        lng: float,
        *,
        radius_m: int,
        max_results: int,
    ) -> list[dict[str, Any]]:
        params = {
            "location": f"{lat},{lng}",
            "radius": str(radius_m),
            "type": "cafe",
            "key": self.api_key,
        }
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.get(NEARBY_LEGACY_URL, params=params)
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPStatusError as exc:
            log.warning(
                "Google Places legacy nearby search failed (%s): %s",
                exc.response.status_code if exc.response is not None else "unknown",
                _response_detail(exc.response),
            )
            return []
        except httpx.HTTPError as exc:
            log.warning("Google Places legacy nearby search failed: %s", exc)
            return []

        api_status = data.get("status")
        if api_status not in {"OK", "ZERO_RESULTS"}:
            log.warning(
                "Google Places legacy nearby search failed (%s): %s",
                api_status,
                data.get("error_message") or "No error message provided.",
            )
            return []

        cafes = []
        for place in data.get("results", [])[:max_results]:
            cafe = _normalize_legacy_place(place)
            if cafe is not None:
                cafes.append(cafe)
        return cafes


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

    return {
        "id": f"google:{place.get('id', '')}",
        "name": name or "Cafe",
        "provider": "google_places",
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


def _normalize_legacy_place(place: dict[str, Any]) -> dict[str, Any] | None:
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
    return {
        "id": f"google:{place_id or ''}",
        "name": place.get("name") or "Cafe",
        "provider": "google_places",
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
