from pathlib import Path

_SYSTEM_PROMPT_TEMPLATE = Path(__file__).parent / "templates" / "system.md"


def load_system_prompt(user_id: int) -> str:
    template = _SYSTEM_PROMPT_TEMPLATE.read_text(encoding="utf-8")
    return template.replace("{user_id}", str(user_id))
