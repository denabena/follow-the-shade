import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import yaml
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore

from app.analysis_store import InMemoryAnalysisStore
from app.builders.agent_factory import AgentFactory
from app.builders.graph_factory import GraphFactory
from app.builders.model_factory import ModelFactory
from app.builders.tool_registry import ToolRegistry
from app.notification_schedule_store import NotificationScheduleStore
from app.user_preferences_store import UserPreferencesStore
from app.state import AppState
from core.config import settings
from core.logging_config import configure_logging
from services.follow_the_shade.cache import TtlCache
from services.notifications.dispatcher import NotificationDispatcher
from services.notifications.email_sender import ResendEmailSender
from tools.find_split_cafe_sun_shade_tool import FindSplitCafeSunShadeTool

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown."""
    configure_logging()
    log.info("--- Starting Follow the Shade agent ---")

    analysis_store = InMemoryAnalysisStore(ttl_seconds=settings.SESSION_TTL_SECONDS)
    preferences_store = UserPreferencesStore(settings.USER_PREFERENCES_PATH)
    notification_store = NotificationScheduleStore(
        settings.NOTIFICATIONS_SCHEDULES_PATH
    )
    upstream_cache = TtlCache(ttl_seconds=settings.FOLLOW_THE_SHADE_CACHE_TTL_SECONDS)
    analysis_tool = FindSplitCafeSunShadeTool(
        analysis_store=analysis_store,
        settings=settings,
        seed_path=settings.SPLIT_CAFE_SEED_PATH,
        upstream_cache=upstream_cache,
    )
    config_data = _load_agent_config()
    models = config_data.get("models", [])
    agents = config_data.get("agents", [])
    tools_config = config_data.get("tools", [])
    swarm = config_data.get("swarm_config", {})
    agent_app = None
    tool_registry = None

    if settings.OPENAI_API_KEY:
        _validate_runtime_config(models=models, agents=agents, swarm=swarm)
        model_factory = ModelFactory(model_configs=models)
        tool_registry = ToolRegistry(
            dependencies={
                "analysis_store": analysis_store,
                "settings": settings,
                "seed_path": settings.SPLIT_CAFE_SEED_PATH,
                "upstream_cache": upstream_cache,
                "preferences_store": preferences_store,
                "find_split_cafe_sun_shade": analysis_tool,
            },
            agents=agents,
        )
        agent_factory = AgentFactory(
            agents_config=agents,
            model_factory=model_factory,
            tool_registry=tool_registry,
            tools_config=tools_config,
        )
        graph_factory = GraphFactory(
            agents_config=agents,
            agent_factory=agent_factory,
            default_agent_name=swarm["default_agent_name"],
        )
        agent_app = graph_factory.build(
            checkpointer=InMemorySaver(),
            store=InMemoryStore(),
        )
        await tool_registry.initialize_async_tools()
    else:
        log.error("OPENAI_API_KEY is not configured; chat agent will be unavailable.")

    notification_dispatcher = NotificationDispatcher(
        schedule_store=notification_store,
        analysis_runner=analysis_tool,
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
        preferences_store=preferences_store,
        notification_store=notification_store,
        notification_dispatcher=notification_dispatcher,
        agent_app=agent_app,
        tool_registry=tool_registry,
        analysis_tool=analysis_tool,
        config={"models": models, "agents": agents, "swarm_config": swarm},
    )

    log.info("--- Initialization complete. Server is ready. ---")

    try:
        yield
    finally:
        if scheduler is not None:
            scheduler.shutdown(wait=False)
        if tool_registry is not None:
            await tool_registry.shutdown_async_tools()
        log.info("--- Server is shutting down. ---")


def _load_agent_config() -> dict[str, Any]:
    config_path = Path(settings.AGENT_CONFIG_PATH)
    if not config_path.is_absolute():
        config_path = Path.cwd() / config_path
    if not config_path.exists():
        raise FileNotFoundError(f"Agent config file not found: {config_path}")
    with config_path.open("r", encoding="utf-8") as config_file:
        return yaml.safe_load(config_file) or {}


def _validate_runtime_config(
    *,
    models: list[dict[str, Any]],
    agents: list[dict[str, Any]],
    swarm: dict[str, Any],
) -> None:
    model_by_name = {model.get("name"): model for model in models}
    default_agent = swarm.get("default_agent_name")
    if not default_agent:
        raise RuntimeError("swarm_config.default_agent_name is required.")
    if default_agent not in {agent.get("name") for agent in agents}:
        raise RuntimeError(f"Default agent '{default_agent}' is not configured.")
    for agent in agents:
        model_name = agent.get("model")
        if model_name not in model_by_name:
            raise RuntimeError(
                f"Agent '{agent.get('name')}' references unknown model '{model_name}'."
            )
