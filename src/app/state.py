from dataclasses import dataclass
from typing import Any

from fastapi import Request


@dataclass
class AppState:
    settings: Any
    analysis_store: Any
    upstream_cache: Any
    agent: Any
    preferences_store: Any
    notification_store: Any
    notification_dispatcher: Any | None


def get_state(request: Request) -> AppState:
    return request.app.state.container
