import asyncio

from fastapi.testclient import TestClient
from shapely.geometry import Polygon

from app.main import app
from app.analysis_store import InMemoryAnalysisStore
from services.follow_the_shade.data_sources import (
    BuildingSummary,
    CafeCandidateBundle,
    WeatherSummary,
)
from services.shadow.shadow_engine import Building
from tools.find_split_cafe_sun_shade_tool import FindSplitCafeSunShadeTool


def test_final_answer_returns_map_payload() -> None:
    with TestClient(app) as client:
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
    assert payload["map_payload"]["results"][0]["exposure"]["preference"] == "shade"


def test_analysis_recovery_returns_saved_payload() -> None:
    with TestClient(app) as client:
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
    assert payload["map_payload"]["request"]["preference"] == "sun"
    assert payload["map_payload"]["results"]


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


class FakeGeometrySources:
    async def cafe_candidates(self, *, center, radius_m, limit):
        return CafeCandidateBundle(
            cafes=[
                {
                    "id": "fake:cafe",
                    "name": "Geometry Cafe",
                    "area": "Riva",
                    "provider": "fake",
                    "location": {"lat": 43.5081, "lng": 16.4391},
                    "terrace_point": {"lat": 43.5081, "lng": 16.4391},
                    "address": "Riva, Split",
                    "rating": 4.5,
                    "user_rating_count": 12,
                    "is_open_for_window": True,
                    "outdoor_seating_confidence": "medium",
                    "patterns": {
                        "morning": ["sun", "sun"],
                        "lunch": ["sun", "shade"],
                        "afternoon": ["shade", "shade"],
                    },
                }
            ],
            source_notes=["Cafe metadata from fake source."],
        )

    async def building_summary(self, *, center, radius_m):
        building = Building(
            polygon_wgs84=Polygon(
                [
                    (16.4389, 43.5080),
                    (16.4390, 43.5080),
                    (16.4390, 43.5081),
                    (16.4389, 43.5081),
                    (16.4389, 43.5080),
                ]
            ),
            height_m=9.0,
            height_confidence="default_estimate",
        )
        return BuildingSummary(
            buildings=[building],
            building_count=1,
            height_tag_count=0,
            source_notes=["Building geometry from fake Overpass."],
            uncertainty_notes=["Some OSM buildings lack heights."],
        )

    async def weather_summary(self, *, center, start, end):
        return WeatherSummary(
            cloud_cover_avg=25,
            precipitation_probability_max=0,
            source_notes=["Weather context from fake Open-Meteo."],
        )


def test_tool_uses_geometry_when_buildings_available() -> None:
    tool = FindSplitCafeSunShadeTool(
        analysis_store=InMemoryAnalysisStore(),
        seed_path="assets/split_cafe_seed.json",
        data_sources=FakeGeometrySources(),
    )

    result = asyncio.run(
        tool.arun(
            query="Find me a shady cafe outside near Riva today from 3 to 5pm.",
            thread_id="geometry-thread",
        )
    )

    assert result["analysis_id"]
    assert "Astral/Shapely" in " ".join(result["map_payload"]["source_notes"])
    assert result["map_payload"]["results"][0]["weather"]["cloud_cover_avg"] == 25
    assert "building" in " ".join(
        result["map_payload"]["results"][0]["exposure"]["confidence_reasons"]
    )
