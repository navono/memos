from fastapi import APIRouter

from agent.schemas import HealthResponse

config_router = APIRouter()


@config_router.get("/healthz", response_model=HealthResponse)
async def healthz():
    return HealthResponse(status="ok")
