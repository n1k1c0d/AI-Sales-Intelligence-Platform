from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from importlib.metadata import version

from fastapi import FastAPI

from dealmind.api.exception_handlers import register_exception_handlers
from dealmind.api.router import api_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.is_ready = True
    try:
        yield
    finally:
        app.state.is_ready = False


def create_app() -> FastAPI:
    app = FastAPI(
        title="DealMind API",
        description="System endpoints for the DealMind sales intelligence backend.",
        version=version("dealmind-api"),
        lifespan=lifespan,
    )
    app.state.is_ready = False
    app.include_router(api_router)
    register_exception_handlers(app)
    return app


app = create_app()
