from __future__ import annotations

import logging
from typing import Any

import httpx

log = logging.getLogger(__name__)

NEARBY_URL = "https://places.googleapis.com/v1/places:searchNearby"


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
        payload = {
            "includedTypes": ["cafe"],
            "maxResultCount": min(max_results, 12),
            "rankPreference": "POPULARITY",
            "locationRestriction": {
                "circle": {
                    "center": {"latitude": lat, "longitude": lng},
                    "radius": float(min(max(radius_m, 100), 2000)),
                }
            },
        }
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self.api_key,
            "X-Goog-FieldMask": (
                "places.id,places.displayName,places.formattedAddress,"
                "places.location,places.rating,places.userRatingCount,"
                "places.currentOpeningHours,places.googleMapsUri,places.outdoorSeating"
            ),
        }
        try:
            async with httpx.AsyncClient(timeout=12.0) as client:
                response = await client.post(NEARBY_URL, json=payload, headers=headers)
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPError as exc:
            log.warning("Google Places nearby search failed: %s", exc)
            return []

        cafes = []
        for place in data.get("places", []):
            location = place.get("location", {})
            lat_value = location.get("latitude")
            lng_value = location.get("longitude")
            if lat_value is None or lng_value is None:
                continue

            display = place.get("displayName", {})
            name = display.get("text") if isinstance(display, dict) else str(display)
            open_hours = place.get("currentOpeningHours") or {}
            outdoor_seating = place.get("outdoorSeating")
            cafes.append(
                {
                    "id": f"google:{place.get('id', '')}",
                    "name": name or "Unnamed Split cafe",
                    "provider": "google_places",
                    "location": {"lat": float(lat_value), "lng": float(lng_value)},
                    "terrace_point": {"lat": float(lat_value), "lng": float(lng_value)},
                    "address": place.get("formattedAddress") or "Split, Croatia",
                    "rating": place.get("rating"),
                    "user_rating_count": place.get("userRatingCount"),
                    "google_maps_uri": place.get("googleMapsUri"),
                    "is_open_for_window": open_hours.get("openNow", True),
                    "outdoor_seating": outdoor_seating,
                    "outdoor_seating_confidence": "medium"
                    if outdoor_seating is True
                    else "unknown",
                }
            )
        return cafes