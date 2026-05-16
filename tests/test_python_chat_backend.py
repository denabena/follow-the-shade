from fastapi.testclient import TestClient

from app.main import app


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
    assert payload["map_payload"]["results"][0]["name"] == "Riva Shade Table"


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
    assert payload["map_payload"]["results"][0]["name"] == "Bacvice Morning Terrace"


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
