# Models Reference

All models are Pydantic v2 classes, importable from `pageserve` or `pageserve._models`.

## Document

```python
class Document(BaseModel):
    doc_id:       str
    name:         str
    status:       str           # "pending" | "indexing" | "completed" | "failed"
    page_count:   int
    description:  str | None
    tags:         list[str]
    size_bytes:   int | None
    created_at:   str
    updated_at:   str
```

### Properties

```python
doc.is_ready       # True when status == "completed"
doc.file_size_mb   # size_bytes / 1_048_576, rounded to 2 dp; None if size unknown
```

## DocumentList

```python
class DocumentList(BaseModel):
    items:   list[Document]
    total:   int
    limit:   int
    offset:  int
```

## UploadResult

Returned by `client.upload()`.

```python
class UploadResult(BaseModel):
    doc_id:  str
    name:    str
    status:  str   # usually "pending" right after upload
```

## BulkDeleteResult

Returned by `client.bulk_delete()`.

```python
class BulkDeleteResult(BaseModel):
    deleted: int
    failed:  int
```

## BulkReindexResult

Returned by `client.bulk_reindex()`.

```python
class BulkReindexResult(BaseModel):
    queued: int
    failed: int
```

## StructureNode

A node in the document's table of contents tree. Recursive — `nodes` contains child `StructureNode` objects.

```python
class StructureNode(BaseModel):
    node_id:     str
    title:       str
    summary:     str | None
    start_index: int       # first page index in this section
    end_index:   int       # last page index
    nodes:       list[StructureNode] = []
```

### Properties

```python
node.page_range    # "5" (single) or "5-12" (range), human-readable
```

`StructureNode` calls `model_rebuild()` after class definition because it self-references.

## Page

Represents one page's content, returned by `get_pages()` and embedded in `QueryResult`.

```python
class Page(BaseModel):
    page:    int
    content: str   # full text of the page
```

### Properties

```python
page.preview   # first 300 chars of content, for quick display
```

## QuerySource

One document's contribution to a multi-doc query result.

```python
class QuerySource(BaseModel):
    doc_id:    str
    doc_name:  str
    page_refs: list[int]   # 1-based page numbers
    raw_pages: list[Page]
```

### Properties

```python
source.citation   # "{doc_name} p.{page_refs joined by ', '}"
                  # e.g. "labor-law-2024.pdf p.22, 24"
```

## QueryResult

Returned by `query()`, `query_docs()`, and `query_many()`.

```python
class QueryResult(BaseModel):
    answer:     str
    page_refs:  list[int]       # for single-doc queries
    raw_pages:  list[Page]      # for single-doc queries
    sources:    list[QuerySource] | None   # for multi-doc queries
    elapsed_ms: int | None
    cached:     bool
```

### Properties

```python
result.citation       # single-doc: "{doc_name} p.5, 6"
                      # multi-doc:  "doc1.pdf p.5, 6 | doc2.pdf p.22, 24"

result.sources_text   # all sources combined into one readable string
```

For multi-doc results, `page_refs` and `raw_pages` are empty — use `sources` instead.

## SSEEvent

Yielded by `query_stream()` and `watch_progress()`.

```python
class SSEEvent(BaseModel):
    type:     str           # "token" | "tool_start" | "tool_done" | "sources" | "done" | "error"
    content:  str | None    # token events
    name:     str | None    # tool_start / tool_done
    id:       str | None    # tool call id
    args:     dict | None   # tool_start: the tool's input arguments
    summary:  str | None    # tool_done: what the tool found
    elapsed:  float | None  # tool_done: seconds the tool took
    error:    str | None    # tool_done: error message if the tool failed
    sources:  list[QuerySource] | None  # sources event
    message:  str | None    # error events
```

## IndexProgress

Yielded by `watch_progress()` during document indexing.

```python
class IndexProgress(BaseModel):
    status:   str           # "pending" | "indexing" | "completed" | "failed"
    progress: int           # 0–100
    error:    str | None    # set when status == "failed"
```

## ApiKey

```python
class ApiKey(BaseModel):
    id:            str
    name:          str
    key_type:      str          # "live" | "test"
    scopes:        list[str]    # ["read", "write"]
    request_count: int
    created_at:    str
    expires_at:    str | None
```

## CreatedApiKey

Returned by `create_key()`. Contains the secret — shown once.

```python
class CreatedApiKey(ApiKey):
    public_key: str
    secret_key: str   # ← store this immediately, it won't be returned again
```

## Stats

Returned by `get_stats()`.

```python
class Stats(BaseModel):
    period:         str
    queries_total:  int
    cache_hit_rate: float          # 0.0–1.0
    daily:          list[DailyCount]
    top_documents:  list[TopDocument]
```

## DailyCount

```python
class DailyCount(BaseModel):
    date:          str   # "2025-06-01"
    query_count:   int
    upload_count:  int
```

## TopDocument

```python
class TopDocument(BaseModel):
    doc_id:      str
    name:        str
    query_count: int
```

## Webhook

```python
class Webhook(BaseModel):
    id:         str
    url:        str
    events:     list[str]  # ["document.completed", "document.failed"]
    created_at: str
```

## WebhookTestResult

```python
class WebhookTestResult(BaseModel):
    success:     bool
    status_code: int | None
    error:       str | None
```

## HealthResult

Returned by `client.health()`.

```python
class HealthResult(BaseModel):
    status:  str           # "ok" | "degraded"
    queue:   QueueInfo | None
    system:  SystemInfo | None
    checks:  list[ServiceCheck]
```

### Properties

```python
health.is_healthy   # True when status == "ok"
```

## QueueInfo

```python
class QueueInfo(BaseModel):
    pending: int   # documents waiting to be indexed
    workers: int   # active indexing workers
```

## SystemInfo

```python
class SystemInfo(BaseModel):
    ram_available_gb: float
    max_file_mb:      int      # upload size limit enforced by server
```

## ServiceCheck

One service component's health status.

```python
class ServiceCheck(BaseModel):
    name:    str   # e.g. "database", "storage", "llm"
    status:  str   # "ok" | "degraded" | "down"
    message: str | None
```
