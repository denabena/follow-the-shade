from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.notification_schedule_store import NotificationScheduleStore
from services.notifications.email_sender import ResendEmailSender
from services.notifications.templates import render_digest_email

log = logging.getLogger(__name__)


class NotificationDispatcher:
    def __init__(
        self,
        *,
        schedule_store: NotificationScheduleStore,
        analysis_runner: Any,
        email_sender: ResendEmailSender,
        app_public_url: str = "http://localhost:3000",
        check_interval_seconds: int = 60,
    ) -> None:
        self.schedule_store = schedule_store
        self.analysis_runner = analysis_runner
        self.email_sender = email_sender
        self.app_public_url = app_public_url
        self.check_interval_seconds = max(1, check_interval_seconds)

    def is_due(
        self,
        schedule: dict[str, Any],
        now_utc: datetime | None = None,
    ) -> bool:
        if not schedule.get("enabled"):
            return False
        if not schedule.get("email"):
            return False

        now = (now_utc or datetime.now(UTC)).astimezone(UTC)
        local_now = now.astimezone(_timezone(schedule.get("timezone")))
        if local_now.weekday() not in set(schedule.get("days_of_week") or []):
            return False

        scheduled_time = _parse_time(schedule.get("send_time_local"))
        if scheduled_time is None:
            return False

        scheduled_local = local_now.replace(
            hour=scheduled_time[0],
            minute=scheduled_time[1],
            second=0,
            microsecond=0,
        )
        seconds_after = (local_now - scheduled_local).total_seconds()
        if seconds_after < 0 or seconds_after >= self.check_interval_seconds:
            return False

        last_sent = _parse_utc(schedule.get("last_sent_at_utc"))
        if last_sent is None:
            return True

        last_local = last_sent.astimezone(local_now.tzinfo)
        return last_local.replace(second=0, microsecond=0) != scheduled_local

    def build_query(self, schedule: dict[str, Any]) -> str:
        preference = schedule.get("exposure_preference") or "shade"
        preference_text = "outdoor" if preference == "either" else str(preference)
        area = schedule.get("area") or "Riva"
        preset = schedule.get("time_window_preset") or "afternoon"
        return f"Find me a {preference_text} cafe near {area} today {preset}."

    async def dispatch_once(self, now_utc: datetime | None = None) -> list[dict[str, Any]]:
        sent = []
        now = (now_utc or datetime.now(UTC)).astimezone(UTC)
        for user_id, schedule in self.schedule_store.all_enabled():
            if not self.is_due(schedule, now):
                continue
            result = await self.dispatch_user(user_id, schedule=schedule, now_utc=now)
            if result is not None:
                sent.append(result)
        return sent

    async def dispatch_user(
        self,
        user_id: str,
        *,
        schedule: dict[str, Any] | None = None,
        now_utc: datetime | None = None,
        force: bool = False,
    ) -> dict[str, Any] | None:
        schedule = schedule or self.schedule_store.get(user_id)
        if not force and not self.is_due(schedule, now_utc):
            return None

        email = schedule.get("email")
        if not email:
            log.warning("Skipping notification for %s because email is missing.", user_id)
            return None

        query = self.build_query(schedule)
        result = await self._run_analysis(query=query, thread_id=f"notif-{user_id}")
        map_payload = result.get("map_payload")
        if not map_payload:
            log.warning("Skipping notification for %s because analysis has no map.", user_id)
            return None

        subject, html, text = render_digest_email(
            map_payload,
            schedule,
            app_public_url=self.app_public_url,
        )
        send_result = await self.email_sender.send(
            to=str(email),
            subject=subject,
            html=html,
            text=text,
        )
        sent_at = (now_utc or datetime.now(UTC)).astimezone(UTC)
        self.schedule_store.mark_sent(user_id, sent_at)
        return {
            "user_id": user_id,
            "email": email,
            "subject": subject,
            "analysis_id": map_payload.get("analysis_id"),
            "send_result": send_result,
        }

    async def _run_analysis(self, *, query: str, thread_id: str) -> dict[str, Any]:
        if hasattr(self.analysis_runner, "run_pipeline"):
            return await self.analysis_runner.run_pipeline(
                query=query,
                thread_id=thread_id,
            )
        if hasattr(self.analysis_runner, "arun"):
            return await self.analysis_runner.arun(query=query, thread_id=thread_id)
        return await self.analysis_runner.run(query=query, thread_id=thread_id)


def _timezone(value: Any) -> ZoneInfo:
    try:
        return ZoneInfo(str(value or "Europe/Zagreb"))
    except ZoneInfoNotFoundError:
        return ZoneInfo("Europe/Zagreb")


def _parse_time(value: Any) -> tuple[int, int] | None:
    if not isinstance(value, str):
        return None
    parts = value.split(":", 1)
    if len(parts) != 2:
        return None
    try:
        hour = int(parts[0])
        minute = int(parts[1])
    except ValueError:
        return None
    if hour not in range(24) or minute not in range(60):
        return None
    return hour, minute


def _parse_utc(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    normalised = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalised)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)
