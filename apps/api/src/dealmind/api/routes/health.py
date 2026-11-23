from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from dealmind.api.dependencies import is_application_ready
from dealmind.schemas.health import HealthResponse, ReadinessResponse

router = APIRouter(tags=["System"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Check liveness",
    description="Reports whether the HTTP process can answer a request.",
)
async def health() -> HealthResponse:
    return HealthResponse(status="ok", service="dealmind-api")


@router.get(
    "/ready",
    response_model=ReadinessResponse,
    summary="Check application readiness",
    description="Checks the FastAPI lifespan state. No external services are queried.",
    responses={503: {"model": ReadinessResponse, "description": "Application is not ready"}},
)
async def readiness(
    response: Response, ready: Annotated[bool, Depends(is_application_ready)]
) -> ReadinessResponse:
    if ready:
        return ReadinessResponse(status="ready", checks={"application": "ok"})
    response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return ReadinessResponse(status="not_ready", checks={"application": "not_ready"})
