from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from pathlib import Path

import httpx

from pageserve._auth import build_headers
from pageserve._client import _parse_query_response
from pageserve._exceptions import TimeoutError, raise_for_response
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
    SSEEvent,
    Stats,
    StructureNode,
    UploadResult,
    Webhook,
    WebhookTestResult,
)
from pageserve._sse import parse_sse_line

_UPLOAD_TIMEOUT = 300.0
_QUERY_TIMEOUT = 120.0


class AsyncPageServeClient:
    """Async client for the PageIndex Self-Host Service.

    Designed for FastAPI, async scripts, and async agent frameworks.
    Every method that touches the network is a coroutine.

    Example:
        async with AsyncPageServeClient(
            base_url   = "https://pageindex.company.com",
            public_key = "<your-public-key>",
            secret_key = "<your-secret-key>",
        ) as client:
            docs    = await client.list_documents()
            results = await client.query_many([
                (docs[0].doc_id, "question 1"),
                (docs[1].doc_id, "question 2"),
            ])
    """

    def __init__(
        self,
        base_url: str,
        public_key: str,
        secret_key: str,
        timeout: float = 60.0,
    ):
        self._base = base_url.rstrip("/")
        self._timeout = timeout
        self._http = httpx.AsyncClient(
            base_url=self._base,
            headers=build_headers(public_key, secret_key),
            timeout=timeout,
        )

    async def __aenter__(self) -> AsyncPageServeClient:
        return self

    async def __aexit__(self, *args) -> None:
        await self.close()

    async def close(self) -> None:
        await self._http.aclose()

    async def _get(self, path: str, **params) -> dict:
        resp = await self._http.get(path, params={k: v for k, v in params.items() if v is not None})
        if not resp.is_success:
            try:
                body = resp.json()
            except Exception:
                body = resp.text
            raise_for_response(resp.status_code, body, dict(resp.headers))
        return resp.json()

    async def _post(self, path: str, json: dict = None, timeout: float = None) -> dict:
        resp = await self._http.post(path, json=json, timeout=timeout or self._timeout)
        if not resp.is_success:
            try:
                body = resp.json()
            except Exception:
                body = resp.text
            raise_for_response(resp.status_code, body, dict(resp.headers))
        return resp.json() if resp.content else {}

    async def _delete(self, path: str) -> None:
        resp = await self._http.delete(path)
        if not resp.is_success:
            try:
                body = resp.json()
            except Exception:
                body = resp.text
            raise_for_response(resp.status_code, body, dict(resp.headers))

    async def list_documents(
        self,
        status: str | None = "completed",
        tags: list[str] | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Document]:
        params = {"limit": limit, "offset": offset}
        if status:
            params["status"] = status
        if tags:
            params["tags"] = ",".join(tags)
        data = await self._get("/v1/documents", **params)
        return [Document(**d) for d in data.get("documents", [])]

    async def get_document(self, doc_id: str) -> Document:
        data = await self._get(f"/v1/documents/{doc_id}")
        return Document(**data)

    async def upload(
        self,
        file_path: str | Path,
        wait: bool = False,
        poll_interval: float = 3.0,
        max_wait: float = 600.0,
    ) -> UploadResult:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        with open(path, "rb") as f:
            resp = await self._http.post(
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
            return await self._poll_until_ready(result.doc_id, poll_interval, max_wait)

        return result

    async def _poll_until_ready(
        self,
        doc_id: str,
        interval: float = 3.0,
        max_wait: float = 600.0,
    ) -> UploadResult:
        elapsed = 0.0
        while elapsed < max_wait:
            doc = await self.get_document(doc_id)
            if doc.status == "completed":
                return UploadResult(doc_id=doc.doc_id, name=doc.name, status="completed")
            if doc.status == "failed":
                from pageserve._exceptions import ServiceError

                raise ServiceError(500, f"Indexing failed: {doc.error_msg}")
            await asyncio.sleep(interval)
            elapsed += interval
        raise TimeoutError(f"Document {doc_id} not ready after {max_wait}s")

    async def delete_document(self, doc_id: str) -> None:
        await self._delete(f"/v1/documents/{doc_id}")

    async def bulk_delete(self, doc_ids: list[str]) -> BulkDeleteResult:
        data = await self._post("/v1/documents/bulk-delete", {"doc_ids": doc_ids})
        return BulkDeleteResult(**data)

    async def reindex(self, doc_id: str) -> UploadResult:
        data = await self._post(f"/v1/documents/{doc_id}/reindex")
        return UploadResult(**data)

    async def bulk_reindex(self, doc_ids: list[str]) -> BulkReindexResult:
        data = await self._post("/v1/documents/bulk-reindex", {"doc_ids": doc_ids})
        return BulkReindexResult(**data)

    async def get_structure(self, doc_id: str, depth: int = 2) -> list[StructureNode]:
        data = await self._get(f"/v1/documents/{doc_id}/structure", depth=depth)
        return [StructureNode(**n) for n in data]

    async def get_subtree(self, doc_id: str, node_id: str) -> list[StructureNode]:
        data = await self._get(f"/v1/documents/{doc_id}/structure/{node_id}")
        return [StructureNode(**n) for n in data]

    async def get_pages(self, doc_id: str, pages: str | int) -> list[Page]:
        """Retrieve raw page text. Instant — no LLM call."""
        data = await self._get(f"/v1/documents/{doc_id}/pages/{pages}")
        return [Page(**p) for p in data]

    async def watch_progress(self, doc_id: str) -> AsyncIterator[IndexProgress]:
        async with self._http.stream("GET", f"/v1/documents/{doc_id}/progress") as resp:
            if not resp.is_success:
                raise_for_response(resp.status_code, resp.text)
            async for line in resp.aiter_lines():
                event = parse_sse_line(line)
                if event:
                    progress = IndexProgress(
                        status=event.get("status", ""),
                        progress=event.get("progress", 0),
                        error=event.get("error"),
                    )
                    yield progress
                    if event.get("status") in ("completed", "failed"):
                        break

    async def query(self, doc_id: str, question: str) -> QueryResult:
        data = await self._post(
            "/v1/query",
            {"doc_id": doc_id, "question": question},
            timeout=_QUERY_TIMEOUT,
        )
        return _parse_query_response(data)

    async def query_docs(self, doc_ids: list[str], question: str) -> QueryResult:
        data = await self._post(
            "/v1/query",
            {"doc_ids": doc_ids, "question": question},
            timeout=_QUERY_TIMEOUT,
        )
        return _parse_query_response(data)

    async def query_many(self, queries: list[tuple[str, str]]) -> list[QueryResult]:
        tasks = [self.query(doc_id, question) for doc_id, question in queries]
        return list(await asyncio.gather(*tasks))

    async def query_stream(
        self,
        doc_id: str | None = None,
        question: str = "",
        doc_ids: list[str] | None = None,
    ) -> AsyncIterator[SSEEvent]:
        body = {"question": question}
        if doc_ids:
            body["doc_ids"] = doc_ids
        elif doc_id:
            body["doc_id"] = doc_id

        async with self._http.stream(
            "POST",
            "/v1/query/stream",
            json=body,
            timeout=_QUERY_TIMEOUT,
        ) as resp:
            if not resp.is_success:
                raise_for_response(resp.status_code, resp.text)
            async for line in resp.aiter_lines():
                event_data = parse_sse_line(line)
                if event_data:
                    yield SSEEvent(**event_data)
                    if event_data.get("type") in ("done", "error"):
                        break

    async def list_keys(self) -> list[ApiKey]:
        data = await self._get("/v1/keys")
        return [ApiKey(**k) for k in data]

    async def create_key(
        self,
        name: str,
        key_type: str = "live",
        scopes: list[str] = None,
        expires_at: str | None = None,
    ) -> CreatedApiKey:
        data = await self._post(
            "/v1/keys",
            {
                "name": name,
                "key_type": key_type,
                "scopes": scopes or ["read", "write"],
                "expires_at": expires_at,
            },
        )
        return CreatedApiKey(**data)

    async def revoke_key(self, key_id: str) -> None:
        await self._delete(f"/v1/keys/{key_id}")

    async def get_stats(self, period: str = "7d") -> Stats:
        data = await self._get("/v1/stats", period=period)
        return Stats(**data)

    async def list_webhooks(self) -> list[Webhook]:
        data = await self._get("/v1/webhooks")
        return [Webhook(**w) for w in data]

    async def create_webhook(
        self,
        url: str,
        events: list[str] = None,
        secret: str | None = None,
    ) -> Webhook:
        data = await self._post(
            "/v1/webhooks",
            {
                "url": url,
                "events": events or ["document.completed", "document.failed"],
                "secret": secret,
            },
        )
        return Webhook(**data)

    async def delete_webhook(self, webhook_id: str) -> None:
        await self._delete(f"/v1/webhooks/{webhook_id}")

    async def test_webhook(self, webhook_id: str) -> WebhookTestResult:
        data = await self._post(f"/v1/webhooks/{webhook_id}/test")
        return WebhookTestResult(**data)

    async def health(self) -> HealthResult:
        resp = await self._http.get("/health", timeout=10)
        return HealthResult(**resp.json())

    def pdf_url(self, doc_id: str) -> str:
        return f"{self._base}/files/{doc_id}.pdf"
