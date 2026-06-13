# Async Client Reference

`AsyncPageServeClient` mirrors the sync client exactly, with every network method as a coroutine. It uses `httpx.AsyncClient` internally.

Use this in FastAPI endpoints, async scripts, and any `asyncio`-based application.

## Constructor

```python
AsyncPageServeClient(
    base_url:   str,
    public_key: str,
    secret_key: str,
    timeout:    float = 60.0,
)
```

## Recommended usage: async context manager

```python
async with AsyncPageServeClient(
    base_url   = os.environ["PAGESERVE_URL"],
    public_key = os.environ["PAGESERVE_PUBLIC_KEY"],
    secret_key = os.environ["PAGESERVE_SECRET_KEY"],
) as client:
    docs = await client.list_documents()
```

## FastAPI example

```python
from fastapi import FastAPI
from pageserve import AsyncPageServeClient

app    = FastAPI()
client = AsyncPageServeClient(
    base_url   = os.environ["PAGESERVE_URL"],
    public_key = os.environ["PAGESERVE_PUBLIC_KEY"],
    secret_key = os.environ["PAGESERVE_SECRET_KEY"],
)

@app.get("/documents")
async def list_docs():
    return await client.list_documents()

@app.post("/query")
async def query(doc_id: str, question: str):
    result = await client.query(doc_id, question)
    return {"answer": result.answer, "citation": result.citation}

@app.on_event("shutdown")
async def shutdown():
    await client.close()
```

## Concurrent queries with `query_many`

Unlike the sync client (which uses threads), the async version uses `asyncio.gather`:

```python
results = await client.query_many([
    ("uuid-contract",  "What are the probation terms?"),
    ("uuid-law",       "What does labor law say about probation?"),
    ("uuid-policy",    "Company policy on new hires?"),
])

for r in results:
    print(r.answer)
```

## Streaming in FastAPI

Forward SSE events from PageIndex to your API consumers:

```python
from fastapi.responses import StreamingResponse
from pageserve import AsyncPageServeClient

@app.post("/chat/stream")
async def chat_stream(doc_id: str, question: str):
    async def generate():
        async for event in client.query_stream(doc_id, question):
            yield f"data: {event.model_dump_json()}\n\n"
            if event.type in ("done", "error"):
                break

    return StreamingResponse(generate(), media_type="text/event-stream")
```

## Streaming progress

```python
result = await client.upload("./report.pdf")

async for progress in client.watch_progress(result.doc_id):
    print(f"{progress.status}: {progress.progress}%")
    if progress.status in ("completed", "failed"):
        break
```

## Method reference

All methods have the same signature as the sync client with `await` prepended.
See the [Sync Client Reference](sync-client.md) for parameter details.

| Sync | Async |
|---|---|
| `client.list_documents()` | `await client.list_documents()` |
| `client.get_document(id)` | `await client.get_document(id)` |
| `client.upload(path)` | `await client.upload(path)` |
| `client.query(id, q)` | `await client.query(id, q)` |
| `client.query_docs(ids, q)` | `await client.query_docs(ids, q)` |
| `client.query_many(pairs)` | `await client.query_many(pairs)` |
| `for e in client.query_stream(...)` | `async for e in client.query_stream(...)` |
| `for p in client.watch_progress(id)` | `async for p in client.watch_progress(id)` |
| `client.get_structure(id)` | `await client.get_structure(id)` |
| `client.get_pages(id, pages)` | `await client.get_pages(id, pages)` |
| `client.health()` | `await client.health()` |
| `client.pdf_url(id)` | `client.pdf_url(id)` ← sync, no network |
