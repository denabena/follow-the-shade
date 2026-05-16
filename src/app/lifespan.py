import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.analysis_store import InMemoryAnalysisStore
from app.state import AppState
from core.config import settings
from core.logging_config import configure_logging
from services.follow_the_shade.agent import FollowTheShadeAgent
from services.follow_the_shade.cache import TtlCache
from tools.find_split_cafe_sun_shade_tool import FindSplitCafeSunShadeTool

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown.

    This mirrors the copied AI repo lifecycle pattern, but keeps the MVP backend
    deterministic until API keys and LangGraph wiring are ready.
    """
    configure_logging()
    log.info("--- Starting Follow the Shade agent ---")

    analysis_store = InMemoryAnalysisStore(ttl_seconds=settings.SESSION_TTL_SECONDS)
    upstream_cache = TtlCache(ttl_seconds=settings.FOLLOW_THE_SHADE_CACHE_TTL_SECONDS)
    tool = FindSplitCafeSunShadeTool(
        analysis_store=analysis_store,
        seed_path=settings.SPLIT_CAFE_SEED_PATH,
        settings=settings,
        upstream_cache=upstream_cache,
    )
    agent = FollowTheShadeAgent(tool=tool)

    app.state.container = AppState(
        settings=settings,
        analysis_store=analysis_store,
        upstream_cache=upstream_cache,
        agent=agent,
    )

    log.info("--- Initialization complete. Server is ready. ---")

    try:
        yield
    finally:
        log.info("--- Server is shutting down. ---")
