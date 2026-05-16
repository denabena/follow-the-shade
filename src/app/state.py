from dataclasses import dataclass
from typing import Any

from fastapi import Request


@dataclass
class AppState:
    settings: Any
    analysis_store: Any
    upstream_cache: Any
    preferences_store: Any
    agent: Any | None = None
    agent_app: Any | None = None
    tool_registry: Any | None = None
    config: dict[str, Any] | None = None


def get_state(request: Request) -> AppState:
    return request.app.state.container
