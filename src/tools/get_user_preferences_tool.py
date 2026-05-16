import json
from typing import Any

from langchain_core.tools import BaseTool
from pydantic import BaseModel

from app.user_preferences_store import DEFAULT_PREFERENCES, UserPreferencesStore
from services.follow_the_shade.thread_context import current_user_id
from tools.utils import get_tool_config, override_field_descriptions_from_schema


class GetUserPreferencesInput(BaseModel):
    pass


class GetUserPreferencesTool(BaseTool):
    name: str = "get_user_preferences"
    description: str = (
        "Read the signed-in user's saved Follow the Shade preferences "
        "(exposure preference, favorite areas, default time preset, avoid_busy). "
        "Returns defaults when no user is signed in or no preferences are stored."
    )
    args_schema: Any = GetUserPreferencesInput

    preferences_store: Any = None

    def __init__(self, *, preferences_store: UserPreferencesStore) -> None:
        super().__init__()

        tool_config = get_tool_config(self.name)
        if desc := tool_config.get("description"):
            self.description = desc
        self.args_schema = override_field_descriptions_from_schema(
            GetUserPreferencesInput,
            tool_config.get("args_schema", {}) or {},
        )

        self.preferences_store = preferences_store

    def _run(self) -> str:
        return self._fetch()

    async def _arun(self) -> str:
        return self._fetch()

    def _fetch(self) -> str:
        user_id = current_user_id.get()
        if not user_id:
            payload = {
                "signed_in": False,
                "preferences": dict(DEFAULT_PREFERENCES),
                "note": "No signed-in user; defaults returned.",
            }
        else:
            payload = {
                "signed_in": True,
                "user_id": user_id,
                "preferences": self.preferences_store.get(user_id),
            }
        return json.dumps(payload, ensure_ascii=False)
