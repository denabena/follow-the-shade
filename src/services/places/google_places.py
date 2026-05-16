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
                "places.regularOpeningHours,places.googleMapsUri,places.outdoorSeating"
            ),
        }
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.post(NEARBY_URL, json=payload, headers=headers)
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPError as exc:
            log.warning("Google Places nearby search failed: %s", exc)
            return []

        cafes = []
        for place in data.get("places", []):
            location = place.get("location", {})
            lat_v = location.get("latitude")
            lng_v = location.get("longitude")
            if lat_v is None or lng_v is None:
                continue
            display = place.get("displayName", {})
            name = display.get("text") if isinstance(display, dict) else str(display)
            cafes.append(
                {
                    "id": f"google:{place.get('id', '')}",
                    "name": name or "Cafe",
                    "provider": "google_places",
                    "location": {"lat": lat_v, "lng": lng_v},
                    "terrace_point": {"lat": lat_v, "lng": lng_v},
                    "address": place.get("formattedAddress"),
                    "rating": place.get("rating"),
                    "user_rating_count": place.get("userRatingCount"),
                    "google_maps_uri": place.get("googleMapsUri"),
                    "outdoor_seating": place.get("outdoorSeating"),
                    "outdoor_seating_confidence": "medium"
                    if place.get("outdoorSeating") is True
                    else "unknown",
                }
            )
        return cafes
