from pageserve._models import (
    Document,
    HealthResult,
    QueryResult,
    QuerySource,
    StructureNode,
)


def test_document_is_ready():
    doc = Document(doc_id="uuid", name="test.pdf", status="completed")
    assert doc.is_ready is True

    doc2 = Document(doc_id="uuid", name="test.pdf", status="indexing")
    assert doc2.is_ready is False


def test_document_file_size_mb():
    doc = Document(doc_id="uuid", name="test.pdf", status="completed", file_size=2097152)
    assert doc.file_size_mb == 2.0

    doc2 = Document(doc_id="uuid", name="test.pdf", status="completed")
    assert doc2.file_size_mb is None


def test_query_result_citation_single():
    result = QueryResult(
        doc_id="uuid-1",
        doc_name="Luật Lao động 2024",
        answer="Lương thử việc tối thiểu 85%",
        page_refs=[22, 24],
    )
    assert result.citation == "Luật Lao động 2024 tr.22, 24"


def test_query_result_citation_from_sources():
    sources = [
        QuerySource(doc_id="uuid-1", doc_name="Hợp đồng", page_refs=[5, 6]),
        QuerySource(doc_id="uuid-2", doc_name="Luật LĐ", page_refs=[22, 24]),
    ]
    result = QueryResult(answer="...", sources=sources)
    assert "Hợp đồng" in result.citation
    assert "Luật LĐ" in result.citation


def test_query_result_empty_citation():
    result = QueryResult(answer="...", doc_name="Test")
    assert result.citation == "Test"


def test_structure_node_page_range():
    node = StructureNode(title="Chapter 1", start_index=1, end_index=10)
    assert node.page_range == "1–10"

    node2 = StructureNode(title="Intro", start_index=1, end_index=1)
    assert node2.page_range == "1"


def test_query_source_citation():
    src = QuerySource(doc_id="uuid", doc_name="Test Doc", page_refs=[5, 6, 7])
    assert src.citation == "Test Doc tr.5, 6, 7"

    src2 = QuerySource(doc_id="uuid", doc_name="Test Doc", page_refs=[])
    assert src2.citation == "Test Doc"


def test_health_result_is_healthy():
    h = HealthResult(status="ok")
    assert h.is_healthy is True

    h2 = HealthResult(status="degraded")
    assert h2.is_healthy is False
