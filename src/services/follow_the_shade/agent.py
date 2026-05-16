from __future__ import annotations

from tools.find_split_cafe_sun_shade_tool import FindSplitCafeSunShadeTool


class FollowTheShadeAgent:
    """Small deterministic agent facade.

    The copied AI backend used LangGraph behind this boundary. For the hackathon
    backend MVP, this facade calls the one composite tool directly so the API is
    useful before model keys and full geospatial services are ready.
    """

    def __init__(self, tool: FindSplitCafeSunShadeTool) -> None:
        self.tool = tool

    async def answer(self, *, message: str, thread_id: str) -> dict:
        return await self.tool.arun(query=message, thread_id=thread_id)
