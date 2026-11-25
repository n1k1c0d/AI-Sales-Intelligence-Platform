from uuid import UUID, uuid4

from dealmind.core.context import request_id, resolve_request_id


def test_nested_request_context_resets() -> None:
    assert request_id.get() is None
    token = request_id.set(str(uuid4()))
    try:
        first = request_id.get()
        other = request_id.set(str(uuid4()))
        assert request_id.get() != first
        request_id.reset(other)
        assert request_id.get() == first
    finally:
        request_id.reset(token)
    assert request_id.get() is None


def test_request_id_accepts_only_v4() -> None:
    expected = uuid4()
    assert resolve_request_id(str(expected).upper()) == str(expected)
    assert resolve_request_id(expected.hex) == str(expected)
    for supplied in (None, "", "untrusted", "00000000-0000-1000-8000-000000000000"):
        received = resolve_request_id(supplied)
        assert UUID(received).version == 4 and received != supplied
