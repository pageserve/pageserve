# Error Handling

All exceptions live in `pageserve.exceptions` and are also importable directly from `pageserve`.

```python
from pageserve import (
    PageServeError,
    AuthError,
    NotFoundError,
    DocumentNotReadyError,
    FileTooLargeError,
    RateLimitError,
    ServiceError,
    ServiceUnavailableError,
    InsufficientStorageError,
    TimeoutError,
)
```

## Exception hierarchy

```
PageServeError
├── AuthError               # 401 / 403
├── NotFoundError           # 404
├── DocumentNotReadyError   # document still indexing
├── FileTooLargeError       # 413
├── RateLimitError          # 429 — has retry_after
├── ServiceError            # other 5xx — has status_code
├── ServiceUnavailableError # 503
├── InsufficientStorageError# 507
└── TimeoutError            # request timed out
```

## When each exception is raised

| Exception | HTTP status | When |
|---|---|---|
| `AuthError` | 401, 403 | Invalid key, expired key, or key lacks the required scope |
| `NotFoundError` | 404 | Document doesn't exist, page out of range |
| `DocumentNotReadyError` | — | Querying a document whose `status != "completed"` |
| `FileTooLargeError` | 413 | Upload exceeds server's `max_file_mb` limit |
| `RateLimitError` | 429 | Too many requests — check `e.retry_after` |
| `ServiceUnavailableError` | 503 | Server is temporarily overloaded or restarting |
| `InsufficientStorageError` | 507 | Server disk is full |
| `ServiceError` | other 5xx | Any other server-side error — check `e.status_code` |
| `TimeoutError` | — | Request exceeded the client timeout |

## Basic error handling

```python
from pageserve import PageServeClient, PageServeError, AuthError, NotFoundError

client = PageServeClient(
    base_url   = "https://pageindex.company.com",
    public_key = "<your-public-key>",
    secret_key = "<your-secret-key>",
)

try:
    result = client.query("uuid-xxx", "What are the probation terms?")
except AuthError:
    print("Invalid or expired API key")
except NotFoundError:
    print("Document not found")
except PageServeError as e:
    print(f"Something went wrong: {e}")
```

Catch `PageServeError` as a fallback — it's the base class for everything.

## Rate limit with retry

```python
import time
from pageserve import RateLimitError

for attempt in range(3):
    try:
        result = client.query(doc_id, question)
        break
    except RateLimitError as e:
        wait = e.retry_after or 5.0
        print(f"Rate limited — retrying in {wait}s")
        time.sleep(wait)
```

## Waiting for indexing

If you call `query()` on a document that isn't ready yet, you get `DocumentNotReadyError`. The easiest fix is `upload(wait=True)`:

```python
result = client.upload("./report.pdf", wait=True, max_wait=600.0)
# safe to query now
answer = client.query(result.doc_id, "Summary?")
```

Or poll manually:

```python
import time
from pageserve import DocumentNotReadyError

for _ in range(60):
    try:
        result = client.query(doc_id, question)
        break
    except DocumentNotReadyError:
        time.sleep(10)
```

## Streaming errors

In `query_stream`, errors arrive as events rather than exceptions:

```python
for event in client.query_stream(doc_id, question):
    if event.type == "error":
        print(f"Stream error: {event.message}")
        break
    elif event.type == "done":
        break
```

## Async

The same exceptions are raised in the async client — just add `await` and an `async` context:

```python
import asyncio
from pageserve import AsyncPageServeClient, RateLimitError

async def main():
    async with AsyncPageServeClient(...) as client:
        try:
            result = await client.query(doc_id, question)
        except RateLimitError as e:
            await asyncio.sleep(e.retry_after or 5.0)

asyncio.run(main())
```

## Inspecting the raw response

`ServiceError` exposes the HTTP status code when the server returns an unexpected 5xx:

```python
from pageserve import ServiceError

try:
    result = client.query(doc_id, question)
except ServiceError as e:
    print(f"Server error {e.status_code}: {e}")
```

`RateLimitError` exposes the `Retry-After` header:

```python
from pageserve import RateLimitError

try:
    result = client.query(doc_id, question)
except RateLimitError as e:
    print(f"Retry after {e.retry_after} seconds")
```
