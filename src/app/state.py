from dataclasses import dataclass
from typing import Any

from fastapi import Request


@dataclass
class AppState:
    settings: Any
    analysis_store: Any
    agent: Any


def get_state(request: Request) -> AppState:
    return request.app.state.container
