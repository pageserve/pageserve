import pytest

from pageserve._exceptions import (
    AuthError,
    NotFoundError,
    RateLimitError,
    ServiceError,
    raise_for_response,
)


def test_raise_401():
    with pytest.raises(AuthError):
        raise_for_response(401, {"detail": "Invalid key"})


def test_raise_403():
    with pytest.raises(AuthError):
        raise_for_response(403, {"detail": "Forbidden"})


def test_raise_404():
    with pytest.raises(NotFoundError):
        raise_for_response(404, {"detail": "Not found"})


def test_raise_429_with_retry_after():
    with pytest.raises(RateLimitError) as exc_info:
        raise_for_response(429, {"detail": "Rate limit"}, {"retry-after": "30"})
    assert exc_info.value.retry_after == 30


def test_raise_503():
    from pageserve._exceptions import ServiceUnavailableError

    with pytest.raises(ServiceUnavailableError):
        raise_for_response(503, {"detail": "Overloaded"})


def test_raise_500():
    with pytest.raises(ServiceError) as exc_info:
        raise_for_response(500, {"detail": "Internal error"})
    assert exc_info.value.status_code == 500
