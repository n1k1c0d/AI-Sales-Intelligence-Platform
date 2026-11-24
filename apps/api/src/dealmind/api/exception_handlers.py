from collections.abc import Mapping

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from starlette.exceptions import HTTPException

from dealmind.db.engine import DatabaseUnavailable
from dealmind.schemas.errors import ErrorDetail, ErrorResponse, ValidationIssue

_HTTP_ERRORS = {
    404: ("NOT_FOUND", "Resource not found"),
    405: ("METHOD_NOT_ALLOWED", "HTTP method is not allowed"),
    422: ("VALIDATION_ERROR", "Request validation failed"),
    500: ("INTERNAL_SERVER_ERROR", "An unexpected error occurred"),
}
_VALIDATION_MESSAGES = {
    "missing": "Field required",
    "int_parsing": "Input should be a valid integer",
    "json_invalid": "Invalid JSON",
    "extra_forbidden": "Unexpected field",
}


def _error_response(
    status_code: int,
    details: list[ValidationIssue] | None = None,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    code, message = _HTTP_ERRORS.get(status_code, ("HTTP_ERROR", "HTTP request failed"))
    body = ErrorResponse(error=ErrorDetail(code=code, message=message, details=details))
    return JSONResponse(body.model_dump(mode="json"), status_code=status_code, headers=headers)


def _public_location(request: Request, location: tuple[str | int, ...]) -> list[str | int]:
    # Nested locations can contain user-supplied keys. Expose only declared parameter names.
    if not location or location[0] not in ("query", "path", "header", "cookie", "body"):
        return []
    source = location[0]
    route = request.scope.get("route")
    if isinstance(route, APIRoute) and len(location) > 1 and source != "body":
        params = (
            *route.dependant.query_params,
            *route.dependant.path_params,
            *route.dependant.header_params,
            *route.dependant.cookie_params,
        )
        if any(field.alias == location[1] for field in params):
            return [source, location[1]]
    return [source]


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(DatabaseUnavailable)
    async def database_unavailable(request: Request, exc: DatabaseUnavailable) -> JSONResponse:
        body = ErrorResponse(
            error=ErrorDetail(code="DATABASE_UNAVAILABLE", message="Database unavailable")
        )
        return JSONResponse(body.model_dump(mode="json"), status_code=503)

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException) -> JSONResponse:
        return _error_response(exc.status_code, headers=exc.headers)

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request: Request, exc: RequestValidationError) -> JSONResponse:
        details = []
        for error in exc.errors():
            kind = error["type"]
            if kind not in _VALIDATION_MESSAGES:
                kind = "invalid_value"
            details.append(
                ValidationIssue(
                    loc=_public_location(request, error["loc"]),
                    message=_VALIDATION_MESSAGES.get(kind, "Invalid value"),
                    type=kind,
                )
            )
        return _error_response(422, details)

    @app.exception_handler(Exception)
    async def unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        return _error_response(500)
