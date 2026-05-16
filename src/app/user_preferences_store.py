from __future__ import annotations

import json
from pathlib import Path
from threading import Lock
from typing import Any, Literal

ExposurePreference = Literal["sun", "shade", "either"]
TimePreset = Literal["morning", "lunch", "afternoon"]

DEFAULT_PREFERENCES: dict[str, Any] = {
    "exposure_preference": "either",
    "favorite_areas": ["Riva"],
    "default_time_preset": "afternoon",
    "digest_enabled": False,
    "avoid_busy": False,
}


class UserPreferencesStore:
    def __init__(self, path: str) -> None:
        self.path = Path(path)
        self._lock = Lock()
        self._data: dict[str, dict[str, Any]] = {}
        self._load()

    def get(self, user_id: str) -> dict[str, Any]:
        with self._lock:
            stored = self._data.get(user_id)
            if stored is None:
                return dict(DEFAULT_PREFERENCES)
            return {**DEFAULT_PREFERENCES, **stored}

    def update(self, user_id: str, patch: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            current = self.get(user_id)
            current.update(patch)
            self._data[user_id] = current
            self._persist()
            return dict(current)

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return
        if isinstance(raw, dict):
            self._data = raw

    def _persist(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self._data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
