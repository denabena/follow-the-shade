from datetime import UTC, datetime

from app.notification_schedule_store import NotificationScheduleStore


def test_notification_schedule_store_persists_round_trip(tmp_path) -> None:
    path = tmp_path / "notification_schedules.json"
    store = NotificationScheduleStore(str(path))

    saved = store.upsert(
        "user_1",
        {
            "enabled": True,
            "email": "ivan@example.com",
            "days_of_week": [0, 5],
            "send_time_local": "08:30",
            "area": "Riva",
        },
    )
    store.mark_sent("user_1", datetime(2026, 5, 16, 6, 30, tzinfo=UTC))

    reloaded = NotificationScheduleStore(str(path))
    schedule = reloaded.get("user_1")

    assert saved["enabled"] is True
    assert schedule["email"] == "ivan@example.com"
    assert schedule["days_of_week"] == [0, 5]
    assert schedule["last_sent_at_utc"] == "2026-05-16T06:30:00Z"
    assert reloaded.all_enabled()[0][0] == "user_1"


def test_notification_schedule_store_returns_defaults(tmp_path) -> None:
    store = NotificationScheduleStore(str(tmp_path / "missing.json"))

    schedule = store.get("new_user")

    assert schedule["enabled"] is False
    assert schedule["area"] == "Riva"
    assert schedule["send_time_local"] == "12:00"
