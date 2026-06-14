from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class Document(BaseModel):
    doc_id: str
    name: str
    status: str  # "pending"|"indexing"|"completed"|"failed"
    page_count: int | None = None
    file_size: int | None = None  # bytes
    description: str | None = ""
    tags: list[str] = Field(default_factory=list)
    language: str | None = "vi"
    error_msg: str | None = None
    created_at: datetime | None = None

    @property
    def is_ready(self) -> bool:
        return self.status == "completed"

    @property
    def file_size_mb(self) -> float | None:
        if self.file_size is None:
            return None
        return round(self.file_size / (1024 * 1024), 2)


class DocumentList(BaseModel):
    total: int
    documents: list[Document]


class UploadResult(BaseModel):
    doc_id: str
    name: str
    status: str  # "pending" ngay sau upload
    queue_position: int | None = None
    job_id: str | None = None
    max_file_mb: int | None = None
    cached: bool = False


class BulkDeleteResult(BaseModel):
    deleted: int
    failed: list[str] = Field(default_factory=list)


class BulkReindexResult(BaseModel):
    queued: int


class StructureNode(BaseModel):
    title: str
    node_id: str | None = None
    start_index: int  # trang bắt đầu (1-indexed)
    end_index: int  # trang kết thúc
    summary: str | None = None
    has_children: bool = False  # True khi tree bị trim
    nodes: list[StructureNode] = Field(default_factory=list)

    @property
    def page_range(self) -> str:
        if self.start_index == self.end_index:
            return str(self.start_index)
        return f"{self.start_index}–{self.end_index}"


StructureNode.model_rebuild()


class Page(BaseModel):
    page: int
    content: str

    @property
    def preview(self) -> str:
        return self.content[:300] + ("..." if len(self.content) > 300 else "")


class QuerySource(BaseModel):
    doc_id: str
    doc_name: str | None = ""
    page_refs: list[int] = Field(default_factory=list)
    raw_pages: list[Page] = Field(default_factory=list)

    @property
    def citation(self) -> str:
        if not self.page_refs:
            return self.doc_name or self.doc_id
        pages = ", ".join(str(p) for p in self.page_refs)
        return f"{self.doc_name or self.doc_id} tr.{pages}"


class QueryResult(BaseModel):
    doc_id: str | None = None
    doc_name: str | None = None
    question: str | None = None
    answer: str
    page_refs: list[int] = Field(default_factory=list)
    raw_pages: list[Page] = Field(default_factory=list)
    sources: list[QuerySource] = Field(default_factory=list)
    elapsed_ms: int | None = None
    cached: bool = False

    @property
    def citation(self) -> str:
        if self.sources:
            return " | ".join(s.citation for s in self.sources if s.page_refs)
        if not self.page_refs:
            return self.doc_name or ""
        pages = ", ".join(str(p) for p in self.page_refs)
        return f"{self.doc_name or ''} tr.{pages}"

    @property
    def sources_text(self) -> str:
        return self.citation


class Section(BaseModel):
    """Một section liên quan trả về từ POST /v1/retrieve."""

    title: str
    node_id: str | None = None
    page_start: int | None = None
    page_end: int | None = None
    pages: list[Page] = Field(default_factory=list)

    @property
    def page_range(self) -> str:
        if self.page_start is None:
            return ""
        if self.page_start == self.page_end or self.page_end is None:
            return str(self.page_start)
        return f"{self.page_start}–{self.page_end}"

    @property
    def text(self) -> str:
        """Nội dung thô của toàn bộ section, nối các trang."""
        return "\n\n".join(p.content for p in self.pages)


class RetrieveDocResult(BaseModel):
    """Kết quả retrieve cho một document."""

    doc_id: str
    doc_name: str | None = None
    sections: list[Section] = Field(default_factory=list)


class RetrieveResult(BaseModel):
    """Phản hồi từ POST /v1/retrieve — nội dung gốc, KHÔNG synthesize answer."""

    doc_ids: list[str] = Field(default_factory=list)
    question: str | None = None
    results: list[RetrieveDocResult] = Field(default_factory=list)
    elapsed_ms: int | None = None
    cached: bool = False

    @property
    def sections(self) -> list[Section]:
        """Phẳng hóa tất cả sections từ mọi document."""
        return [s for r in self.results for s in r.sections]

    @property
    def text(self) -> str:
        """Toàn bộ nội dung retrieve nối lại — tiện làm context cho LLM."""
        return "\n\n".join(s.text for s in self.sections)


class SSEEvent(BaseModel):
    type: str

    # tool_start
    id: str | None = None
    name: str | None = None
    args: dict | None = None

    # tool_done
    summary: str | None = None
    elapsed: float | None = None
    error: bool | None = False

    # token
    content: str | None = None

    # sources
    sources: list[QuerySource] | None = None

    # progress (document indexing)
    status: str | None = None
    progress: int | None = None

    # error
    message: str | None = None

    # done
    cached: bool | None = None


class IndexProgress(BaseModel):
    """SSE event từ /v1/documents/{id}/progress."""

    status: str  # "pending"|"indexing"|"completed"|"failed"
    progress: int = 0  # 0-100
    error: str | None = None


class ApiKey(BaseModel):
    id: str
    name: str
    public_key: str
    secret_prefix: str
    key_type: str  # "live"|"test"
    scopes: list[str]
    is_active: bool
    request_count: int = 0
    last_used_at: datetime | None = None
    expires_at: datetime | None = None
    created_at: datetime | None = None


class CreatedApiKey(ApiKey):
    """Trả về khi tạo key mới — có secret_key (chỉ 1 lần)."""

    secret_key: str  # raw secret, CHỈ có khi vừa tạo


class DailyCount(BaseModel):
    date: str
    count: int


class TopDocument(BaseModel):
    doc_id: str
    doc_name: str
    query_count: int


class Stats(BaseModel):
    queries_total: int
    queries_by_day: list[DailyCount]
    uploads_by_day: list[DailyCount]
    top_documents: list[TopDocument]
    avg_latency_ms: int
    cache_hit_rate: float
    documents_by_status: dict[str, int]


class Webhook(BaseModel):
    id: str
    url: str
    events: list[str]
    is_active: bool
    created_at: datetime | None = None


class WebhookTestResult(BaseModel):
    delivered: bool
    status_code: int
    response: str | None = None


class ServiceCheck(BaseModel):
    status: str  # "ok"|"degraded"|"error"
    latency_ms: int | None = None
    free_gb: float | None = None
    error: str | None = None


class QueueInfo(BaseModel):
    pending: int
    indexing: int | None = None
    workers: int | None = None


class SystemInfo(BaseModel):
    ram_total_gb: float
    ram_available_gb: float
    ram_used_pct: float
    max_file_mb: int | None = None


class HealthResult(BaseModel):
    status: str  # "ok"|"degraded"
    version: str | None = None
    checks: dict[str, ServiceCheck] = Field(default_factory=dict)
    queue: QueueInfo | None = None
    system: SystemInfo | None = None

    @property
    def is_healthy(self) -> bool:
        return self.status == "ok"
