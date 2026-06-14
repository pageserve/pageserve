from __future__ import annotations

import time
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import httpx

from pageserve._auth import build_headers
from pageserve._exceptions import raise_for_response
from pageserve._models import (
    ApiKey,
    BulkDeleteResult,
    BulkReindexResult,
    CreatedApiKey,
    Document,
    HealthResult,
    IndexProgress,
    Page,
    QueryResult,
    RetrieveResult,
    SSEEvent,
    Stats,
    StructureNode,
    UploadResult,
    Webhook,
    WebhookTestResult,
)
from pageserve._sse import parse_sse_line

_UPLOAD_TIMEOUT = 300.0  # 5 min — large PDFs can be slow to upload
_QUERY_TIMEOUT = 120.0  # 2 min — RAG queries involve multiple LLM calls


def _parse_query_response(data: dict) -> QueryResult:
    """Normalize the two response shapes from POST /v1/query into a single QueryResult.

    Shape 1 — single-doc query (flat):
        {doc_id, doc_name, answer, page_refs, raw_pages}

    Shape 2 — multi-doc query (sources list):
        {answer, sources: [{doc_id, doc_name, page_refs, raw_pages}]}
    """
    from pageserve._models import Page, QuerySource

    if "sources" in data and data["sources"]:
        sources = [QuerySource(**s) for s in data["sources"]]
        all_refs = [p for s in sources for p in s.page_refs]
        all_pages = [p for s in sources for p in s.raw_pages]
        return QueryResult(
            answer=data.get("answer", ""),
            page_refs=sorted(set(all_refs)),
            raw_pages=all_pages,
            sources=sources,
            elapsed_ms=data.get("elapsed_ms"),
            cached=data.get("cached", False),
        )
    else:
        raw_pages = [Page(**p) for p in data.get("raw_pages", [])]
        return QueryResult(
            doc_id=data.get("doc_id"),
            doc_name=data.get("doc_name"),
            question=data.get("question"),
            answer=data.get("answer", ""),
            page_refs=data.get("page_refs", []),
            raw_pages=raw_pages,
            elapsed_ms=data.get("elapsed_ms"),
            cached=data.get("cached", False),
        )


