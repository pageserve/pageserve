# Sync Client Reference

`PageServeClient` is the synchronous client. It uses `httpx.Client` internally and is safe to use in scripts, Django views, and any non-async context.

## Constructor

```python
PageServeClient(
    base_url:   str,
    public_key: str,
    secret_key: str,
    timeout:    float = 60.0,   # default request timeout in seconds
)
```

## Documents

### `list_documents()`

```python
docs = client.list_documents(
    status = "completed",   # "pending" | "indexing" | "completed" | "failed" | None (all)
    tags   = ["legal"],     # optional tag filter
    limit  = 100,
    offset = 0,
)
# returns list[Document]
```

### `get_document(doc_id)`

```python
doc = client.get_document("uuid-xxx")
# returns Document

print(doc.status)        # "completed"
print(doc.is_ready)      # True / False
print(doc.file_size_mb)  # e.g. 2.4
```

### `upload(file_path, wait=False)`

```python
# Start upload, return immediately
result = client.upload("./report.pdf")
print(result.doc_id, result.status)   # "pending"

# Upload and wait until indexing completes
result = client.upload("./report.pdf", wait=True, max_wait=600.0)
print(result.status)   # "completed"
```

### `delete_document(doc_id)`

```python
client.delete_document("uuid-xxx")   # deletes document and all indexed data
```

### `bulk_delete(doc_ids)`

```python
result = client.bulk_delete(["uuid-1", "uuid-2"])
print(result.deleted, result.failed)
```

### `reindex(doc_id)` / `bulk_reindex(doc_ids)`

```python
client.reindex("uuid-xxx")                           # single doc
client.bulk_reindex(["uuid-1", "uuid-2", "uuid-3"]) # queue multiple
```

### `watch_progress(doc_id)`

SSE stream of indexing progress events. Yields `IndexProgress` objects.

```python
result = client.upload("./report.pdf")

for progress in client.watch_progress(result.doc_id):
    bar = "█" * (progress.progress // 5)
    print(f"\r[{bar:<20}] {progress.progress}%", end="")
    if progress.status in ("completed", "failed"):
        break
```

## Structure

### `get_structure(doc_id, depth=2)`

Fetch the hierarchical table of contents. Useful for understanding a document before querying.

```python
tree = client.get_structure("uuid-xxx", depth=2)
for node in tree:
    print(f"{node.title} (pages {node.page_range})")
    for child in node.nodes:
        print(f"  {child.title}")
```

### `get_subtree(doc_id, node_id)`

Drill into a specific node to get its children:

```python
children = client.get_subtree("uuid-xxx", node_id="0001")
```

## Pages

### `get_pages(doc_id, pages)`

Retrieve raw text for specific pages. No LLM involved — returns instantly.

```python
pages = client.get_pages("uuid-xxx", "22-24")    # range
pages = client.get_pages("uuid-xxx", "5")         # single page
pages = client.get_pages("uuid-xxx", "3,8,12")    # multiple pages

for p in pages:
    print(f"Page {p.page}: {p.preview}")   # first 300 chars
```

## Query

### `query(doc_id, question)`

Ask a question against a single document. The LLM navigates the tree structure to find the right pages, then synthesizes an answer.

```python
result = client.query("uuid-xxx", "What are the probation terms?")

print(result.answer)
print(result.citation)    # "Contract p.5, 6"
print(result.page_refs)   # [5, 6]
print(result.elapsed_ms)  # 3200
print(result.cached)      # False

for page in result.raw_pages:
    print(f"Page {page.page}: {page.content}")
```

### `query_docs(doc_ids, question)`

Cross-reference multiple documents in a single request. The service queries them in parallel and synthesizes a combined answer.

```python
result = client.query_docs(
    ["uuid-contract", "uuid-labor-law"],
    "Does the contract comply with labor law on probation pay?",
)

print(result.answer)
for source in result.sources:
    print(f"{source.doc_name}: pages {source.page_refs}")
    print(f"  {source.citation}")
```

### `query_many(queries, max_workers=4)`

Run multiple `(doc_id, question)` queries in parallel using a thread pool. Results come back in the same order as the input.

```python
results = client.query_many([
    ("uuid-contract",  "What are the probation terms?"),
    ("uuid-law",       "What does labor law say about probation?"),
    ("uuid-policy",    "What is the company policy on probation?"),
], max_workers=3)

for r in results:
    print(r.answer)
```

### `query_stream(doc_id, question, doc_ids=None)`

Streaming query — yields `SSEEvent` objects as they arrive.

```python
for event in client.query_stream("uuid-xxx", "question"):
    if event.type == "tool_start":
        print(f"[searching: {event.name}]", end="", flush=True)
    elif event.type == "token":
        print(event.content, end="", flush=True)
    elif event.type == "sources":
        for src in event.sources:
            print(f"\nSource: {src.citation}")
    elif event.type == "done":
        break
    elif event.type == "error":
        print(f"\nError: {event.message}")
        break
```

## API Keys

```python
keys    = client.list_keys()
new_key = client.create_key("My App", key_type="live", scopes=["read", "write"])
client.revoke_key(key_id)
```

## Stats

```python
stats = client.get_stats(period="7d")   # "7d" | "30d" | "90d"
print(stats.queries_total)
print(stats.cache_hit_rate)
```

## Webhooks

```python
hooks = client.list_webhooks()
hook  = client.create_webhook(
    url    = "https://app.company.com/webhooks/pageindex",
    events = ["document.completed", "document.failed"],
    secret = "hmac-signing-secret",
)
result = client.test_webhook(hook.id)
client.delete_webhook(hook.id)
```

## Health

```python
h = client.health()
print(h.status)          # "ok" | "degraded"
print(h.is_healthy)      # True / False
print(h.queue.pending)   # documents waiting to be indexed
```

## PDF URL

```python
url = client.pdf_url("uuid-xxx")
# https://pageindex.company.com/files/uuid-xxx.pdf
```
