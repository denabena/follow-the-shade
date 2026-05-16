import asyncio
from datetime import UTC, datetime

from app.notification_schedule_store import NotificationScheduleStore
from services.notifications.dispatcher import NotificationDispatcher


class FakeRunner:
    async def arun(self, *, query: str, thread_id: str):
        assert "Riva" in query
        assert thread_id == "notif-user_1"
        return {"map_payload": _map_payload()}


class FakeSender:
    def __init__(self) -> None:
        self.sent = []

    async def send(self, *, to: str, subject: str, html: str, text: str):
        self.sent.append(
            {"to": to, "subject": subject, "html": html, "text": text}
        )
        return {"id": "email_1"}


def test_dispatcher_sends_digest_with_top_cafes(tmp_path) -> None:
    asyncio.run(_run_dispatcher_test(tmp_path))


async def _run_dispatcher_test(tmp_path) -> None:
    store = NotificationScheduleStore(str(tmp_path / "schedules.json"))
    store.upsert(
        "user_1",
        {
            "enabled": True,
            "email": "ivan@example.com",
            "days_of_week": [5],
            "send_time_local": "12:00",
            "area": "Riva",
            "time_window_preset": "afternoon",
            "exposure_preference": "shade",
        },
    )
    sender = FakeSender()
    dispatcher = NotificationDispatcher(
        schedule_store=store,
        analysis_runner=FakeRunner(),
        email_sender=sender,
    )

    result = await dispatcher.dispatch_user(
        "user_1",
        force=True,
        now_utc=datetime(2026, 5, 16, 10, 0, tzinfo=UTC),
    )

    assert result["analysis_id"] == "shade_test"
    assert sender.sent[0]["to"] == "ivan@example.com"
    assert "Figa" in sender.sent[0]["subject"] or "Figa" in sender.sent[0]["text"]
    assert "Bokeria" in sender.sent[0]["html"]
    assert store.get("user_1")["last_sent_at_utc"] == "2026-05-16T10:00:00Z"


def _map_payload():
    return {
        "analysis_id": "shade_test",
        "request": {
            "preference": "shade",
            "location_label": "Riva, Split",
            "start": "2026-05-16T14:00:00+02:00",
            "end": "2026-05-16T18:00:00+02:00",
        },
        "results": [
            {
                "name": "Figa",
                "exposure": {
                    "summary": "Mostly shaded from 14:00 to 18:00.",
                    "match_score": 0.92,
                    "samples": [
                        {"time": "2026-05-16T14:00:00+02:00", "state": "shade"}
                    ],
                },
            },
            {
                "name": "Bokeria",
                "exposure": {
                    "summary": "Mostly shaded with a short sunny patch.",
                    "match_score": 0.84,
                    "samples": [
                        {"time": "2026-05-16T15:00:00+02:00", "state": "shade"}
                    ],
                },
            },
        ],
    }
