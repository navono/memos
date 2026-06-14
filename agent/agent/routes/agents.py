from fastapi import APIRouter, HTTPException, Request

from agent.schemas import AgentInfo

agents_router = APIRouter()


@agents_router.get("/agents", response_model=list[AgentInfo])
async def list_agents(request: Request):
    registry = request.app.state.agent_registry
    return [
        AgentInfo(id=a.id, name=a.name, description=a.description, icon=a.icon)
        for a in registry.list_agents()
    ]


@agents_router.get("/agents/{agent_id}", response_model=AgentInfo)
async def get_agent(agent_id: str, request: Request):
    registry = request.app.state.agent_registry
    agent = registry.get(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent not found: {agent_id}")
    return AgentInfo(id=agent.id, name=agent.name, description=agent.description, icon=agent.icon)
