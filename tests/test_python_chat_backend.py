import asyncio
import json
from datetime import datetime
from unittest.mock import AsyncMock, patch
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage, ToolMessage

from app.api.chat.generate_answer import run_chat_flow
from core.config import settings
from app.main import app
from services.follow_the_shade.pipeline import FollowTheShadePipeline
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


def test_around_single_time_returns_bacvice_shade_payload() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/chat/final_answer",
            json={
                "message": "Find me a shady spot near Bacvice around 4pm.",
                "thread_id": "around-time-thread",
            },
        )

    payload = response.json()
    assert response.status_code == 200
    assert payload["analysis_id"]
    request = payload["map_payload"]["request"]
    assert request["preference"] == "shade"
    assert request["location_label"] == "Bacvice, Split"
    assert request["start"].endswith("15:30:00+01:00") or request["start"].endswith(
        "15:30:00+02:00"
    )
    assert request["end"].endswith("16:30:00+01:00") or request["end"].endswith(
        "16:30:00+02:00"
    )


def test_restaurant_request_returns_restaurant_venue_payload() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/chat/final_answer",
            json={
                "message": "Find me a shady restaurant near Riva today from 3 to 5pm.",
                "thread_id": "restaurant-type-thread",
            },
        )

    payload = response.json()
    assert response.status_code == 200
    request = payload["map_payload"]["request"]
    assert request["venue_types"] == ["restaurant"]
    assert payload["map_payload"]["results"]
    assert all(
        "restaurant" in result.get("venue_types", [result.get("venue_type")])
        for result in payload["map_payload"]["results"]
    )


def test_parser_ignores_iso_date_when_reading_afternoon_window() -> None:
    pipeline = FollowTheShadePipeline(settings, settings.SPLIT_CAFE_SEED_PATH)
    parsed = pipeline.parse_request(
        "Find me somewhere shady to sit in Varos on 2026-05-16 this afternoon.",
        now=datetime(2026, 5, 16, 12, tzinfo=ZoneInfo("Europe/Zagreb")),
    )

    assert parsed.location_label == "Varos, Split"
    assert parsed.period == "afternoon"
    assert parsed.start is not None
    assert parsed.end is not None
    assert parsed.start.hour == 14
    assert parsed.end.hour == 18


def test_time_clarification_keeps_thread_location_and_preference() -> None:
    with TestClient(app) as client:
        first = client.post(
            "/chat/final_answer",
            json={
                "message": "Find me a shady spot near Bacvice.",
                "thread_id": "carry-context-thread",
            },
        ).json()
        response = client.post(
            "/chat/final_answer",
            json={
                "message": "today from 3 to 5pm",
                "thread_id": "carry-context-thread",
            },
        )

    payload = response.json()
    assert first["map_payload"] is None
    assert response.status_code == 200
    request = payload["map_payload"]["request"]
    assert request["preference"] == "shade"
    assert request["location_label"] == "Bacvice, Split"


def test_point_time_clarification_keeps_thread_location_and_preference() -> None:
    with TestClient(app) as client:
        first = client.post(
            "/chat/final_answer",
            json={
                "message": "Find me a shady spot near Bacvice.",
                "thread_id": "carry-point-time-thread",
            },
        ).json()
        response = client.post(
            "/chat/final_answer",
            json={
                "message": "around 4pm.",
                "thread_id": "carry-point-time-thread",
            },
        )

    payload = response.json()
    assert first["map_payload"] is None
    assert response.status_code == 200
    request = payload["map_payload"]["request"]
    assert request["preference"] == "shade"
    assert request["location_label"] == "Bacvice, Split"
    assert request["start"].endswith("15:30:00+01:00") or request["start"].endswith(
        "15:30:00+02:00"
    )
    assert request["end"].endswith("16:30:00+01:00") or request["end"].endswith(
        "16:30:00+02:00"
    )


