from __future__ import annotations

from pathlib import Path

from agent.registry import AgentConfig

_SYSTEM_PROMPT_TEMPLATE = Path(__file__).parent / "templates" / "system.md"


def load_system_prompt(user_id: int, agent_config: AgentConfig | None = None) -> str:
    if agent_config and agent_config.system_prompt:
        return agent_config.system_prompt.replace("{user_id}", str(user_id))

    template = _SYSTEM_PROMPT_TEMPLATE.read_text(encoding="utf-8")
    return template.replace("{user_id}", str(user_id))
