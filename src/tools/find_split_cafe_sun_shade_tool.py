from __future__ import annotations

from typing import Any

from app.analysis_store import InMemoryAnalysisStore
from core.config import Settings
from services.follow_the_shade.cache import TtlCache
from services.follow_the_shade.pipeline import FollowTheShadePipeline


class FindSplitCafeSunShadeTool:
    name = "find_split_cafe_sun_shade"

    def __init__(
        self,
        *,
        analysis_store: InMemoryAnalysisStore,
        settings: Settings,
        seed_path: str,
        upstream_cache: TtlCache | None = None,
        data_sources: Any | None = None,
    ) -> None:
        self.analysis_store = analysis_store
        self.pipeline = FollowTheShadePipeline(
            settings,
            seed_path,
            cache=upstream_cache,
            data_sources=data_sources,
        )

    async def arun(self, *, query: str, thread_id: str) -> dict[str, Any]:
        result = await self.pipeline.run(query=query, thread_id=thread_id)
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

    def parse_request(self, query: str):
        return self.pipeline.parse_request(query)
