import httpx
import pytest
import respx

from pageserve import PageServeClient
from pageserve._exceptions import AuthError, NotFoundError

BASE_URL = "https://pageindex.test"
PUBLIC_KEY = "test-public-key"
SECRET_KEY = "test-secret-key"


@respx.mock
def test_list_documents(client, mock_documents):
    respx.get(f"{client._base}/v1/documents").mock(
        return_value=httpx.Response(200, json=mock_documents)
    )
    docs = client.list_documents()

    assert len(docs) == 2
    assert docs[0].doc_id == "uuid-hop-dong"
    assert docs[0].name == "hop-dong-lao-dong.pdf"
    assert docs[0].is_ready is True


@respx.mock
def test_list_documents_empty(client):
    respx.get(f"{client._base}/v1/documents").mock(
        return_value=httpx.Response(200, json={"total": 0, "documents": []})
    )
    docs = client.list_documents()
    assert docs == []


@respx.mock
def test_list_documents_auth_error(client):
    respx.get(f"{client._base}/v1/documents").mock(
        return_value=httpx.Response(401, json={"detail": "Invalid API key"})
    )
    with pytest.raises(AuthError):
        client.list_documents()


@respx.mock
def test_get_document(client, mock_documents):
    doc_data = mock_documents["documents"][0]
    respx.get(f"{client._base}/v1/documents/uuid-hop-dong").mock(
        return_value=httpx.Response(200, json=doc_data)
    )
    doc = client.get_document("uuid-hop-dong")
    assert doc.doc_id == "uuid-hop-dong"
    assert doc.page_count == 12


@respx.mock
def test_get_document_not_found(client):
    respx.get(f"{client._base}/v1/documents/nonexistent").mock(
        return_value=httpx.Response(404, json={"detail": "Not found"})
    )
    with pytest.raises(NotFoundError):
        client.get_document("nonexistent")


@respx.mock
def test_query_single_doc(client, mock_query_response):
    respx.post(f"{client._base}/v1/query").mock(
        return_value=httpx.Response(200, json=mock_query_response)
    )
    result = client.query("uuid-hop-dong", "điều khoản thử việc")

    assert result.answer == "Hợp đồng quy định thử việc 3 tháng với lương 80%."
    assert result.page_refs == [5, 6]
    assert result.doc_name == "hop-dong-lao-dong.pdf"
    assert "tr.5, 6" in result.citation
    assert len(result.raw_pages) == 2
    assert result.raw_pages[0].page == 5


@respx.mock
def test_query_multi_docs(client, mock_multi_query_response):
    respx.post(f"{client._base}/v1/query").mock(
        return_value=httpx.Response(200, json=mock_multi_query_response)
    )
    result = client.query_docs(["uuid-hop-dong", "uuid-luat-ld"], "hợp đồng có đúng luật không?")

    assert len(result.sources) == 2
    assert result.sources[0].doc_id == "uuid-hop-dong"
    assert result.sources[0].page_refs == [5, 6]
    assert result.sources[1].doc_id == "uuid-luat-ld"
    assert result.sources[1].page_refs == [22, 24]
    assert "hop-dong-lao-dong.pdf" in result.citation


@respx.mock
def test_query_many_parallel(client, mock_query_response):
    respx.post(f"{client._base}/v1/query").mock(
        return_value=httpx.Response(200, json=mock_query_response)
    )
    results = client.query_many(
        [
            ("uuid-1", "câu hỏi 1"),
            ("uuid-2", "câu hỏi 2"),
            ("uuid-3", "câu hỏi 3"),
        ],
        max_workers=3,
    )

    assert len(results) == 3
    assert all(r is not None for r in results)


