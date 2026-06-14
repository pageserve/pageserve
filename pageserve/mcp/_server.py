from __future__ import annotations

import json
import os

from mcp.server.fastmcp import FastMCP

from pageserve._client import PageServeClient
from pageserve._exceptions import PageServeError


def _create_server(
    base_url: str | None = None,
    public_key: str | None = None,
    secret_key: str | None = None,
    name: str = "pageindex",
    host: str = "127.0.0.1",
    port: int = 3000,
) -> FastMCP:
    """
    Tạo FastMCP server với PageIndex tools.
    Đọc credentials từ args hoặc env vars.

    host/port chỉ dùng cho transport `sse` và `streamable-http`; với `stdio`
    chúng bị bỏ qua. FastMCP yêu cầu host/port được set lúc khởi tạo
    (run() KHÔNG nhận tham số port).
    """
    _url = base_url or os.environ.get("PAGESERVE_URL", "")
    _pub = public_key or os.environ.get("PAGESERVE_PUBLIC_KEY", "")
    _sec = secret_key or os.environ.get("PAGESERVE_SECRET_KEY", "")

    if not _url:
        raise ValueError("base_url hoặc PAGESERVE_URL env var là bắt buộc")
    if not _pub:
        raise ValueError("public_key hoặc PAGESERVE_PUBLIC_KEY env var là bắt buộc")
    if not _sec:
        raise ValueError("secret_key hoặc PAGESERVE_SECRET_KEY env var là bắt buộc")

    # Singleton client — dùng chung cho tất cả tool calls
    client = PageServeClient(
        base_url=_url,
        public_key=_pub,
        secret_key=_sec,
        timeout=120.0,
    )

    mcp = FastMCP(
        name=name,
        host=host,
        port=port,
        instructions=(
            "PageIndex RAG service — truy xuất thông tin từ tài liệu nội bộ.\n\n"
            "Workflow:\n"
            "1. list_documents → xem tài liệu có sẵn, lấy doc_id\n"
            "2. query_document → hỏi đáp 1 doc → answer + page refs\n"
            "3. query_multiple_documents → cross-reference nhiều docs\n"
            "4. retrieve_document → lấy nội dung gốc các section liên quan "
            "(không synthesize answer, rẻ hơn query)\n"
            "5. get_page_content → raw text trang cụ thể (instant, không LLM)\n"
            "6. get_document_structure → mục lục phân cấp\n\n"
            "Citation format trong answer: [[doc_id:page_number]]"
        ),
    )

    @mcp.tool()
    def list_documents() -> str:
        """
        List tất cả documents có sẵn trong project.
        Gọi đầu tiên để xem có những tài liệu nào và lấy doc_id.

        Returns:
            JSON array: [{doc_id, name, page_count, description, tags}]
        """
        try:
            docs = client.list_documents()
            return json.dumps(
                [
                    {
                        "doc_id": d.doc_id,
                        "name": d.name,
                        "page_count": d.page_count,
                        "description": (d.description or "")[:200],
                        "tags": d.tags,
                    }
                    for d in docs
                ],
                ensure_ascii=False,
                indent=2,
            )
        except PageServeError as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    def query_document(doc_id: str, question: str) -> str:
        """
        Hỏi đáp với MỘT document bằng PageIndex reasoning-based RAG.
        LLM tự navigate tree structure → fetch đúng trang → synthesize answer.

        Với câu hỏi liên quan nhiều tài liệu, gọi tool này nhiều lần
        (mỗi lần 1 doc_id), hoặc dùng query_multiple_documents.

        Args:
            doc_id:   Document ID (lấy từ list_documents)
            question: Câu hỏi cụ thể liên quan đến document này

        Returns:
            JSON: {doc_id, doc_name, answer, page_refs, sources, raw_pages, elapsed_ms, cached}
            - answer:    câu trả lời tổng hợp
            - page_refs: danh sách số trang nguồn
            - sources:   citation string, vd "Luật LĐ 2024 tr.22, 24"
            - raw_pages: [{page, content}] — nội dung thô của trang
        """
        try:
            result = client.query(doc_id, question)
            return json.dumps(
                {
                    "doc_id": result.doc_id,
                    "doc_name": result.doc_name,
                    "answer": result.answer,
                    "page_refs": result.page_refs,
                    "sources": result.citation,
                    "raw_pages": [
                        {"page": p.page, "content": p.content[:500]} for p in result.raw_pages
                    ],
                    "elapsed_ms": result.elapsed_ms,
                    "cached": result.cached,
                },
                ensure_ascii=False,
            )
        except PageServeError as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    def query_multiple_documents(doc_ids: list[str], question: str) -> str:
        """
        Hỏi đáp cross-reference nhiều documents cùng lúc.
        Service tự query song song và tổng hợp kết quả.

        Dùng khi câu hỏi cần thông tin từ nhiều tài liệu để so sánh
        hoặc cross-reference (vd: "hợp đồng có đúng luật không?")

        Args:
            doc_ids:  List doc_id cần query (lấy từ list_documents)
            question: Câu hỏi cross-reference

        Returns:
            JSON: {answer, sources: [{doc_id, doc_name, page_refs, raw_pages}], elapsed_ms}
        """
        try:
            result = client.query_docs(doc_ids, question)
            return json.dumps(
                {
                    "answer": result.answer,
                    "sources": [
                        {
                            "doc_id": s.doc_id,
                            "doc_name": s.doc_name,
                            "page_refs": s.page_refs,
                            "citation": s.citation,
                            "raw_pages": [
                                {"page": p.page, "content": p.content[:500]} for p in s.raw_pages
                            ],
                        }
                        for s in result.sources
                    ],
                    "elapsed_ms": result.elapsed_ms,
                    "cached": result.cached,
                },
                ensure_ascii=False,
            )
        except PageServeError as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    def retrieve_document(doc_id_or_ids: str | list[str], question: str) -> str:
        """
        Lấy NỘI DUNG GỐC của các section liên quan đến câu hỏi — KHÔNG synthesize
        answer. Rẻ hơn query_document (chỉ 1 LLM call/doc để điều hướng tree).

        Dùng khi bạn muốn tự đọc/đưa nội dung thô vào prompt của mình thay vì
        nhận một câu trả lời đã được tổng hợp sẵn.

        Args:
            doc_id_or_ids: Một doc_id (str) hoặc list doc_id
            question:      Câu hỏi dùng để định vị section liên quan

        Returns:
            JSON: {doc_ids, question, elapsed_ms, cached,
                   results: [{doc_id, sections: [{title, node_id,
                              page_start, page_end, pages: [{page, content}]}]}]}
        """
        try:
            result = client.retrieve(doc_id_or_ids, question)
            return json.dumps(
                {
                    "doc_ids": result.doc_ids,
                    "question": result.question,
                    "elapsed_ms": result.elapsed_ms,
                    "cached": result.cached,
                    "results": [
                        {
                            "doc_id": r.doc_id,
                            "doc_name": r.doc_name,
                            "sections": [
                                {
                                    "title": s.title,
                                    "node_id": s.node_id,
                                    "page_start": s.page_start,
                                    "page_end": s.page_end,
                                    "pages": [
                                        {"page": p.page, "content": p.content} for p in s.pages
                                    ],
                                }
                                for s in r.sections
                            ],
                        }
                        for r in result.results
                    ],
                },
                ensure_ascii=False,
            )
        except PageServeError as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    def get_page_content(doc_id: str, pages: str) -> str:
        """
        Lấy raw text content của trang cụ thể — INSTANT, không gọi LLM.
        Dùng khi cần xem nội dung chi tiết của 1 trang sau khi biết số trang
        từ kết quả query_document.

        Args:
            doc_id: Document ID
            pages:  Số trang: '5' (1 trang) | '5-7' (range) | '3,8,12' (nhiều trang)

        Returns:
            JSON array: [{page: int, content: str}]
        """
        try:
            result = client.get_pages(doc_id, pages)
            return json.dumps(
                [{"page": p.page, "content": p.content} for p in result],
                ensure_ascii=False,
            )
        except PageServeError as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    def get_document_structure(doc_id: str, depth: int = 2) -> str:
        """
        Lấy tree structure (mục lục phân cấp) của document.
        Dùng để hiểu cấu trúc và xác định section cần đọc.

        Args:
            doc_id: Document ID
            depth:  Độ sâu tree (1-4, mặc định 2 để tiết kiệm token)
                    depth=1: chỉ chapters
                    depth=2: chapters + sections (recommended)
                    depth=0: full tree (cẩn thận với doc nhiều sections)

        Returns:
            JSON array: [{title, node_id, start_index, end_index, summary, nodes}]
            start_index/end_index là số trang (1-indexed)
        """
        try:
            tree = client.get_structure(doc_id, depth=depth)

            def serialize(nodes):
                return [
                    {
                        "title": n.title,
                        "node_id": n.node_id,
                        "start_index": n.start_index,
                        "end_index": n.end_index,
                        "page_range": n.page_range,
                        "summary": n.summary,
                        "has_children": n.has_children,
                        "nodes": serialize(n.nodes),
                    }
                    for n in nodes
                ]

            return json.dumps(serialize(tree), ensure_ascii=False)
        except PageServeError as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    def get_service_health() -> str:
        """
        Kiểm tra trạng thái service và queue.
        Dùng để debug hoặc check xem service có sẵn sàng không.

        Returns:
            JSON: {status, queue: {pending, workers}, system: {ram_available_gb}}
        """
        try:
            h = client.health()
            return json.dumps(
                {
                    "status": h.status,
                    "healthy": h.is_healthy,
                    "queue": h.queue.model_dump() if h.queue else None,
                    "system": {
                        "ram_available_gb": h.system.ram_available_gb if h.system else None,
                        "max_file_mb": h.system.max_file_mb if h.system else None,
                    },
                },
                ensure_ascii=False,
            )
        except Exception as e:
            return json.dumps({"error": str(e), "status": "unreachable"})

    return mcp
