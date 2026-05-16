from datetime import UTC, datetime

from app.notification_schedule_store import NotificationScheduleStore
from services.notifications.dispatcher import NotificationDispatcher


def _dispatcher(tmp_path) -> NotificationDispatcher:
    return NotificationDispatcher(
        schedule_store=NotificationScheduleStore(str(tmp_path / "schedules.json")),
        analysis_runner=object(),
        email_sender=object(),
        check_interval_seconds=60,
    )


def _schedule(**overrides):
    schedule = {
        "enabled": True,
        "email": "ivan@example.com",
        "days_of_week": [5],
        "send_time_local": "12:00",
        "timezone": "Europe/Zagreb",
        "last_sent_at_utc": None,
    }
    schedule.update(overrides)
    return schedule


def test_is_due_matches_weekday_and_local_minute(tmp_path) -> None:
    dispatcher = _dispatcher(tmp_path)
    now = datetime(2026, 5, 16, 10, 0, 30, tzinfo=UTC)

    assert dispatcher.is_due(_schedule(), now)


def test_is_due_skips_wrong_weekday(tmp_path) -> None:
    dispatcher = _dispatcher(tmp_path)
    friday = datetime(2026, 5, 15, 10, 0, tzinfo=UTC)

    assert dispatcher.is_due(_schedule(), friday) is False


def test_is_due_skips_already_sent_local_minute(tmp_path) -> None:
    dispatcher = _dispatcher(tmp_path)
    now = datetime(2026, 5, 16, 10, 0, 30, tzinfo=UTC)

    assert (
        dispatcher.is_due(
            _schedule(last_sent_at_utc="2026-05-16T10:00:10Z"),
            now,
        )
        is False
    )


def test_is_due_respects_timezone(tmp_path) -> None:
    dispatcher = _dispatcher(tmp_path)
    now = datetime(2026, 5, 16, 19, 0, tzinfo=UTC)

    assert dispatcher.is_due(_schedule(send_time_local="21:00"), now)
