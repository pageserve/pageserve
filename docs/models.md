# Data Models

All models are [Pydantic v2](https://docs.pydantic.dev/) classes. Import them from the top-level package:

```python
from pageserve import (
    Document, DocumentList, UploadResult,
    StructureNode, Page, QuerySource, QueryResult,
    Section, RetrieveDocResult, RetrieveResult,
    SSEEvent, IndexProgress,
    ApiKey, CreatedApiKey, Stats,
    Webhook, WebhookTestResult, HealthResult,
)
```

> **A note on citations.** The `citation` property currently renders page references with the Vietnamese abbreviation `tr.` (e.g. `"Employment Contract tr.5, 6"`), because the service defaults to Vietnamese-language documents. See [`QueryResult.citation`](#queryresult) below.

---

## Document

Returned by [`list_documents()`](sync-client.md#list_documents) and [`get_document()`](sync-client.md#get_document).

```python
class Document(BaseModel):
    doc_id:      str
    name:        str
    status:      str                  # "pending" | "indexing" | "completed" | "failed"
    page_count:  int | None  = None
    file_size:   int | None  = None   # bytes
    description: str | None  = ""
    tags:        list[str]   = []
    language:    str | None  = "vi"
    error_msg:   str | None  = None
    created_at:  datetime | None = None
```

**Properties**

| Property | Returns | Notes |
| --- | --- | --- |
| `is_ready` | `bool` | `True` when `status == "completed"` |
| `file_size_mb` | `float \| None` | `file_size` in MB, rounded to 2 dp; `None` if size unknown |

## DocumentList

```python
class DocumentList(BaseModel):
    total:     int
    documents: list[Document]
```

## UploadResult

Returned by [`upload()`](sync-client.md#upload), [`reindex()`](sync-client.md#reindex), and the `wait=True` polling path.

```python
class UploadResult(BaseModel):
    doc_id:         str
    name:           str
    status:         str           # usually "pending" right after upload
    queue_position: int | None = None
    job_id:         str | None = None
    max_file_mb:    int | None = None
    cached:         bool = False
```

## BulkDeleteResult

Returned by [`bulk_delete()`](sync-client.md#bulk_delete).

```python
class BulkDeleteResult(BaseModel):
    deleted: int
    failed:  list[str] = []   # doc_ids that could not be deleted
```

## BulkReindexResult

Returned by [`bulk_reindex()`](sync-client.md#bulk_reindex).

```python
class BulkReindexResult(BaseModel):
    queued: int
```

## StructureNode

A node in the document's table-of-contents tree. Recursive — `nodes` holds child `StructureNode` objects.

```python
class StructureNode(BaseModel):
    title:        str
    node_id:      str | None = None
    start_index:  int                 # first page in this section (1-indexed)
    end_index:    int                 # last page
    summary:      str | None = None
    has_children: bool = False         # True when the tree was trimmed at this depth
    nodes:        list[StructureNode] = []
```

**Properties**

| Property | Returns | Example |
| --- | --- | --- |
| `page_range` | `str` | `"5"` (single page) or `"5–12"` (range, en-dash) |

## Page

One page's raw text. Returned by [`get_pages()`](sync-client.md#get_pages) and embedded in `QueryResult`.

```python
class Page(BaseModel):
    page:    int
    content: str
```

**Properties**

| Property | Returns | Notes |
| --- | --- | --- |
| `preview` | `str` | First 300 chars of `content`, with a trailing `...` if truncated |

## QuerySource

One document's contribution to a multi-document query result.

```python
class QuerySource(BaseModel):
    doc_id:          str
    doc_name:        str | None = ""
    doc_description: str | None = None   # auto-generated document summary
    page_refs:       list[int]  = []     # 1-based page numbers
    raw_pages:       list[Page] = []
```

**Properties**

| Property | Returns | Notes |
| --- | --- | --- |
| `citation` | `str` | `"{doc_name} tr.{page_refs}"`, e.g. `"Labor Law 2024 tr.22, 24"`; falls back to `doc_name` / `doc_id` when there are no page refs |

## QueryResult

Returned by [`query()`](sync-client.md#query), [`query_docs()`](sync-client.md#query_docs), and [`query_many()`](sync-client.md#query_many).

```python
class QueryResult(BaseModel):
    doc_id:     str | None = None     # single-doc queries
    doc_name:   str | None = None
    question:   str | None = None
    answer:     str
    page_refs:  list[int]  = []       # single-doc queries
    raw_pages:  list[Page] = []       # single-doc queries
    sources:    list[QuerySource] = []  # multi-doc queries
    elapsed_ms: int | None = None
    cached:     bool = False
```

**Properties**

| Property | Returns | Notes |
| --- | --- | --- |
| `citation` | `str` | Single-doc: `"{doc_name} tr.5, 6"`. Multi-doc: each source joined with ` \| ` |
| `sources_text` | `str` | Alias of `citation` |

> For multi-document results, the top-level `page_refs` / `raw_pages` are empty — read per-document data from `sources` instead.

## Section

One relevant section returned by [`retrieve()`](sync-client.md#retrieve).

```python
class Section(BaseModel):
    title:      str
    node_id:    str | None = None
    page_start: int | None = None
    page_end:   int | None = None
    summary:    str | None = None         # node summary (when include_summary=True)
    pages:      list[Page] | None = None  # None when retrieve(include_content=False)
```

**Properties**

| Property | Returns | Notes |
| --- | --- | --- |
| `page_range` | `str` | `"5"` for a single page, `"5–6"` for a range |
| `text` | `str` | The content of all `pages` joined with blank lines (empty string when `pages` is `None`) |

> `pages` is `None` when you call `retrieve(..., include_content=False)` — the
> server returns section metadata + `summary` only. Use `get_pages()` to fetch the
> page text on demand.

## RetrieveDocResult

Per-document grouping of sections inside a `RetrieveResult`.

```python
class RetrieveDocResult(BaseModel):
    doc_id:          str
    doc_name:        str | None = None
    doc_description: str | None = None   # auto-generated document summary
    sections:        list[Section] = []
```

## RetrieveResult

Returned by [`retrieve()`](sync-client.md#retrieve). Unlike `QueryResult`, it contains **no synthesized answer** — only the raw content of the matching sections.

```python
class RetrieveResult(BaseModel):
    doc_ids:    list[str] = []
    question:   str | None = None
    results:    list[RetrieveDocResult] = []
    elapsed_ms: int | None = None
    cached:     bool = False
```

**Properties**

| Property | Returns | Notes |
| --- | --- | --- |
| `sections` | `list[Section]` | All sections flattened across every document in `results` |
| `text` | `str` | Every section's text joined — ready to drop into a prompt |

## SSEEvent

Yielded by [`query_stream()`](streaming.md). A single model covers every event type; only the fields relevant to each `type` are populated.

```python
class SSEEvent(BaseModel):
    type:     str                 # "tool_start" | "tool_done" | "token" | "sources" | "done" | "error"

    # tool_start
    id:       str | None  = None
    name:     str | None  = None
    args:     dict | None = None

    # tool_done
    summary:  str | None   = None
    elapsed:  float | None = None
    error:    bool | None  = False

    # token
    content:  str | None = None

    # sources
    sources:  list[QuerySource] | None = None

    # progress (document indexing)
    status:   str | None = None
    progress: int | None = None

    # error / done
    message:  str | None  = None
    cached:   bool | None = None
```

## IndexProgress

Yielded by [`watch_progress()`](streaming.md#indexing-progress) during indexing.

```python
class IndexProgress(BaseModel):
    status:   str           # "pending" | "indexing" | "completed" | "failed"
    progress: int = 0       # 0–100
    error:    str | None = None
```

## ApiKey

Returned by [`list_keys()`](sync-client.md#api-keys). Secret values are never included.

```python
class ApiKey(BaseModel):
    id:            str
    name:          str
    public_key:    str
    secret_prefix: str
    key_type:      str            # "live" | "test"
    scopes:        list[str]
    is_active:     bool
    request_count: int = 0
    last_used_at:  datetime | None = None
    expires_at:    datetime | None = None
    created_at:    datetime | None = None
```

## CreatedApiKey

Returned by [`create_key()`](authentication.md#create-a-key). Subclass of `ApiKey` that additionally carries the raw `secret_key` — **shown only once.**

```python
class CreatedApiKey(ApiKey):
    secret_key: str   # raw secret — store it immediately, it is never returned again
```

## Stats

Returned by [`get_stats()`](sync-client.md#stats).

```python
class Stats(BaseModel):
    queries_total:       int
    queries_by_day:      list[DailyCount]
    uploads_by_day:      list[DailyCount]
    top_documents:       list[TopDocument]
    avg_latency_ms:      int
    cache_hit_rate:      float          # 0.0–1.0
    documents_by_status: dict[str, int]
```

### DailyCount

```python
class DailyCount(BaseModel):
    date:  str   # "2026-06-01"
    count: int
```

### TopDocument

```python
class TopDocument(BaseModel):
    doc_id:      str
    doc_name:    str
    query_count: int
```

## Webhook

Returned by [`list_webhooks()`](sync-client.md#webhooks) and `create_webhook()`.

```python
class Webhook(BaseModel):
    id:         str
    url:        str
    events:     list[str]   # e.g. ["document.completed", "document.failed"]
    is_active:  bool
    created_at: datetime | None = None
```

## WebhookTestResult

Returned by [`test_webhook()`](sync-client.md#webhooks).

```python
class WebhookTestResult(BaseModel):
    delivered:   bool
    status_code: int
    response:    str | None = None
```

## HealthResult

Returned by [`health()`](sync-client.md#health).

```python
class HealthResult(BaseModel):
    status:  str                          # "ok" | "degraded"
    version: str | None = None
    checks:  dict[str, ServiceCheck] = {}  # keyed by component name
    queue:   QueueInfo  | None = None
    system:  SystemInfo | None = None
```

**Properties**

| Property | Returns | Notes |
| --- | --- | --- |
| `is_healthy` | `bool` | `True` when `status == "ok"` |

### ServiceCheck

One component's health (e.g. `"database"`, `"storage"`, `"llm"`).

```python
class ServiceCheck(BaseModel):
    status:     str            # "ok" | "degraded" | "error"
    latency_ms: int | None = None
    free_gb:    float | None = None
    error:      str | None = None
```

### QueueInfo

```python
class QueueInfo(BaseModel):
    pending:  int            # documents waiting to be indexed
    indexing: int | None = None
    workers:  int | None = None
```

### SystemInfo

```python
class SystemInfo(BaseModel):
    ram_total_gb:     float
    ram_available_gb: float
    ram_used_pct:     float
    max_file_mb:      int | None = None   # upload size limit enforced by the server
```

---

**See also:** [Sync Client Reference](sync-client.md) · [Error Handling](error-handling.md) · [Back to docs index](../README.md#documentation)