def test_open_meteo_rain_blocks_usable_direct_sun() -> None:
    with (
        patch.object(settings, "FOLLOW_THE_SHADE_DATA_MODE", "actual"),
        patch(
            "services.places.google_places.GooglePlacesClient.nearby_venues",
            new_callable=AsyncMock,
            return_value=[],
        ),
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
                "cloud_cover_avg": 96.0,
                "precipitation_probability_max": 85.0,
                "precipitation_mm_max": 0.4,
            },
        ),
        TestClient(app) as client,
    ):
        response = client.post(
            "/chat/final_answer",
            json={
                "message": "I want sun around Bacvice today from 3 to 5pm.",
                "thread_id": "weather-block-thread",
            },
        )

    payload = response.json()
    assert response.status_code == 200
    answer = payload["answer"].lower()
    assert "rain" in answer or "heavy cloud" in answer
    assert "direct sun" in answer
    assert "Open-Meteo" not in payload["answer"]
    assert "estimated" not in payload["answer"].lower()
    result = payload["map_payload"]["results"][0]
    assert result["exposure"]["sun_ratio"] == 0.0
    assert all(sample["state"] == "shade" for sample in result["exposure"]["samples"])
    assert result["weather"]["precipitation_mm_max"] == 0.4


def test_pipeline_injects_google_places_and_weather_answer_facts() -> None:
    google_cafes = [
        {
            "id": "google:places-cafe-1",
            "name": "Places View Cafe",
            "provider": "google_places",
            "location": {"lat": 43.5082, "lng": 16.4392},
            "terrace_point": {"lat": 43.5082, "lng": 16.4392},
            "address": "Riva, Split",
            "rating": 4.8,
            "user_rating_count": 240,
            "google_maps_uri": "https://maps.example/places-cafe-1",
            "is_open_for_window": True,
            "outdoor_seating": True,
            "outdoor_seating_confidence": "medium",
        }
    ]

    with (
        patch.object(settings, "FOLLOW_THE_SHADE_DATA_MODE", "actual"),
        patch.object(settings, "GOOGLE_PLACES_API_KEY", "test-key"),
        patch(
            "services.places.google_places.GooglePlacesClient.nearby_venues",
            new_callable=AsyncMock,
            return_value=google_cafes,
        ),
        patch(
            "services.geodata.overpass_client.OverpassClient.fetch_buildings",
            new_callable=AsyncMock,
            return_value=[],
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
                "cloud_cover_avg": 72.0,
                "precipitation_probability_max": 10.0,
                "precipitation_mm_max": 0.0,
            },
        ),
    ):
        pipeline = FollowTheShadePipeline(settings, settings.SPLIT_CAFE_SEED_PATH)
        result = asyncio.run(
            pipeline.run(
                query="I want sun near Riva today from 3 to 5pm.",
                thread_id="answer-facts-thread",
            )
        )

    facts = result["answer_facts"]
    assert facts["weather"]["impact"] == "sun_muted"
    assert facts["weather"]["cloud_cover_avg"] == 72
    assert facts["source_context"]["uses_google_places"] is True
    assert facts["source_context"]["uses_open_meteo"] is True

    places_match = next(
        match for match in facts["best_matches"] if match["name"] == "Places View Cafe"
    )
    assert places_match["rating"] == 4.8
    assert places_match["user_rating_count"] == 240
    assert places_match["samples"]


def test_run_chat_flow_prefers_agent_recommendation_over_tool_fallback() -> None:
    final_answer = "Konoba-style pick: Places View Cafe is the best fit because its terrace stays sunny, with cloud cover softening the glare."
    tool_payload = {
        "answer": "I found 4 sunny options near Riva, Split for 15:00-17:00.",
        "analysis_id": "shade_20260516_test",
        "answer_facts": {
            "best_matches": [{"name": "Places View Cafe"}],
            "weather": {"impact": "sun_muted"},
        },
        "map_payload": {
            "request": {"preference": "sun"},
            "results": [],
        },
        "sources": [],
    }

    class FakeAgentApp:
        async def ainvoke(self, _state, _config):
            return {
                "messages": [
                    ToolMessage(
                        content=json.dumps(tool_payload),
                        tool_call_id="call-find-shade",
                    ),
                    AIMessage(content=final_answer),
                ]
            }

    result = asyncio.run(
        run_chat_flow(
            input_text="Find me sun near Riva from 3 to 5pm.",
            thread_id="agent-answer-thread",
            agent_app=FakeAgentApp(),
        )
    )

    assert result.answer == final_answer
    assert result.analysis_id == "shade_20260516_test"
    assert result.answer_facts == tool_payload["answer_facts"]