class PageServeClient:
    """Synchronous client for the PageIndex Self-Host Service.

    Args:
        base_url:   Service base URL, e.g. "https://pageindex.company.com"
        public_key: Project public key, e.g. "<your-public-key>"
        secret_key: Project secret key, e.g. "<your-secret-key>"
        timeout:    Default request timeout in seconds.

    Example:
        client = PageServeClient(
            base_url   = "https://pageindex.company.com",
            public_key = "<your-public-key>",
            secret_key = "<your-secret-key>",
        )
        docs   = client.list_documents()
        result = client.query(docs[0].doc_id, "What are the probation terms?")
        print(result.answer)
        print(result.citation)
    """

    def __init__(
        self,
        base_url: str,
        public_key: str,
        secret_key: str,
        timeout: float = 60.0,
    ):
        self._base = base_url.rstrip("/")
        self._public_key = public_key
        self._secret_key = secret_key
        self._timeout = timeout
        self._http = httpx.Client(
            base_url=self._base,
            headers=build_headers(public_key, secret_key),
            timeout=timeout,
        )

    def __enter__(self) -> PageServeClient:
        return self

    def __exit__(self, *args) -> None:
        self.close()

    def close(self) -> None:
        self._http.close()

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _get(self, path: str, **params) -> dict:
        resp = self._http.get(path, params={k: v for k, v in params.items() if v is not None})
        if not resp.is_success:
            try:
                body = resp.json()
            except Exception:
                body = resp.text
            raise_for_response(resp.status_code, body, dict(resp.headers))
        return resp.json()

    def _post(self, path: str, json: dict | None = None, timeout: float | None = None) -> dict:
        resp = self._http.post(path, json=json, timeout=timeout or self._timeout)
        if not resp.is_success:
            try:
                body = resp.json()
            except Exception:
                body = resp.text
            raise_for_response(resp.status_code, body, dict(resp.headers))
        return resp.json() if resp.content else {}

    def _delete(self, path: str) -> None:
        resp = self._http.delete(path)
        if not resp.is_success:
            try:
                body = resp.json()
            except Exception:
                body = resp.text
            raise_for_response(resp.status_code, body, dict(resp.headers))

    # ── Documents ─────────────────────────────────────────────────────────────

    def list_documents(
        self,
        status: str | None = "completed",
        tags: list[str] | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Document]:
        """List documents in the project.

        Args:
            status: Filter by indexing status. Pass None to return all statuses.
            tags:   Filter by tags.
            limit:  Maximum number of results.
            offset: Pagination offset.
        """
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if status:
            params["status"] = status
        if tags:
            params["tags"] = ",".join(tags)
        data = self._get("/v1/documents", **params)
        return [Document(**d) for d in data.get("documents", [])]

    def get_document(self, doc_id: str) -> Document:
        """Fetch metadata for a single document."""
        data = self._get(f"/v1/documents/{doc_id}")
        return Document(**data)

    def upload(
        self,
        file_path: str | Path,
        wait: bool = False,
        poll_interval: float = 3.0,
        max_wait: float = 600.0,
    ) -> UploadResult:
        """Upload a PDF and start indexing.

        Args:
            file_path:     Path to the PDF file.
            wait:          If True, poll until status is 'completed'.
            poll_interval: Polling interval in seconds.
            max_wait:      Maximum time to wait in seconds.

        Returns:
            UploadResult containing the doc_id and initial status.
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        if not path.suffix.lower() == ".pdf":
            raise ValueError("Only PDF files are accepted")

        with open(path, "rb") as f:
            resp = self._http.post(
                "/v1/documents",
                files={"file": (path.name, f, "application/pdf")},
                timeout=_UPLOAD_TIMEOUT,
            )

        if not resp.is_success:
            try:
                body = resp.json()
            except Exception:
                body = resp.text
            if resp.status_code == 413:
                from pageserve._exceptions import FileTooLargeError

                size_mb = path.stat().st_size / (1024 * 1024)
                max_mb = (resp.json() or {}).get("max_file_mb", 0) if resp.content else 0
                raise FileTooLargeError(size_mb, max_mb)
            raise_for_response(resp.status_code, body, dict(resp.headers))

        result = UploadResult(**resp.json())

        if wait and result.status not in ("completed", "failed"):
            return self._poll_until_ready(result.doc_id, poll_interval, max_wait)

        return result

    def _poll_until_ready(
        self,
        doc_id: str,
        interval: float = 3.0,
        max_wait: float = 600.0,
    ) -> UploadResult:
        elapsed = 0.0
        while elapsed < max_wait:
            doc = self.get_document(doc_id)
            if doc.status == "completed":
                return UploadResult(
                    doc_id=doc.doc_id, name=doc.name, status="completed", cached=False
                )
            if doc.status == "failed":
                from pageserve._exceptions import ServiceError

                raise ServiceError(500, f"Indexing failed: {doc.error_msg}")
            time.sleep(interval)
            elapsed += interval

        from pageserve._exceptions import TimeoutError

        raise TimeoutError(f"Document {doc_id} not ready after {max_wait}s")

    def delete_document(self, doc_id: str) -> None:
        """Delete a document and all its indexed data (structure, pages)."""
        self._delete(f"/v1/documents/{doc_id}")

    def bulk_delete(self, doc_ids: list[str]) -> BulkDeleteResult:
        """Delete multiple documents in one request."""
        data = self._post("/v1/documents/bulk-delete", {"doc_ids": doc_ids})
        return BulkDeleteResult(**data)

    def reindex(self, doc_id: str) -> UploadResult:
        """Rebuild the tree index for a document (drops the old index and re-runs)."""
        data = self._post(f"/v1/documents/{doc_id}/reindex")
        return UploadResult(**data)

    def bulk_reindex(self, doc_ids: list[str]) -> BulkReindexResult:
        """Queue multiple documents for reindexing."""
        data = self._post("/v1/documents/bulk-reindex", {"doc_ids": doc_ids})
        return BulkReindexResult(**data)

    # ── Structure ─────────────────────────────────────────────────────────────

    def get_structure(self, doc_id: str, depth: int = 2) -> list[StructureNode]:
        """Fetch the hierarchical structure (table of contents) of a document.

        Args:
            doc_id: Document ID.
            depth:  Tree depth (1-4). Default 2 keeps token count reasonable.
                    Pass 0 for the full tree (careful with large documents).
        """
        data = self._get(f"/v1/documents/{doc_id}/structure", depth=depth)
        return [StructureNode(**n) for n in data]

    def get_subtree(self, doc_id: str, node_id: str) -> list[StructureNode]:
        """Fetch children of a specific structure node (drill-down)."""
        data = self._get(f"/v1/documents/{doc_id}/structure/{node_id}")
        return [StructureNode(**n) for n in data]

    # ── Pages ─────────────────────────────────────────────────────────────────

    def get_pages(self, doc_id: str, pages: str | int) -> list[Page]:
        """Retrieve raw text for specific pages. Instant — no LLM call.

        Args:
            doc_id: Document ID.
            pages:  Page spec: '5', 5, '5-7', or '3,8,12'.
        """
        data = self._get(f"/v1/documents/{doc_id}/pages/{pages}")
        return [Page(**p) for p in data]

    def watch_progress(self, doc_id: str) -> Iterator[IndexProgress]:
        """Stream indexing progress events via SSE.

        Yields IndexProgress until the document reaches 'completed' or 'failed'.

        Example:
            for progress in client.watch_progress(doc_id):
                print(f"{progress.status}: {progress.progress}%")
                if progress.status in ("completed", "failed"):
                    break
        """
        with self._http.stream("GET", f"/v1/documents/{doc_id}/progress") as resp:
            if not resp.is_success:
                raise_for_response(resp.status_code, resp.text)
            for line in resp.iter_lines():
                event = parse_sse_line(line)
                if event:
                    yield IndexProgress(
                        status=event.get("status", ""),
                        progress=event.get("progress", 0),
                        error=event.get("error"),
                    )
                    if event.get("status") in ("completed", "failed"):
                        break

    # ── Query ─────────────────────────────────────────────────────────────────

    def query(self, doc_id: str, question: str) -> QueryResult:
        """Ask a question against a single document using PageIndex RAG.

        The LLM navigates the tree structure, fetches the relevant pages,
        and synthesizes an answer with page-level citations.

        Args:
            doc_id:   Document ID.
            question: Natural-language question.

        Returns:
            QueryResult with answer, page_refs, raw_pages, and citation string.
        """
        data = self._post(
            "/v1/query",
            {"doc_id": doc_id, "question": question},
            timeout=_QUERY_TIMEOUT,
        )
        return _parse_query_response(data)

    def query_docs(self, doc_ids: list[str], question: str) -> QueryResult:
        """Ask a question across multiple documents in a single request.

        The service queries all documents in parallel and synthesizes a
        cross-referenced answer.

        Args:
            doc_ids:  List of document IDs.
            question: Question that may span multiple documents.
        """
        data = self._post(
            "/v1/query",
            {"doc_ids": doc_ids, "question": question},
            timeout=_QUERY_TIMEOUT,
        )
        return _parse_query_response(data)

    def query_many(
        self,
        queries: list[tuple[str, str]],
        max_workers: int = 4,
    ) -> list[QueryResult]:
        """Run multiple (doc_id, question) queries in parallel via ThreadPoolExecutor.

        Results are returned in the same order as the input list.

        Args:
            queries:     List of (doc_id, question) tuples.
            max_workers: Number of concurrent threads.

        Example:
            results = client.query_many([
                ("uuid-contract", "What are the probation terms?"),
                ("uuid-law",      "What does the law say about probation?"),
            ])
        """
        results: list[QueryResult | None] = [None] * len(queries)

        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {
                pool.submit(self.query, doc_id, question): i
                for i, (doc_id, question) in enumerate(queries)
            }
            for future in as_completed(futures):
                idx = futures[future]
                results[idx] = future.result()

        return results  # type: ignore[return-value]

    def retrieve(
        self,
        doc_id_or_ids: str | list[str],
        question: str,
    ) -> RetrieveResult:
        """Retrieve the raw content of the sections relevant to a question.

        Unlike ``query()``, this does NOT synthesize an answer — it returns the
        original page content of the matching sections. It is cheaper (one LLM
        call per document just to navigate the tree) and is ideal when you want
        to feed the source material into your own LLM / prompt.

        Args:
            doc_id_or_ids: A single doc_id, or a list of doc_ids.
            question:      Natural-language question used to locate sections.

        Returns:
            RetrieveResult with one entry per document, each containing the
            relevant sections and their page-level content.
        """
        body: dict[str, Any] = {"question": question}
        if isinstance(doc_id_or_ids, (list, tuple)):
            body["doc_ids"] = list(doc_id_or_ids)
        else:
            body["doc_id"] = doc_id_or_ids
        data = self._post("/v1/retrieve", body, timeout=_QUERY_TIMEOUT)
        return RetrieveResult(**data)

    def query_stream(
        self,
        doc_id: str | None = None,
        question: str = "",
        doc_ids: list[str] | None = None,
    ) -> Iterator[SSEEvent]:
        """Stream a query response as SSE events.

        Event sequence:
            tool_start  — LLM started calling a tool
            tool_done   — tool finished, includes elapsed time
            token       — one chunk of the answer text
            sources     — page refs and raw page content (sent after streaming ends)
            done        — stream is complete
            error       — something went wrong

        Example:
            answer = ""
            for event in client.query_stream(doc_id, "question"):
                if event.type == "token":
                    answer += event.content
                    print(event.content, end="", flush=True)
                elif event.type == "done":
                    break
        """
        body: dict[str, Any] = {"question": question}
        if doc_ids:
            body["doc_ids"] = doc_ids
        elif doc_id:
            body["doc_id"] = doc_id

        with self._http.stream(
            "POST",
            "/v1/query/stream",
            json=body,
            timeout=_QUERY_TIMEOUT,
        ) as resp:
            if not resp.is_success:
                raise_for_response(resp.status_code, resp.text)
            for line in resp.iter_lines():
                event_data = parse_sse_line(line)
                if event_data:
                    yield SSEEvent(**event_data)
                    if event_data.get("type") in ("done", "error"):
                        break

    # ── API Keys ──────────────────────────────────────────────────────────────

    def list_keys(self) -> list[ApiKey]:
        """List all API keys for the project (no secret values returned)."""
        data = self._get("/v1/keys")
        return [ApiKey(**k) for k in data]

    def create_key(
        self,
        name: str,
        key_type: str = "live",
        scopes: list[str] | None = None,
        expires_at: str | None = None,
    ) -> CreatedApiKey:
        """Create a new API key.

        The secret_key in the response is only shown once — save it immediately.

        Args:
            name:       Human-readable label for the key.
            key_type:   "live" or "test".
            scopes:     ["read"] or ["read", "write"]. Defaults to both.
            expires_at: ISO 8601 expiry datetime, or None for no expiry.
        """
        body = {
            "name": name,
            "key_type": key_type,
            "scopes": scopes or ["read", "write"],
            "expires_at": expires_at,
        }
        data = self._post("/v1/keys", body)
        return CreatedApiKey(**data)

    def revoke_key(self, key_id: str) -> None:
        """Revoke an API key immediately."""
        self._delete(f"/v1/keys/{key_id}")

    # ── Stats ─────────────────────────────────────────────────────────────────

    def get_stats(self, period: str = "7d") -> Stats:
        """Fetch usage statistics for the project.

        Args:
            period: Time window — "7d", "30d", or "90d".
        """
        data = self._get("/v1/stats", period=period)
        return Stats(**data)

    # ── Webhooks ──────────────────────────────────────────────────────────────

    def list_webhooks(self) -> list[Webhook]:
        data = self._get("/v1/webhooks")
        return [Webhook(**w) for w in data]

    def create_webhook(
        self,
        url: str,
        events: list[str] | None = None,
        secret: str | None = None,
    ) -> Webhook:
        """Register a webhook endpoint.

        Args:
            url:    URL that will receive webhook POST requests.
            events: Event types to subscribe to. Defaults to document.completed and document.failed.
            secret: HMAC signing secret for request verification.
        """
        data = self._post(
            "/v1/webhooks",
            {
                "url": url,
                "events": events or ["document.completed", "document.failed"],
                "secret": secret,
            },
        )
        return Webhook(**data)

    def delete_webhook(self, webhook_id: str) -> None:
        self._delete(f"/v1/webhooks/{webhook_id}")

    def test_webhook(self, webhook_id: str) -> WebhookTestResult:
        """Send a test event to verify the webhook URL is reachable."""
        data = self._post(f"/v1/webhooks/{webhook_id}/test")
        return WebhookTestResult(**data)

    # ── Health ────────────────────────────────────────────────────────────────

    def health(self) -> HealthResult:
        """Check service health. No auth required."""
        resp = httpx.get(f"{self._base}/health", timeout=10)
        return HealthResult(**resp.json())

    # ── PDF URL ───────────────────────────────────────────────────────────────

    def pdf_url(self, doc_id: str) -> str:
        """Return the URL for downloading or streaming the original PDF."""
        return f"{self._base}/files/{doc_id}.pdf"
