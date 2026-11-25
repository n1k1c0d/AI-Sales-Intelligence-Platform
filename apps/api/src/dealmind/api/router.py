from fastapi import APIRouter

from dealmind.api.routes.health import router as health_router
from dealmind.schemas.errors import ErrorResponse

api_router = APIRouter(
    prefix="/api/v1",
    responses={
        422: {"model": ErrorResponse, "description": "Request validation failed"},
        500: {"model": ErrorResponse, "description": "Unexpected server error"},
    },
)
api_router.include_router(health_router)
