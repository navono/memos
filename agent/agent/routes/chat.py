import json

from fastapi import APIRouter, HTTPException, Request
from sse_starlette.sse import EventSourceResponse

from agent.core.prompt import load_system_prompt
from agent.observability.logger import log

chat_router = APIRouter()


@chat_router.post("/chat")
async def chat(request: Request):
    user_id = request.state.user_id
    auth_token = request.state.auth_token

    body = await request.json()
    message = body.get("message")
    if not message:
        raise HTTPException(status_code=400, detail="Missing 'message' field")

    conversation_id = body.get("conversation_id")
    agent = request.app.state.agent
    db = request.app.state.db

    if not conversation_id:
        conversation_id = await db.create_conversation(user_id)

    conv = await db.get_conversation(conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    if conv["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Forbidden")

    log.info("chat request", extra={"extra_data": {
        "user_id": user_id,
        "conversation_id": conversation_id,
        "message_length": len(message),
    }})

    system_prompt = load_system_prompt(user_id)

    config = {
        "configurable": {
            "thread_id": conversation_id,
            "auth_token": auth_token,
            "user_id": user_id,
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
            yield {"data": json.dumps({"done": True, "conversation_id": conversation_id})}
        except Exception as e:
            log.error("chat error", extra={"extra_data": {"error": str(e), "conversation_id": conversation_id}})
            yield {"data": json.dumps({"error": str(e)})}

    return EventSourceResponse(event_generator())


@chat_router.get("/conversations")
async def list_conversations(request: Request):
    user_id = request.state.user_id
    db = request.app.state.db
    cursor = await db._db.execute(
        "SELECT * FROM conversations WHERE user_id = ? ORDER BY updated_at DESC LIMIT 50",
        (user_id,),
    )
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


@chat_router.get("/conversations/{conversation_id}")
async def get_conversation(conversation_id: str, request: Request):
    user_id = request.state.user_id
    db = request.app.state.db
    conv = await db.get_conversation(conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    if conv["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Forbidden")

    agent = request.app.state.agent
    config = {"configurable": {"thread_id": conversation_id}}
    state = await agent.aget_state(config)
    messages = []
    for msg in state.values.get("messages", []):
        entry = {"role": getattr(msg, "type", "unknown"), "content": getattr(msg, "content", "")}
        messages.append(entry)

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

    await db._db.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))
    await db._db.commit()

    # Clean checkpointer state
    agent = request.app.state.agent
    if agent.checkpointer:
        await agent.checkpointer.adelete_thread(conversation_id)

    return {"status": "ok"}