@respx.mock
def test_retrieve_single_doc(client, mock_retrieve_response):
    route = respx.post(f"{client._base}/v1/retrieve").mock(
        return_value=httpx.Response(200, json=mock_retrieve_response)
    )
    result = client.retrieve("uuid-hop-dong", "điều khoản thử việc")

    import json as _json

    sent = _json.loads(route.calls.last.request.read())
    assert sent == {
        "question": "điều khoản thử việc",
        "doc_id": "uuid-hop-dong",
        "max_sections": 6,
        "max_pages_per_section": 4,
        "include_content": True,
        "include_summary": True,
    }
    assert result.doc_ids == ["uuid-hop-dong"]
    assert result.cached is False
    assert len(result.results) == 1
    sec = result.results[0].sections[0]
    assert sec.title == "Thử việc"
    assert sec.page_range == "5–6"
    assert len(sec.pages) == 2
    # convenience accessors
    assert len(result.sections) == 1
    assert "Thời gian thử việc" in result.text


@respx.mock
def test_retrieve_multi_docs_sends_doc_ids(client, mock_retrieve_response):
    route = respx.post(f"{client._base}/v1/retrieve").mock(
        return_value=httpx.Response(200, json=mock_retrieve_response)
    )
    client.retrieve(["uuid-a", "uuid-b"], "so sánh")

    import json as _json

    body = _json.loads(route.calls.last.request.read())
    assert body == {
        "question": "so sánh",
        "doc_ids": ["uuid-a", "uuid-b"],
        "max_sections": 6,
        "max_pages_per_section": 4,
        "include_content": True,
        "include_summary": True,
    }


@respx.mock
def test_get_pages(client):
    respx.get(f"{client._base}/v1/documents/uuid-hop-dong/pages/5-6").mock(
        return_value=httpx.Response(
            200,
            json=[
                {"page": 5, "content": "Điều 4. Thời gian thử việc..."},
                {"page": 6, "content": "Lương thử việc 80%..."},
            ],
        )
    )
    pages = client.get_pages("uuid-hop-dong", "5-6")

    assert len(pages) == 2
    assert pages[0].page == 5
    assert "Điều 4" in pages[0].content
    assert pages[0].preview  # property hoạt động


@respx.mock
def test_get_structure(client):
    tree_data = [
        {
            "title": "Chương I",
            "node_id": "0001",
            "start_index": 1,
            "end_index": 5,
            "summary": "Tổng quan",
            "has_children": True,
            "nodes": [],
        }
    ]
    respx.get(f"{client._base}/v1/documents/uuid-hop-dong/structure").mock(
        return_value=httpx.Response(200, json=tree_data)
    )
    tree = client.get_structure("uuid-hop-dong")

    assert len(tree) == 1
    assert tree[0].title == "Chương I"
    assert tree[0].page_range == "1–5"


@respx.mock
def test_create_key(client):
    respx.post(f"{client._base}/v1/keys").mock(
        return_value=httpx.Response(
            201,
            json={
                "id": "key-uuid",
                "name": "Test Key",
                "public_key": "new-test-public-key",
                "secret_key": "new-test-secret-key",
                "secret_prefix": "new-test",
                "key_type": "live",
                "scopes": ["read", "write"],
                "is_active": True,
                "request_count": 0,
            },
        )
    )
    key = client.create_key("Test Key")

    assert key.public_key == "new-test-public-key"
    assert key.secret_key == "new-test-secret-key"
    assert key.key_type == "live"
    assert key.is_active is True


@respx.mock
def test_revoke_key(client):
    respx.delete(f"{client._base}/v1/keys/key-uuid").mock(return_value=httpx.Response(204))
    client.revoke_key("key-uuid")  # Không raise là pass


@respx.mock
def test_pdf_url(client):
    url = client.pdf_url("uuid-hop-dong")
    assert url == f"{client._base}/files/uuid-hop-dong.pdf"


def test_context_manager(mock_documents):
    with respx.mock:
        respx.get(f"{BASE_URL}/v1/documents").mock(
            return_value=httpx.Response(200, json=mock_documents)
        )
        with PageServeClient(BASE_URL, PUBLIC_KEY, SECRET_KEY) as c:
            docs = c.list_documents()
        assert len(docs) == 2
