import json
from dataclasses import asdict, is_dataclass
from datetime import datetime
from typing import Any

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from core.config import Settings
from services.follow_the_shade.cache import TtlCache
from services.follow_the_shade.pipeline import FollowTheShadePipeline
from tools.utils import get_tool_config, override_field_descriptions_from_schema


class ParseSplitRequestInput(BaseModel):
    query: str = Field(
        ...,
        description="Natural-language Split venue request to parse into slots.",
    )


class ParseSplitRequestTool(BaseTool):
    name: str = "parse_split_request"
    description: str = (
        "Parse a Split cafe, restaurant, bar, or nightclub request into structured "
        "slots: venue type, exposure preference, location, time window, date, and what is explicit vs missing. "
        "Use this before deciding what to ask the user or what to fill from preferences."
    )
    args_schema: Any = ParseSplitRequestInput

    pipeline: Any = None

    def __init__(
        self,
        *,
        settings: Settings,
        seed_path: str,
        upstream_cache: TtlCache | None = None,
    ) -> None:
        super().__init__()

        tool_config = get_tool_config(self.name)
        if desc := tool_config.get("description"):
            self.description = desc
        self.args_schema = override_field_descriptions_from_schema(
            ParseSplitRequestInput,
            tool_config.get("args_schema", {}) or {},
        )

        self.pipeline = FollowTheShadePipeline(
            settings,
            seed_path,
            cache=upstream_cache,
        )

    def _run(self, query: str) -> str:
        return self._parse(query)

    async def _arun(self, query: str) -> str:
        return self._parse(query)

    def _parse(self, query: str) -> str:
        parsed = self.pipeline.parse_request(query)
        return json.dumps(
            _parsed_to_dict(parsed), ensure_ascii=False, default=_json_default
        )


def _parsed_to_dict(parsed: Any) -> dict[str, Any]:
    if is_dataclass(parsed):
        data = asdict(parsed)
    elif hasattr(parsed, "model_dump"):
        data = parsed.model_dump()
    else:
        data = dict(parsed.__dict__)
    missing = []
    if not data.get("location_explicit"):
        missing.append("location")
    if not data.get("preference_explicit"):
        missing.append("preference")
    if (
        not data.get("time_explicit")
        or data.get("start") is None
        or data.get("end") is None
    ):
        missing.append("time_window")
    data["missing_slots"] = missing
    data["canonical_area_names"] = [
        "Riva",
        "Bacvice",
        "Marmontova",
        "Varos",
        "Znjan",
        "Matejuska",
        "Prokurative",
        "Firule",
        "West Coast",
        "Sustipan",
        "Diocletian Palace",
        "Pjaca",
    ]
    data["supported_venue_types"] = ["cafe", "restaurant", "bar", "night_club"]
    data["tool_query_guidance"] = (
        "Use canonical ASCII area names in follow-up and analysis tool queries. "
        "For Bačvice/bačvice, write Bacvice. Do not add Riva as a fallback when "
        "the parsed or carried location is another explicit Split area."
    )
    return data


def _json_default(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat(timespec="seconds")
    return str(value)
