from contextvars import ContextVar
from uuid import UUID, uuid4

request_id: ContextVar[str | None] = ContextVar("dealmind_request_id", default=None)


def resolve_request_id(value: str | None) -> str:
    if value is not None and len(value) in (32, 36):
        try:
            parsed = UUID(value)
        except ValueError:
            pass
        else:
            if parsed.version == 4 and value.lower() in (parsed.hex, str(parsed)):
                return str(parsed)
    return str(uuid4())
