import asyncio
from unittest.mock import AsyncMock, patch

import httpx

from services.places.google_places import (
    NEARBY_LEGACY_URL,
    NEARBY_NEW_URL,
    GooglePlacesClient,
)


def _json_response(
    method: str, url: str, status_code: int, payload: dict
) -> httpx.Response:
    return httpx.Response(
        status_code,
        request=httpx.Request(method, url),
        json=payload,
    )


def test_google_places_falls_back_to_legacy_nearby_search_on_403() -> None:
    new_response = _json_response(
        "POST",
        NEARBY_NEW_URL,
        403,
        {
            "error": {
                "status": "PERMISSION_DENIED",
                "message": "Places API (New) is not enabled for this key.",
            }
        },
    )
    legacy_response = _json_response(
        "GET",
        NEARBY_LEGACY_URL,
        200,
        {
            "status": "OK",
            "results": [
                {
                    "place_id": "legacy-place-1",
                    "name": "Legacy Cafe",
                    "geometry": {"location": {"lat": 43.5081, "lng": 16.4391}},
                    "vicinity": "Riva, Split",
                    "rating": 4.4,
                    "user_ratings_total": 120,
                    "opening_hours": {"open_now": True},
                }
            ],
        },
    )

    with (
        patch(
            "httpx.AsyncClient.post", new_callable=AsyncMock, return_value=new_response
        ) as post_mock,
        patch(
            "httpx.AsyncClient.get",
            new_callable=AsyncMock,
            return_value=legacy_response,
        ) as get_mock,
    ):
        cafes = asyncio.run(
            GooglePlacesClient("test-key").nearby_cafes(43.5081, 16.4391)
        )

    assert post_mock.await_count == 1
    assert get_mock.await_count == 1
    assert cafes[0]["name"] == "Legacy Cafe"
    assert cafes[0]["location"] == {"lat": 43.5081, "lng": 16.4391}
    assert cafes[0]["is_open_for_window"] is True
    assert cafes[0]["outdoor_seating_confidence"] == "unknown"


def test_google_places_uses_new_api_when_available() -> None:
    new_response = _json_response(
        "POST",
        NEARBY_NEW_URL,
        200,
        {
            "places": [
                {
                    "id": "new-place-1",
                    "displayName": {"text": "New API Cafe"},
                    "formattedAddress": "Split, Croatia",
                    "location": {"latitude": 43.5081, "longitude": 16.4391},
                    "rating": 4.7,
                    "userRatingCount": 88,
                    "regularOpeningHours": {"openNow": False},
                    "googleMapsUri": "https://maps.app.goo.gl/demo",
                    "outdoorSeating": True,
                }
            ]
        },
    )

    with (
        patch(
            "httpx.AsyncClient.post", new_callable=AsyncMock, return_value=new_response
        ) as post_mock,
        patch("httpx.AsyncClient.get", new_callable=AsyncMock) as get_mock,
    ):
        cafes = asyncio.run(
            GooglePlacesClient("test-key").nearby_cafes(43.5081, 16.4391)
        )

    assert post_mock.await_count == 1
    assert get_mock.await_count == 0
    assert cafes[0]["name"] == "New API Cafe"
    assert cafes[0]["is_open_for_window"] is False
    assert cafes[0]["outdoor_seating"] is True
