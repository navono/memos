import json

from fastapi import APIRouter, HTTPException, Request
from sse_starlette.sse import EventSourceResponse

from agent.core.prompt import load_system_prompt
from agent.observability.logger import log
from agent.registry import DEFAULT_AGENT_ID

chat_router = APIRouter()


@chat_router.post("/chat")
async def chat(request: Request):
    user_id = request.state.user_id
    auth_token = request.state.auth_token
    username = getattr(request.state, "username", "")

    body = await request.json()
    message = body.get("message")
    if not message:
        raise HTTPException(status_code=400, detail="Missing 'message' field")

    agent_id = body.get("agent_id") or DEFAULT_AGENT_ID
    conversation_id = body.get("conversation_id")

    agents: dict = request.app.state.agents
    agent_registry = request.app.state.agent_registry
    agent = agents.get(agent_id)
    if agent is None:
        raise HTTPException(status_code=400, detail=f"Unknown agent: {agent_id}")

    db = request.app.state.db

    if not conversation_id:
        conversation_id = await db.create_conversation(user_id, agent_id=agent_id)

    conv = await db.get_conversation(conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    if conv["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Forbidden")

    agent_config = agent_registry.get(agent_id)
    system_prompt = load_system_prompt(user_id, agent_config)

    config = {
        "configurable": {
            "thread_id": f"{agent_id}:{conversation_id}",
            "auth_token": auth_token,
            "user_id": user_id,
            "username": username,
        },
    }

    # Only inject system prompt on first message (no prior state)
    state = await agent.aget_state(config)
    existing_messages = state.values.get("messages", [])
    if existing_messages:
        input_messages = [{"role": "user", "content": message}]
    else:
        input_messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message},
        ]

    async def event_generator():
        try:
            async for msg, metadata in agent.astream(
                {"messages": input_messages},
                config=config,
                stream_mode="messages",
            ):
                if (
                    metadata.get("langgraph_node") == "model"
                    and hasattr(msg, "content")
                    and msg.content
                    and not getattr(msg, "tool_calls", None)
                ):
                    yield {"data": json.dumps({"content": msg.content}, ensure_ascii=False)}
            yield {"data": json.dumps({"done": True, "conversation_id": conversation_id, "agent_id": agent_id})}
        except Exception as e:
            log.error("chat error", extra={"extra_data": {"error": str(e), "conversation_id": conversation_id}})
            yield {"data": json.dumps({"error": str(e)})}

    return EventSourceResponse(event_generator())


@chat_router.get("/conversations")
async def list_conversations(request: Request, agent_id: str | None = None):
    user_id = request.state.user_id
    db = request.app.state.db
    return await db.list_conversations(user_id, agent_id=agent_id)


@chat_router.get("/conversations/{conversation_id}")
async def get_conversation(conversation_id: str, request: Request):
    user_id = request.state.user_id
    db = request.app.state.db
    conv = await db.get_conversation(conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    if conv["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Forbidden")

    agent_id = conv.get("agent_id", DEFAULT_AGENT_ID)
    agents: dict = request.app.state.agents
    agent = agents.get(agent_id)
    if not agent:
        agent = agents.get(DEFAULT_AGENT_ID)

    config = {"configurable": {"thread_id": f"{agent_id}:{conversation_id}"}}
    state = await agent.aget_state(config)
    messages = []
    for msg in state.values.get("messages", []):
        msg_type = getattr(msg, "type", "unknown")
        # Skip tool messages and AI messages that only contain tool calls
        if msg_type == "tool":
            continue
        if msg_type == "ai" and getattr(msg, "tool_calls", None):
            continue
        # Map LangChain types to frontend roles
        role = {"human": "user", "ai": "assistant", "system": "system"}.get(msg_type, msg_type)
        content = getattr(msg, "content", "")
        if content:
            messages.append({"role": role, "content": content})

    return {"conversation": conv, "messages": messages}


@chat_router.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str, request: Request):
    user_id = request.state.user_id
    db = request.app.state.db
    conv = await db.get_conversation(conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    if conv["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Forbidden")

    agent_id = conv.get("agent_id", DEFAULT_AGENT_ID)
    await db.delete_conversation(conversation_id)

    # Clean checkpointer state
    agents: dict = request.app.state.agents
    agent = agents.get(agent_id)
    if agent and agent.checkpointer:
        await agent.checkpointer.adelete_thread(f"{agent_id}:{conversation_id}")

    return {"status": "ok"}
