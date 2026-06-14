# Streaming (SSE)

Both `query_stream` and `watch_progress` use Server-Sent Events (SSE) to deliver results incrementally.

## Query streaming

`query_stream` yields events as the model thinks and writes. This lets you show the answer token-by-token instead of waiting for the full response.

### Sync

```python
answer  = ""
sources = []

for event in client.query_stream(doc_id, "What are the probation terms?"):
    if event.type == "tool_start":
        # Model is calling an internal search tool
        print(f"\n[searching: {event.name}]", end="", flush=True)

    elif event.type == "tool_done":
        elapsed = f" {event.elapsed:.1f}s" if event.elapsed else ""
        print(f" done{elapsed}", flush=True)

    elif event.type == "token":
        # One chunk of the answer text
        answer += event.content or ""
        print(event.content or "", end="", flush=True)

    elif event.type == "sources":
        # Sent once at the end, after all tokens
        sources = event.sources or []

    elif event.type == "done":
        break

    elif event.type == "error":
        raise RuntimeError(event.message)

print("\n\nSources:")
for src in sources:
    print(f"  {src.citation}")
```

### Async

```python
async for event in client.query_stream(doc_id, "question"):
    if event.type == "token":
        print(event.content or "", end="", flush=True)
    elif event.type == "done":
        break
```

### Multi-doc streaming

```python
for event in client.query_stream(
    doc_ids  = ["uuid-contract", "uuid-law"],
    question = "Does the contract comply with labor law?",
):
    ...
```

## Event types

| `event.type` | Payload fields | Description |
|---|---|---|
| `tool_start` | `id`, `name`, `args` | Model started an internal search tool |
| `tool_done` | `id`, `name`, `summary`, `elapsed`, `error` | Tool finished |
| `token` | `content` | One chunk of the answer text (1–5 chars typically) |
| `sources` | `sources: list[QuerySource]` | Page refs + raw pages, sent after streaming ends |
| `done` | — | Stream is complete |
| `error` | `message` | Something went wrong |

## Indexing progress

`watch_progress` streams indexing status while a document is being processed.

```python
# Sync
result = client.upload("./report.pdf")
for progress in client.watch_progress(result.doc_id):
    bar_len = 30
    filled  = int(bar_len * progress.progress / 100)
    bar     = "█" * filled + "░" * (bar_len - filled)
    print(f"\r[{bar}] {progress.progress}%", end="", flush=True)
    if progress.status in ("completed", "failed"):
        print()
        break

# Async
result = await client.upload("./report.pdf")
async for progress in client.watch_progress(result.doc_id):
    print(f"{progress.status}: {progress.progress}%")
    if progress.status in ("completed", "failed"):
        break
```

### Progress event fields

```python
progress.status    # "pending" | "indexing" | "completed" | "failed"
progress.progress  # 0–100
progress.error     # error message if status == "failed", else None
```

## Forwarding SSE in FastAPI

```python
from fastapi.responses import StreamingResponse

@app.post("/stream")
async def stream_endpoint(doc_id: str, question: str):
    async def generate():
        async for event in client.query_stream(doc_id, question):
            yield f"data: {event.model_dump_json()}\n\n"
            if event.type in ("done", "error"):
                break

    return StreamingResponse(generate(), media_type="text/event-stream")
```

## SSE parser

The raw line parser is available if you need to handle SSE from a non-pageserve source:

```python
from pageserve._sse import parse_sse_line

line   = 'data: {"type": "token", "content": "Hello"}'
result = parse_sse_line(line)
# {"type": "token", "content": "Hello"}
```

> `parse_sse_line` lives in the internal `pageserve._sse` module — it is not part of the public API and may change between releases.

---

**See also:** [Sync Client Reference](sync-client.md) · [Async Client Reference](async-client.md) · [Data Models](models.md) · [Back to docs index](../README.md#documentation)
