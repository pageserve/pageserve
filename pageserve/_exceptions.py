class PageServeError(Exception):
    """Base class for all pageserve errors."""


class AuthError(PageServeError):
    """401 invalid/expired key, or 403 insufficient scope."""


class NotFoundError(PageServeError):
    """404 — document or resource doesn't exist in this project."""


class DocumentNotReadyError(PageServeError):
    """Document exists but hasn't finished indexing (status != completed)."""

    def __init__(self, doc_id: str, status: str):
        self.doc_id = doc_id
        self.status = status
        super().__init__(f"Document '{doc_id}' is not ready yet (status: {status})")


class FileTooLargeError(PageServeError):
    """413 — file exceeds the server's size limit."""

    def __init__(self, file_size_mb: float, max_size_mb: int):
        self.file_size_mb = file_size_mb
        self.max_size_mb = max_size_mb
        super().__init__(f"File {file_size_mb:.1f}MB exceeds the {max_size_mb}MB limit")


class ServiceUnavailableError(PageServeError):
    """503 — service is overloaded (RAM full, queue full, etc.)."""


class InsufficientStorageError(PageServeError):
    """507 — not enough disk space on the server."""


class RateLimitError(PageServeError):
    """429 — rate limit exceeded."""

    def __init__(self, retry_after: int = 60):
        self.retry_after = retry_after
        super().__init__(f"Rate limited. Retry after {retry_after}s")


class ServiceError(PageServeError):
    """5xx — unexpected server error."""

    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        super().__init__(f"[{status_code}] {message}")


class TimeoutError(PageServeError):
    """Request timed out — usually happens when querying large documents."""


def raise_for_response(status_code: int, body: dict | str, headers: dict | None = None):
    """Map an HTTP response to the appropriate exception and raise it.

    Args:
        status_code: HTTP status code from the response.
        body:        Parsed JSON body or raw text.
        headers:     Response headers (used to read Retry-After).
    """
    if isinstance(body, dict):
        detail = body.get("detail", str(body))
    else:
        detail = str(body)

    if status_code == 401:
        raise AuthError(detail)
    if status_code == 403:
        raise AuthError(f"Forbidden: {detail}")
    if status_code == 404:
        raise NotFoundError(detail)
    if status_code == 413:
        raise FileTooLargeError(0, 0)  # caller fills in actual sizes
    if status_code == 429:
        retry_after = int((headers or {}).get("retry-after", 60))
        raise RateLimitError(retry_after)
    if status_code == 503:
        raise ServiceUnavailableError(detail)
    if status_code == 507:
        raise InsufficientStorageError(detail)
    if status_code >= 500:
        raise ServiceError(status_code, detail)

    raise PageServeError(f"[{status_code}] {detail}")
