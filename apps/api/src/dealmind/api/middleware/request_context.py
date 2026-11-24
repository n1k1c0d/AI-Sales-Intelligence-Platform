import logging
from time import perf_counter

from starlette.datastructures import Headers, MutableHeaders
from starlette.routing import Route
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from dealmind.core.context import request_id, resolve_request_id


def _route_template(scope: Scope) -> str:
    # Included FastAPI routers keep their prefix on the effective route.
    effective = scope.get("fastapi", {}).get("effective_route_context")
    template = getattr(effective or scope.get("route"), "path_format", None)
    if isinstance(template, str):
        return template
    endpoint = scope.get("endpoint")
    if endpoint is not None:
        for route in scope["app"].routes:
            if isinstance(route, Route) and route.endpoint is endpoint:
                return route.path_format
    return "<unmatched>"


class RequestContextMiddleware:
    def __init__(self, app: ASGIApp, logger: logging.Logger) -> None:
        self.app = app
        self.logger = logger

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        supplied = Headers(scope=scope).getlist("x-request-id")
        identifier = resolve_request_id(supplied[0] if len(supplied) == 1 else None)
        started = perf_counter()
        status_code = 500
        complete = False

        async def send_response(message: Message) -> None:
            nonlocal status_code, complete
            if message["type"] == "http.response.start":
                MutableHeaders(scope=message)["X-Request-ID"] = identifier
                status_code = message["status"]
            await send(message)
            if message["type"] == "http.response.body" and not message.get("more_body", False):
                complete = True

        token = request_id.set(identifier)
        try:
            await self.app(scope, receive, send_response)
        except Exception as exc:
            self.logger.error(
                "HTTP request failed",
                extra={
                    "event": "http.request.failed",
                    "http_route": _route_template(scope),
                    "status_code": status_code,
                    "exception_type": type(exc).__name__,
                },
            )
            # Starlette re-raises after sending its configured 500 response.
            # An unfinished stream must still signal failure to the ASGI server.
            if not complete:
                raise RuntimeError("HTTP response interrupted") from None
        finally:
            try:
                if complete:
                    self.logger.info(
                        "HTTP request completed",
                        extra={
                            "event": "http.request.completed",
                            "http_method": scope["method"],
                            "http_route": _route_template(scope),
                            "status_code": status_code,
                            "duration_ms": round((perf_counter() - started) * 1000, 3),
                        },
                    )
            finally:
                request_id.reset(token)
