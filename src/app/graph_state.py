from langchain.agents import AgentState
from typing_extensions import NotRequired


class MultiAgentState(AgentState):
    """State for the multi-agent handoff system."""

    active_agent: NotRequired[str]
