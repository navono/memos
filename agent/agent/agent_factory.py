from __future__ import annotations

from langchain_core.language_models import BaseChatModel
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Checkpointer

from deepagents import HarnessProfile, create_deep_agent, register_harness_profile

from agent.registry import AgentConfig

register_harness_profile("openai", HarnessProfile(
    excluded_tools=frozenset([
        "write_todos", "ls", "read_file", "write_file", "edit_file",
        "glob", "grep", "execute", "task",
    ]),
))


def create_agent_for_config(
    agent_config: AgentConfig,
    model: BaseChatModel,
    checkpointer: Checkpointer,
) -> CompiledStateGraph:
    tools = agent_config.resolve_tools()
    return create_deep_agent(
        model=model,
        tools=tools,
        system_prompt=agent_config.system_prompt,
        checkpointer=checkpointer,
    )


def create_all_agents(
    agent_configs: list[AgentConfig],
    model: BaseChatModel,
    checkpointer: Checkpointer,
) -> dict[str, CompiledStateGraph]:
    agents: dict[str, CompiledStateGraph] = {}
    for config in agent_configs:
        agents[config.id] = create_agent_for_config(config, model, checkpointer)
    return agents
