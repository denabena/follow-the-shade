from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Any

DEFAULT_NOTIFICATION_SCHEDULE: dict[str, Any] = {
    "enabled": False,
    "email": None,
    "days_of_week": [5],
    "send_time_local": "12:00",
    "timezone": "Europe/Zagreb",
    "area": "Riva",
    "time_window_preset": "afternoon",
    "exposure_preference": "shade",
    "last_sent_at_utc": None,
}


class NotificationScheduleStore:
    def __init__(self, path: str) -> None:
        self.path = Path(path)
        self._lock = Lock()
        self._data: dict[str, dict[str, Any]] = {}
        self._load()

    def get(self, user_id: str) -> dict[str, Any]:
        with self._lock:
            return self._with_defaults(self._data.get(user_id))

    def upsert(self, user_id: str, schedule: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            current = self._with_defaults(self._data.get(user_id))
            current.update(schedule)
            self._data[user_id] = current
            self._persist()
            return deepcopy(current)

    def all_enabled(self) -> list[tuple[str, dict[str, Any]]]:
        with self._lock:
            return [
                (user_id, self._with_defaults(schedule))
                for user_id, schedule in self._data.items()
                if schedule.get("enabled") is True
            ]

    def mark_sent(self, user_id: str, when_utc: datetime) -> dict[str, Any]:
        sent_at = when_utc.replace(microsecond=0).isoformat().replace("+00:00", "Z")
        with self._lock:
            current = self._with_defaults(self._data.get(user_id))
            current["last_sent_at_utc"] = sent_at
            self._data[user_id] = current
            self._persist()
            return deepcopy(current)

    def _with_defaults(self, schedule: dict[str, Any] | None) -> dict[str, Any]:
        return {**deepcopy(DEFAULT_NOTIFICATION_SCHEDULE), **(schedule or {})}

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return
        if isinstance(raw, dict):
            self._data = {
                str(user_id): schedule
                for user_id, schedule in raw.items()
                if isinstance(schedule, dict)
            }

    def _persist(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self._data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
