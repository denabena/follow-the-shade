import logging
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI

from app.analysis_store import InMemoryAnalysisStore
from app.notification_schedule_store import NotificationScheduleStore
from app.user_preferences_store import UserPreferencesStore
from app.state import AppState
from core.config import settings
from core.logging_config import configure_logging
from services.follow_the_shade.agent import FollowTheShadeAgent
from services.follow_the_shade.cache import TtlCache
from services.notifications.dispatcher import NotificationDispatcher
from services.notifications.email_sender import ResendEmailSender
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
    preferences_store = UserPreferencesStore(settings.USER_PREFERENCES_PATH)
    notification_store = NotificationScheduleStore(settings.NOTIFICATIONS_SCHEDULES_PATH)
    upstream_cache = TtlCache(ttl_seconds=settings.FOLLOW_THE_SHADE_CACHE_TTL_SECONDS)
    tool = FindSplitCafeSunShadeTool(
        analysis_store=analysis_store,
        settings=settings,
        seed_path=settings.SPLIT_CAFE_SEED_PATH,
        upstream_cache=upstream_cache,
    )
    agent = FollowTheShadeAgent(tool=tool)
    notification_dispatcher = NotificationDispatcher(
        schedule_store=notification_store,
        analysis_runner=tool,
        email_sender=ResendEmailSender(
            api_key=settings.RESEND_API_KEY,
            from_email=settings.RESEND_FROM_EMAIL,
            dry_run=settings.NOTIFICATIONS_DRY_RUN,
        ),
        app_public_url=settings.APP_PUBLIC_URL,
        check_interval_seconds=settings.NOTIFICATIONS_CHECK_INTERVAL_SECONDS,
    )
    scheduler = None

    if settings.NOTIFICATIONS_ENABLED:
        scheduler = AsyncIOScheduler(timezone="UTC")
        scheduler.add_job(
            notification_dispatcher.dispatch_once,
            "interval",
            seconds=settings.NOTIFICATIONS_CHECK_INTERVAL_SECONDS,
            id="notification-dispatch",
            max_instances=1,
            coalesce=True,
        )
        scheduler.start()
        log.info("--- Notification scheduler started. ---")

    app.state.container = AppState(
        settings=settings,
        analysis_store=analysis_store,
        upstream_cache=upstream_cache,
        agent=agent,
        preferences_store=preferences_store,
        notification_store=notification_store,
        notification_dispatcher=notification_dispatcher,
    )

    log.info("--- Initialization complete. Server is ready. ---")

    try:
        yield
    finally:
        if scheduler is not None:
            scheduler.shutdown(wait=False)
        log.info("--- Server is shutting down. ---")
