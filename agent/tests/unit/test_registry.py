"""Unit tests for agent registry module."""

import textwrap
from pathlib import Path

import pytest
import yaml

from agent.registry import AgentConfig, AgentRegistry, DEFAULT_AGENT_ID, load_agents_from_directory


class TestAgentConfig:
    """Tests for AgentConfig dataclass."""

    def test_resolve_tools_known_names(self):
        config = AgentConfig(
            id="test",
            name="Test",
            description="test",
            icon="x",
            system_prompt="",
            tool_names=["search_memos", "get_memo", "list_tags"],
        )
        tools = config.resolve_tools()
        assert len(tools) == 3
        names = [t.name for t in tools]
        assert "search_memos" in names
        assert "get_memo" in names
        assert "list_tags" in names

    def test_resolve_tools_unknown_name_skipped(self):
        config = AgentConfig(
            id="test",
            name="Test",
            description="test",
            icon="x",
            system_prompt="",
            tool_names=["search_memos", "nonexistent_tool"],
        )
        tools = config.resolve_tools()
        assert len(tools) == 1
        assert tools[0].name == "search_memos"

    def test_resolve_tools_empty(self):
        config = AgentConfig(
            id="test",
            name="Test",
            description="test",
            icon="x",
            system_prompt="",
            tool_names=[],
        )
        assert config.resolve_tools() == []


class TestAgentRegistry:
    """Tests for AgentRegistry class."""

    def test_register_and_get(self):
        registry = AgentRegistry()
        config = AgentConfig(
            id="sum", name="Summary", description="Summarize", icon="bar-chart",
            system_prompt="summarize", tool_names=["search_memos"],
        )
        registry.register(config)
        assert registry.get("sum") is config

    def test_get_unknown_returns_none(self):
        registry = AgentRegistry()
        assert registry.get("nope") is None

    def test_list_agents(self):
        registry = AgentRegistry()
        for i in range(3):
            registry.register(AgentConfig(
                id=f"a{i}", name=f"Agent {i}", description="d", icon="x",
                system_prompt="", tool_names=[],
            ))
        assert len(registry.list_agents()) == 3

    def test_default_agent_id(self):
        assert AgentRegistry().default_agent_id == DEFAULT_AGENT_ID
        assert DEFAULT_AGENT_ID == "general"


class TestLoadAgentsFromDirectory:
    """Tests for YAML-based agent loading."""

    def test_load_from_yaml(self, tmp_path: Path):
        yaml_data = {
            "id": "test-agent",
            "name": "Test Agent",
            "description": "A test agent",
            "icon": "star",
            "system_prompt": "You are a test agent for user {user_id}.",
            "tools": ["search_memos", "get_memo"],
            "mcp_servers": [],
        }
        (tmp_path / "test.yaml").write_text(yaml.dump(yaml_data), encoding="utf-8")

        registry = load_agents_from_directory(tmp_path)
        config = registry.get("test-agent")
        assert config is not None
        assert config.name == "Test Agent"
        assert config.icon == "star"
        assert config.tool_names == ["search_memos", "get_memo"]
        assert "{user_id}" in config.system_prompt

    def test_load_multiple_yaml(self, tmp_path: Path):
        for name in ["a.yaml", "b.yaml"]:
            (tmp_path / name).write_text(yaml.dump({
                "id": name[0], "name": name, "description": "d", "icon": "",
                "system_prompt": "", "tools": [],
            }), encoding="utf-8")

        registry = load_agents_from_directory(tmp_path)
        assert len(registry.list_agents()) == 2

    def test_empty_directory(self, tmp_path: Path):
        registry = load_agents_from_directory(tmp_path)
        assert len(registry.list_agents()) == 0

    def test_nonexistent_directory(self, tmp_path: Path):
        registry = load_agents_from_directory(tmp_path / "nope")
        assert len(registry.list_agents()) == 0

    def test_missing_optional_fields(self, tmp_path: Path):
        yaml_data = {
            "id": "minimal",
            "name": "Minimal",
            "description": "desc",
        }
        (tmp_path / "minimal.yaml").write_text(yaml.dump(yaml_data), encoding="utf-8")

        registry = load_agents_from_directory(tmp_path)
        config = registry.get("minimal")
        assert config is not None
        assert config.icon == ""
        assert config.tool_names == []
        assert config.mcp_servers == []

    def test_load_actual_agents_dir(self):
        agents_dir = Path(__file__).parent.parent.parent / "agent" / "agents"
        if not agents_dir.exists():
            pytest.skip("agents directory not found")

        registry = load_agents_from_directory(agents_dir)
        assert registry.get("general") is not None
        assert registry.get("summary") is not None
        assert registry.get("recommend") is not None
        assert len(registry.list_agents()) == 3

        # General should have all tools
        general = registry.get("general")
        assert len(general.tool_names) == 8

        # Summary should have fewer tools
        summary = registry.get("summary")
        assert len(summary.tool_names) < len(general.tool_names)
        assert "search_memos" in summary.tool_names
