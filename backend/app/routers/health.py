"""GET /api/health — liveness/configuration probe for the frontend and demos."""

from fastapi import APIRouter

from ..config import APP_NAME, APP_VERSION
from ..schemas import HealthResponse
from ..services.inference import INFERENCE_MODE

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def get_health() -> HealthResponse:
    return HealthResponse(
        service=APP_NAME,
        version=APP_VERSION,
        inference_mode=INFERENCE_MODE,
    )
