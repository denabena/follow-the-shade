import logging
from typing import Any

from langchain.agents import create_agent

from app.api.chat.schemas import StructuredChatAnswer
from app.builders.model_factory import ModelFactory
from app.builders.tool_registry import ToolRegistry

log = logging.getLogger(__name__)


class AgentFactory:
    """Create LangChain agents from YAML configuration."""

    def __init__(
        self,
        agents_config: list[dict[str, Any]],
        model_factory: ModelFactory,
        tool_registry: ToolRegistry,
        tools_config: list[dict[str, Any]],
    ) -> None:
        self.agents_config = agents_config
        self.model_factory = model_factory
        self.tool_registry = tool_registry
        self._tools_config_map = {
            tool["name"]: tool for tool in tools_config if "name" in tool
        }

    def create_agent(
        self,
        agent_config: dict[str, Any],
        extra_tools: list[Any] | None = None,
    ) -> Any:
        agent_name = agent_config["name"]
        model_name = agent_config.get("model")
        if not model_name:
            raise ValueError(f"Agent '{agent_name}' is not assigned a model.")

        model_instance = self.model_factory.get_model(model_name)
        domain_tools = []
        for tool_name in agent_config.get("domain_tools", []):
            tool = self.tool_registry.get_tool(tool_name)
            if tool:
                domain_tools.append(tool)
            else:
                log.warning(
                    "Domain tool '%s' for agent '%s' not found.",
                    tool_name,
                    agent_name,
                )

        all_tools = domain_tools + (extra_tools or [])
        log.info(
            "Creating agent '%s' with model '%s', tools: %s",
            agent_name,
            model_name,
            [tool.name for tool in all_tools],
        )

        create_kwargs = {
            "model": model_instance,
            "tools": all_tools,
            "system_prompt": agent_config.get("prompt", ""),
            "name": agent_name,
        }
        if agent_config.get("structured_response"):
            create_kwargs["response_format"] = StructuredChatAnswer

        return create_agent(**create_kwargs)
