import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import yaml
from fastapi import FastAPI
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore

from app.analysis_store import InMemoryAnalysisStore
from app.builders.agent_factory import AgentFactory
from app.builders.graph_factory import GraphFactory
from app.builders.model_factory import ModelFactory
from app.builders.tool_registry import ToolRegistry
from app.state import AppState
from app.user_preferences_store import UserPreferencesStore
from core.config import settings
from core.logging_config import configure_logging
from services.follow_the_shade.agent import FollowTheShadeAgent
from services.follow_the_shade.cache import TtlCache
from tools.find_split_cafe_sun_shade_tool import FindSplitCafeSunShadeTool

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown."""
    configure_logging()
    log.info("--- Starting Follow the Shade agent ---")

    analysis_store = InMemoryAnalysisStore(ttl_seconds=settings.SESSION_TTL_SECONDS)
    preferences_store = UserPreferencesStore(settings.USER_PREFERENCES_PATH)
    upstream_cache = TtlCache(ttl_seconds=settings.FOLLOW_THE_SHADE_CACHE_TTL_SECONDS)
    fallback_tool = FindSplitCafeSunShadeTool(
        analysis_store=analysis_store,
        settings=settings,
        seed_path=settings.SPLIT_CAFE_SEED_PATH,
        upstream_cache=upstream_cache,
    )
    fallback_agent = FollowTheShadeAgent(tool=fallback_tool)

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
        log.warning(
            "OPENAI_API_KEY is not configured; using deterministic fallback agent."
        )

    app.state.container = AppState(
        settings=settings,
        analysis_store=analysis_store,
        upstream_cache=upstream_cache,
        preferences_store=preferences_store,
        agent=fallback_agent,
        agent_app=agent_app,
        tool_registry=tool_registry,
        config={"models": models, "agents": agents, "swarm_config": swarm},
    )

    log.info("--- Initialization complete. Server is ready. ---")

    try:
        yield
    finally:
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
