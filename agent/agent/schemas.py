from pydantic import BaseModel


class ChatRequest(BaseModel):
    message: str
    conversation_id: str | None = None
    agent_id: str | None = None


class ChatEvent(BaseModel):
    content: str | None = None
    done: bool = False
    conversation_id: str | None = None
    agent_id: str | None = None


class HealthResponse(BaseModel):
    status: str


class AgentInfo(BaseModel):
    id: str
    name: str
    description: str
    icon: str
