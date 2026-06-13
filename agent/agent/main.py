from contextlib import asynccontextmanager

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from deepagents import HarnessProfile, create_deep_agent, register_harness_profile

from agent.auth import AuthMiddleware
from agent.config import settings
from agent.db.database import AgentDB
from agent.observability.logger import log
from agent.routes.chat import chat_router
from agent.routes.config import config_router
from agent.tools.memos import (
    create_memo,
    create_resource,
    delete_resource,
    get_memo,
    list_resources,
    list_tags,
    search_memos,
    set_memos_client,
    update_resource,
)
from agent.tools.memos_client import MemosClient

load_dotenv()

register_harness_profile("openai", HarnessProfile(
    excluded_tools=frozenset([
        "write_todos", "ls", "read_file", "write_file", "edit_file",
        "glob", "grep", "execute", "task",
    ]),
))


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

    agent = create_deep_agent(
        model=model,
        tools=[search_memos, get_memo, create_memo, list_tags, list_resources, create_resource, update_resource, delete_resource],
        system_prompt=None,
        checkpointer=checkpointer,
    )

    app.state.agent = agent
    app.state.memos_client = memos_client

    log.info("agent service started", extra={"extra_data": {"port": settings.port, "model": settings.llm_model}})

    yield

    await memos_client.close()
    await db.close()
    log.info("agent service stopped")


app = FastAPI(title="Memos Agent", version="0.1.0", lifespan=lifespan)
app.add_middleware(AuthMiddleware)
app.include_router(chat_router, prefix="/v1")
app.include_router(config_router, prefix="/v1")

if __name__ == "__main__":
    uvicorn.run(app, host=settings.host, port=settings.port)
