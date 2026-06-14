from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml
from langchain_core.tools import BaseTool

from agent.observability.logger import log
from agent.tools.memos import (
    create_memo,
    create_resource,
    delete_resource,
    get_memo,
    list_resources,
    list_tags,
    search_memos,
    update_resource,
)

_ALL_TOOLS: dict[str, BaseTool] = {
    "search_memos": search_memos,
    "get_memo": get_memo,
    "create_memo": create_memo,
    "list_tags": list_tags,
    "list_resources": list_resources,
    "create_resource": create_resource,
    "update_resource": update_resource,
    "delete_resource": delete_resource,
}

DEFAULT_AGENT_ID = "general"


@dataclass
class AgentConfig:
    id: str
    name: str
    description: str
    icon: str
    system_prompt: str
    tool_names: list[str] = field(default_factory=list)
    mcp_servers: list[dict] = field(default_factory=list)

    def resolve_tools(self) -> list[BaseTool]:
        tools: list[BaseTool] = []
        for name in self.tool_names:
            tool = _ALL_TOOLS.get(name)
            if tool is None:
                log.warning("unknown tool in agent config", extra={"extra_data": {"agent_id": self.id, "tool": name}})
                continue
            tools.append(tool)
        return tools


class AgentRegistry:
    def __init__(self) -> None:
        self._agents: dict[str, AgentConfig] = {}

    def register(self, config: AgentConfig) -> None:
        self._agents[config.id] = config

    def get(self, agent_id: str) -> AgentConfig | None:
        return self._agents.get(agent_id)

    def list_agents(self) -> list[AgentConfig]:
        return list(self._agents.values())

    @property
    def default_agent_id(self) -> str:
        return DEFAULT_AGENT_ID


def load_agents_from_directory(directory: Path) -> AgentRegistry:
    registry = AgentRegistry()
    for path in sorted(directory.glob("*.yaml")):
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        config = AgentConfig(
            id=data["id"],
            name=data["name"],
            description=data["description"],
            icon=data.get("icon", ""),
            system_prompt=data.get("system_prompt", ""),
            tool_names=data.get("tools", []),
            mcp_servers=data.get("mcp_servers", []),
        )
        registry.register(config)
        log.info("loaded agent config", extra={"extra_data": {"agent_id": config.id, "tools": config.tool_names}})
    return registry
