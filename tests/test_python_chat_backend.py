from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.main import app
from services.shadow.shadow_engine import Building
from shapely.geometry import Polygon


def _sample_building() -> list[Building]:
    return [
        Building(
            polygon_wgs84=Polygon(
                [
                    (16.4388, 43.5072),
                    (16.4396, 43.5072),
                    (16.4396, 43.5084),
                    (16.4388, 43.5084),
                    (16.4388, 43.5072),
                ]
            ),
            height_m=14.0,
            height_confidence="levels_estimate",
        )
    ]


def test_final_answer_returns_map_payload() -> None:
    with (
        patch(
            "services.geodata.overpass_client.OverpassClient.fetch_buildings",
            new_callable=AsyncMock,
            return_value=_sample_building(),
        ),
        patch(
            "services.geodata.overpass_client.OverpassClient.fetch_outdoor_seating",
            new_callable=AsyncMock,
            return_value=[],
        ),
        patch(
            "services.weather.open_meteo.OpenMeteoClient.window_weather",
            new_callable=AsyncMock,
            return_value={
                "cloud_cover_avg": 20.0,
                "precipitation_probability_max": 5.0,
            },
        ),
        TestClient(app) as client,
    ):
        response = client.post(
            "/chat/final_answer",
            json={
                "message": "Find me a shady cafe outside near Riva today from 3 to 5pm.",
                "thread_id": "test-thread",
            },
        )

    payload = response.json()
    assert response.status_code == 200
    assert payload["thread_id"] == "test-thread"
    assert payload["analysis_id"]
    assert payload["map_payload"]["request"]["preference"] == "shade"
    assert payload["map_payload"]["results"]
    assert payload["map_payload"]["results"][0]["exposure"]["samples"]


def test_between_and_time_window_returns_map_payload() -> None:
    with (
        patch(
            "services.geodata.overpass_client.OverpassClient.fetch_buildings",
            new_callable=AsyncMock,
            return_value=_sample_building(),
        ),
        patch(
            "services.geodata.overpass_client.OverpassClient.fetch_outdoor_seating",
            new_callable=AsyncMock,
            return_value=[],
        ),
        patch(
            "services.weather.open_meteo.OpenMeteoClient.window_weather",
            new_callable=AsyncMock,
            return_value={
                "cloud_cover_avg": 20.0,
                "precipitation_probability_max": 5.0,
            },
        ),
        TestClient(app) as client,
    ):
        response = client.post(
            "/chat/final_answer",
            json={
                "message": "I want a cafe in the sun on the Riva between 3 and 5pm today.",
                "thread_id": "test-thread",
            },
        )

    payload = response.json()
    assert response.status_code == 200
    assert payload["analysis_id"]
    assert payload["map_payload"]["request"]["preference"] == "sun"
    assert payload["map_payload"]["request"]["start"].endswith(
        "15:00:00+01:00"
    ) or payload["map_payload"]["request"]["start"].endswith("15:00:00+02:00")
    assert payload["map_payload"]["request"]["end"].endswith(
        "17:00:00+01:00"
    ) or payload["map_payload"]["request"]["end"].endswith("17:00:00+02:00")


def test_analysis_recovery_returns_saved_payload() -> None:
    with (
        patch(
            "services.geodata.overpass_client.OverpassClient.fetch_buildings",
            new_callable=AsyncMock,
            return_value=_sample_building(),
        ),
        patch(
            "services.geodata.overpass_client.OverpassClient.fetch_outdoor_seating",
            new_callable=AsyncMock,
            return_value=[],
        ),
        patch(
            "services.weather.open_meteo.OpenMeteoClient.window_weather",
            new_callable=AsyncMock,
            return_value={
                "cloud_cover_avg": 10.0,
                "precipitation_probability_max": 0.0,
            },
        ),
        TestClient(app) as client,
    ):
        chat = client.post(
            "/chat/final_answer",
            json={
                "message": "I want sun around Bacvice tomorrow morning.",
                "thread_id": "test-thread",
            },
        ).json()
        response = client.get(f"/chat/analysis/{chat['analysis_id']}")

    payload = response.json()
    assert response.status_code == 200
    assert payload["analysis_id"] == chat["analysis_id"]
    assert payload["map_payload"]["results"]
    names = " ".join(
        result["name"] for result in payload["map_payload"]["results"]
    ).lower()
    assert "bacvice" in names or any(
        result.get("area", "").lower() == "bacvice"
        for result in payload["map_payload"]["results"]
    )


def test_outside_split_redirect_has_no_map_payload() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/chat/final_answer",
            json={
                "message": "Find me shade on Tkalciceva today from 3 to 5pm.",
                "thread_id": "test-thread",
            },
        )

    payload = response.json()
    assert response.status_code == 200
    assert "focused on Split" in payload["answer"]
    assert payload["analysis_id"] is None
    assert payload["map_payload"] is None


def test_missing_time_asks_clarifying_question() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/chat/final_answer",
            json={
                "query": "I want a shady cafe near Marmontova.",
                "thread_id": "test-thread",
            },
        )

    payload = response.json()
    assert response.status_code == 200
    assert "What time window" in payload["answer"]
    assert payload["map_payload"] is None
