import json
from typing import Any, Literal

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from app.analysis_store import InMemoryAnalysisStore
from core.config import Settings
from services.follow_the_shade.cache import TtlCache
from services.follow_the_shade.pipeline import FollowTheShadePipeline
from services.follow_the_shade.thread_context import (
    current_thread_id,
    current_user_query,
)
from tools.utils import get_tool_config, override_field_descriptions_from_schema


class FindSplitCafeSunShadeInput(BaseModel):
    query: str = Field(
        ...,
        description="Complete natural-language Split venue sun/shade request.",
    )
    venue_types: list[Literal["cafe", "restaurant", "bar", "night_club"]] | None = Field(
        default=None,
        description=(
            "Optional exact venue categories requested by the user. Use ['bar'] for bars, pubs, cocktails, wine, beer, or drinks; "
            "['night_club'] for clubs/nightlife/dancing; ['restaurant'] for restaurants, konoba, dinner, pizza, bistro, or grill; "
            "['cafe'] for cafes or coffee. Omit only when the user did not specify a category."
        ),
    )


class FindSplitCafeSunShadeTool(BaseTool):
    name: str = "find_split_cafe_sun_shade"
    description: str = "Run Split venue sun/shade analysis and return map payload JSON."
    args_schema: Any = FindSplitCafeSunShadeInput

    analysis_store: Any = None
    pipeline: Any = None

    def __init__(
        self,
        *,
        analysis_store: InMemoryAnalysisStore,
        settings: Settings,
        seed_path: str,
        upstream_cache: TtlCache | None = None,
        data_sources: Any | None = None,
    ) -> None:
        super().__init__()

        tool_config = get_tool_config(self.name)
        if desc := tool_config.get("description"):
            self.description = desc
        self.args_schema = override_field_descriptions_from_schema(
            FindSplitCafeSunShadeInput,
            tool_config.get("args_schema", {}) or {},
        )

        self.analysis_store = analysis_store
        self.pipeline = FollowTheShadePipeline(
            settings,
            seed_path,
            cache=upstream_cache,
            data_sources=data_sources,
        )

    def _run(
        self,
        query: str,
        venue_types: list[str] | None = None,
    ) -> str:
        raise NotImplementedError("find_split_cafe_sun_shade is async-only")

    async def _arun(
        self,
        query: str,
        venue_types: list[str] | None = None,
    ) -> str:
        thread_id = current_thread_id.get()
        effective_query = query.strip() if isinstance(query, str) else ""
        result = await self.run_pipeline(
            query=effective_query or current_user_query.get() or "",
            thread_id=thread_id,
            venue_types=venue_types,
        )
        return json.dumps(result, ensure_ascii=False)

    async def run_pipeline(
        self,
        *,
        query: str,
        thread_id: str,
        venue_types: list[str] | None = None,
    ) -> dict[str, Any]:
        result = await self.pipeline.run(
            query=query,
            thread_id=thread_id,
            venue_types=venue_types,
        )
        analysis_id = result.get("analysis_id")
        map_payload = result.get("map_payload")
        if analysis_id and map_payload:
            self.analysis_store.save(
                analysis_id=analysis_id,
                thread_id=thread_id,
                query=query,
                parsed_request=map_payload["request"],
                map_payload=map_payload,
            )
        return result

    def parse_request(self, query: str, venue_types: list[str] | None = None):
        return self.pipeline.parse_request(query, venue_types=venue_types)
