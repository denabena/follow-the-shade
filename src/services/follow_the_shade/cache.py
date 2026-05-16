from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Any


@dataclass(frozen=True)
class CacheEntry:
    value: Any
    expires_at: datetime


class TtlCache:
    def __init__(self, ttl_seconds: int) -> None:
        self.ttl_seconds = ttl_seconds
        self._items: dict[str, CacheEntry] = {}
        self._lock = Lock()

    def get(self, key: str) -> Any | None:
        with self._lock:
            entry = self._items.get(key)
            if entry is None:
                return None
            if entry.expires_at <= datetime.now(timezone.utc):
                self._items.pop(key, None)
                return None
            return entry.value

    def set(self, key: str, value: Any, ttl_seconds: int | None = None) -> None:
        expires_at = datetime.now(timezone.utc) + timedelta(
            seconds=ttl_seconds or self.ttl_seconds
        )
        with self._lock:
            self._items[key] = CacheEntry(value=value, expires_at=expires_at)

    @staticmethod
    def make_key(namespace: str, payload: dict[str, Any]) -> str:
        serialized = json.dumps(payload, sort_keys=True, default=str)
        digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:16]
        return f"{namespace}:{digest}"