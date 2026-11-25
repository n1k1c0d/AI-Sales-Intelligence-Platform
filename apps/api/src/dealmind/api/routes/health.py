from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from dealmind.api.dependencies import is_application_ready, is_database_ready
from dealmind.schemas.health import HealthResponse, ReadinessChecks, ReadinessResponse

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
    description="Checks the application lifecycle and a bounded PostgreSQL SELECT 1.",
    responses={
        503: {"model": ReadinessResponse, "description": "Application or database is not ready"}
    },
)
async def readiness(
    response: Response,
    application: Annotated[bool, Depends(is_application_ready)],
    database: Annotated[bool, Depends(is_database_ready)],
) -> ReadinessResponse:
    ready = application and database
    if not ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return ReadinessResponse(
        status="ready" if ready else "not_ready",
        checks=ReadinessChecks(
            application="ok" if application else "not_ready",
            database="ok" if ready else "not_ready",
        ),
    )
