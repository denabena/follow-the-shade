from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Any


@dataclass(frozen=True)
class AnalysisRecord:
    analysis_id: str
    thread_id: str
    created_at: str
    expires_at: str
    query: str
    parsed_request: dict[str, Any]
    map_payload: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class InMemoryAnalysisStore:
    def __init__(self, ttl_seconds: int = 24 * 60 * 60) -> None:
        self.ttl_seconds = ttl_seconds
        self._records: dict[str, AnalysisRecord] = {}
        self._lock = Lock()

    def save(
        self,
        *,
        analysis_id: str,
        thread_id: str,
        query: str,
        parsed_request: dict[str, Any],
        map_payload: dict[str, Any],
    ) -> AnalysisRecord:
        now = datetime.now(timezone.utc)
        record = AnalysisRecord(
            analysis_id=analysis_id,
            thread_id=thread_id,
            created_at=now.isoformat(),
            expires_at=(now + timedelta(seconds=self.ttl_seconds)).isoformat(),
            query=query,
            parsed_request=parsed_request,
            map_payload=map_payload,
        )
        with self._lock:
            self._records[analysis_id] = record
        return record

    def get(self, analysis_id: str) -> AnalysisRecord | None:
        with self._lock:
            record = self._records.get(analysis_id)
            if record is None:
                return None
            if datetime.fromisoformat(record.expires_at) < datetime.now(timezone.utc):
                self._records.pop(analysis_id, None)
                return None
            return record
