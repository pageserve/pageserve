import json
from typing import Any


def parse_sse_line(line: str) -> dict[str, Any] | None:
    """Parse a single SSE line into a dict, or return None for non-data lines.

    Args:
        line: Raw line from the SSE stream (trailing newline is fine).

    Returns:
        Parsed dict for data lines, None for comments and blank lines.
    """
    line = line.strip()

    if not line or line.startswith(":"):
        return None

    if not line.startswith("data:"):
        return None

    payload = line[5:].strip()  # strip the "data: " prefix

    if payload == "[DONE]":
        return {"type": "done"}

    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        return {"type": "raw", "content": payload}


def iter_sse_lines(lines) -> "Iterator[dict]":  # noqa: F821
    """Filter and parse multiple SSE lines from a sync httpx response.

    Example:
        with client.stream("GET", "/v1/documents/{id}/progress") as resp:
            for event in iter_sse_lines(resp.iter_lines()):
                print(event)
    """
    for line in lines:
        event = parse_sse_line(line)
        if event is not None:
            yield event


async def aiter_sse_lines(lines) -> "AsyncIterator[dict]":  # noqa: F821
    """Async version of iter_sse_lines for use with httpx.AsyncClient.

    Example:
        async with client.stream("GET", path) as resp:
            async for event in aiter_sse_lines(resp.aiter_lines()):
                print(event)
    """
    async for line in lines:
        event = parse_sse_line(line)
        if event is not None:
            yield event
