import pytest

from pageserve import AsyncPageServeClient, PageServeClient

BASE_URL = "https://pageindex.test"
PUBLIC_KEY = "test-public-key"
SECRET_KEY = "test-secret-key"


@pytest.fixture
def client():
    """Sync client với respx mock."""
    return PageServeClient(
        base_url=BASE_URL,
        public_key=PUBLIC_KEY,
        secret_key=SECRET_KEY,
        timeout=5.0,
    )


@pytest.fixture
async def async_client():
    """Async client với respx mock."""
    async with AsyncPageServeClient(
        base_url=BASE_URL,
        public_key=PUBLIC_KEY,
        secret_key=SECRET_KEY,
        timeout=5.0,
    ) as c:
        yield c


@pytest.fixture
def mock_documents():
    return {
        "total": 2,
        "documents": [
            {
                "doc_id": "uuid-hop-dong",
                "name": "hop-dong-lao-dong.pdf",
                "status": "completed",
                "page_count": 12,
                "file_size": 102400,
                "description": "Hợp đồng lao động mẫu",
                "tags": ["legal", "hr"],
                "language": "vi",
                "created_at": "2026-06-13T10:00:00Z",
            },
            {
                "doc_id": "uuid-luat-ld",
                "name": "luat-lao-dong-2024.pdf",
                "status": "completed",
                "page_count": 142,
                "file_size": 2048000,
                "description": "Bộ luật Lao động 2024",
                "tags": ["legal"],
                "language": "vi",
                "created_at": "2026-06-10T08:00:00Z",
            },
        ],
    }


@pytest.fixture
def mock_query_response():
    """Single doc query response."""
    return {
        "doc_id": "uuid-hop-dong",
        "doc_name": "hop-dong-lao-dong.pdf",
        "question": "điều khoản thử việc",
        "answer": "Hợp đồng quy định thử việc 3 tháng với lương 80%.",
        "page_refs": [5, 6],
        "raw_pages": [
            {"page": 5, "content": "Điều 4. Thời gian thử việc: 03 tháng..."},
            {"page": 6, "content": "Lương thử việc: 80% lương chính thức..."},
        ],
        "elapsed_ms": 3200,
        "cached": False,
    }


@pytest.fixture
def mock_multi_query_response():
    """Multi-doc query response."""
    return {
        "answer": "Hợp đồng vi phạm 2 điểm: lương 80% (luật quy định 85%)...",
        "sources": [
            {
                "doc_id": "uuid-hop-dong",
                "doc_name": "hop-dong-lao-dong.pdf",
                "page_refs": [5, 6],
                "raw_pages": [
                    {"page": 5, "content": "Điều 4. Thời gian thử việc: 03 tháng, lương 80%..."},
                ],
            },
            {
                "doc_id": "uuid-luat-ld",
                "doc_name": "luat-lao-dong-2024.pdf",
                "page_refs": [22, 24],
                "raw_pages": [
                    {"page": 22, "content": "Điều 24. Thử việc tối đa 60 ngày..."},
                    {"page": 24, "content": "Điều 25. Lương tối thiểu 85%..."},
                ],
            },
        ],
        "elapsed_ms": 5400,
        "cached": False,
    }
