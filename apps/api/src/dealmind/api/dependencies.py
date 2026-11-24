from typing import cast

from fastapi import Request

from dealmind.core.config import Settings


def get_settings(request: Request) -> Settings:
    return cast(Settings, request.app.state.settings)


def is_application_ready(request: Request) -> bool:
    return bool(request.app.state.is_ready)
