from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from importlib.metadata import version

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from starlette.types import ASGIApp

from dealmind.api.exception_handlers import register_exception_handlers
from dealmind.api.middleware.request_context import RequestContextMiddleware
from dealmind.api.router import api_router
from dealmind.core.config import Settings
from dealmind.core.logging import create_app_logger


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.is_ready = True
    try:
        yield
    finally:
        app.state.is_ready = False


class DealMindAPI(FastAPI):
    def build_middleware_stack(self) -> ASGIApp:
        # Wrap Starlette's error handler so even its 500 response gets both sets of headers.
        cors = CORSMiddleware(
            super().build_middleware_stack(),
            allow_origins=self.state.settings.cors_origins,
            allow_methods=["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
            allow_headers=["Content-Type", "Authorization", "X-Request-ID"],
            expose_headers=["X-Request-ID"],
        )
        return RequestContextMiddleware(cors, self.state.logger)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings if settings is not None else Settings()
    app = DealMindAPI(
        title="DealMind API",
        description="System endpoints for the DealMind sales intelligence backend.",
        version=version("dealmind-api"),
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.logger = create_app_logger(settings)
    app.state.is_ready = False
    app.include_router(api_router)
    register_exception_handlers(app)
    return app


app = create_app()
