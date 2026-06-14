from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from agent.auth import AuthMiddleware
from agent.config import settings
from agent.db.database import AgentDB
from agent.observability.logger import log
from agent.registry import DEFAULT_AGENT_ID, load_agents_from_directory
from agent.agent_factory import create_all_agents
from agent.routes.agents import agents_router
from agent.routes.chat import chat_router
from agent.routes.config import config_router
from agent.tools.memos import set_memos_client
from agent.tools.memos_client import MemosClient

load_dotenv()


_AGENTS_DIR = Path(__file__).parent / "agents"


@asynccontextmanager
async def lifespan(app: FastAPI):
    db = AgentDB()
    await db.initialize(settings.data_dir)
    app.state.db = db

    memos_client = MemosClient(settings.memos_addr)
    set_memos_client(memos_client)

    model = ChatOpenAI(
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url or None,
        model=settings.llm_model,
    )

    checkpointer = AsyncSqliteSaver(db._db)
    await checkpointer.setup()

    agent_registry = load_agents_from_directory(_AGENTS_DIR)
    agents = create_all_agents(agent_registry.list_agents(), model, checkpointer)

    app.state.agents = agents
    app.state.agent_registry = agent_registry
    app.state.agent = agents.get(DEFAULT_AGENT_ID)
    app.state.memos_client = memos_client

    log.info("agent service started", extra={"extra_data": {
        "port": settings.port,
        "model": settings.llm_model,
        "agents": list(agents.keys()),
    }})

    yield

    await memos_client.close()
    await db.close()
    log.info("agent service stopped")


app = FastAPI(title="Memos Agent", version="0.1.0", lifespan=lifespan)
app.add_middleware(AuthMiddleware)
app.include_router(chat_router, prefix="/v1")
app.include_router(agents_router, prefix="/v1")
app.include_router(config_router, prefix="/v1")

if __name__ == "__main__":
    uvicorn.run(app, host=settings.host, port=settings.port)
