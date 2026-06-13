import httpx
import pytest
import respx

from pageserve import AsyncPageServeClient

BASE_URL = "https://pageindex.test"
PUBLIC_KEY = "test-public-key"
SECRET_KEY = "test-secret-key"


@pytest.mark.asyncio
@respx.mock
async def test_async_list_documents(mock_documents):
    respx.get(f"{BASE_URL}/v1/documents").mock(
        return_value=httpx.Response(200, json=mock_documents)
    )
    async with AsyncPageServeClient(BASE_URL, PUBLIC_KEY, SECRET_KEY) as client:
        docs = await client.list_documents()

    assert len(docs) == 2
    assert docs[0].doc_id == "uuid-hop-dong"


@pytest.mark.asyncio
@respx.mock
async def test_async_query_many_concurrent(mock_query_response):
    respx.post(f"{BASE_URL}/v1/query").mock(
        return_value=httpx.Response(200, json=mock_query_response)
    )
    async with AsyncPageServeClient(BASE_URL, PUBLIC_KEY, SECRET_KEY) as client:
        results = await client.query_many(
            [
                ("uuid-1", "câu hỏi 1"),
                ("uuid-2", "câu hỏi 2"),
            ]
        )

    assert len(results) == 2
    assert all(r.answer for r in results)


@pytest.mark.asyncio
@respx.mock
async def test_async_context_manager(mock_documents):
    respx.get(f"{BASE_URL}/v1/documents").mock(
        return_value=httpx.Response(200, json=mock_documents)
    )
    async with AsyncPageServeClient(BASE_URL, PUBLIC_KEY, SECRET_KEY) as client:
        docs = await client.list_documents()
    assert len(docs) == 2
