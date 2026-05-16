import logging
from typing import Any

from langchain.messages import AIMessage, ToolMessage
from langchain.tools import ToolRuntime, tool
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command
from pydantic import BaseModel

from app.builders.agent_factory import AgentFactory
from app.graph_state import MultiAgentState

log = logging.getLogger(__name__)


def _make_handoff_tool(target_agent_name: str):
    tool_name = f"transfer_to_{target_agent_name}"

    @tool(tool_name)
    def handoff(runtime: ToolRuntime) -> Command:
        """Transfer the conversation to another agent."""
        last_ai_message = next(
            msg
            for msg in reversed(runtime.state["messages"])
            if isinstance(msg, AIMessage)
        )
        transfer_message = ToolMessage(
            content=f"Transferred to {target_agent_name}",
            tool_call_id=runtime.tool_call_id,
        )
        return Command(
            goto=target_agent_name,
            update={
                "active_agent": target_agent_name,
                "messages": [last_ai_message, transfer_message],
            },
            graph=Command.PARENT,
        )

    handoff.description = f"Transfer the conversation to {target_agent_name}."
    return handoff


class GraphFactory:
    """Build a LangGraph multi-agent graph with BINA-style handoff support."""

    def __init__(
        self,
        agents_config: list[dict[str, Any]],
        agent_factory: AgentFactory,
        default_agent_name: str,
    ) -> None:
        self.agents_config = agents_config
        self.agent_factory = agent_factory
        self.default_agent_name = default_agent_name

    def _build_handoff_tools(self, agent_config: dict[str, Any]) -> list[Any]:
        return [
            _make_handoff_tool(target_name)
            for target_name in agent_config.get("handoff_tools", [])
        ]

    def build(self, checkpointer=None, store=None):
        agent_names = [cfg["name"] for cfg in self.agents_config]
        agents = {}
        for cfg in self.agents_config:
            name = cfg["name"]
            agents[name] = self.agent_factory.create_agent(
                cfg,
                extra_tools=self._build_handoff_tools(cfg),
            )
            log.info("Agent '%s' registered in graph.", name)

        def _make_node(agent_name: str):
            async def node_fn(state: MultiAgentState) -> Command:
                result = await agents[agent_name].ainvoke(state)
                structured_response = result.get("structured_response")
                if isinstance(structured_response, BaseModel):
                    result = {
                        **result,
                        "structured_response": structured_response.model_dump(),
                    }
                return result

            node_fn.__name__ = f"call_{agent_name}"
            return node_fn

        default = self.default_agent_name

        def route_initial(state: MultiAgentState) -> str:
            return state.get("active_agent") or default

        def route_after_agent(state: MultiAgentState) -> str:
            messages = state.get("messages", [])
            if messages:
                last_msg = messages[-1]
                if isinstance(last_msg, AIMessage) and not last_msg.tool_calls:
                    return "__end__"
            active = state.get("active_agent", default)
            return active if active in agent_names else default

        builder = StateGraph(MultiAgentState)
        for name in agent_names:
            builder.add_node(name, _make_node(name))

        builder.add_conditional_edges(START, route_initial, agent_names)
        possible_targets = agent_names + [END]
        for name in agent_names:
            builder.add_conditional_edges(name, route_after_agent, possible_targets)

        compile_kwargs = {}
        if checkpointer:
            compile_kwargs["checkpointer"] = checkpointer
        if store:
            compile_kwargs["store"] = store

        graph = builder.compile(**compile_kwargs)
        log.info(
            "Multi-agent graph compiled. Agents: %s | Default: %s",
            agent_names,
            default,
        )
        return graph
