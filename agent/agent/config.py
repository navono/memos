import os

from pydantic_settings import BaseSettings, SettingsConfigDict

# Bypass system proxy for outbound HTTP requests (LLM API, Memos API).
os.environ.setdefault("NO_PROXY", "*")
os.environ.setdefault("no_proxy", "*")
os.environ.setdefault("LANGCHAIN_OPENAI_TCP_KEEPALIVE", "0")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AGENT_", env_file=".env")

    # LLM
    llm_api_key: str = ""
    llm_model: str = "gpt-4o"
    llm_base_url: str = ""

    # Memos connection
    memos_addr: str = "http://localhost:5230"
    memos_secret: str = "usememos"

    # Agent behavior
    max_react_iterations: int = 10

    # Server
    host: str = "0.0.0.0"
    port: int = 8082
    data_dir: str = "./agent_data"


settings = Settings()
