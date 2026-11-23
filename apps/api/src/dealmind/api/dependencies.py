from fastapi import Request


def is_application_ready(request: Request) -> bool:
    return bool(request.app.state.is_ready)
