import yaml
import os
from core.config import settings
from app.analysis_store import InMemoryAnalysisStore
from services.follow_the_shade.cache import TtlCache
from app.builders.model_factory import ModelFactory
from app.builders.tool_registry import ToolRegistry
from app.builders.agent_factory import AgentFactory
from app.builders.graph_factory import GraphFactory
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore

print("Importing classes... Done.")
with open(settings.AGENT_CONFIG_PATH, "r", encoding="utf-8") as f:
    config = yaml.safe_load(f)
print("Config loaded.")

agents = config.get("agents", [])
tools = config.get("tools", [])
deps = {
    "analysis_store": InMemoryAnalysisStore(),
    "settings": settings,
    "seed_path": settings.SPLIT_CAFE_SEED_PATH,
    "upstream_cache": TtlCache(60)
}
print("Deps created.")

registry = ToolRegistry(deps, agents)
print("Registry created.")

model_factory = ModelFactory(config.get("models", []))
factory = AgentFactory(agents_config=agents, model_factory=model_factory, tool_registry=registry, tools_config=tools)
print("Factory created.")

graph_factory = GraphFactory(agents_config=agents, agent_factory=factory, default_agent_name=config["swarm_config"]["default_agent_name"])
app = graph_factory.build(checkpointer=InMemorySaver(), store=InMemoryStore())

print(f"Graph type: {type(app).__name__}")
print(f"Tool: {registry.get_tool('find_split_cafe_sun_shade').name}")
