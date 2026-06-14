from pageserve._async_client import AsyncPageServeClient
from pageserve._client import PageServeClient
from pageserve._exceptions import (
    AuthError,
    DocumentNotReadyError,
    FileTooLargeError,
    InsufficientStorageError,
    NotFoundError,
    PageServeError,
    RateLimitError,
    ServiceError,
    ServiceUnavailableError,
    TimeoutError,
)
from pageserve._models import (
    ApiKey,
    CreatedApiKey,
    Document,
    DocumentList,
    HealthResult,
    IndexProgress,
    Page,
    QueryResult,
    QuerySource,
    RetrieveDocResult,
    RetrieveResult,
    Section,
    SSEEvent,
    Stats,
    StructureNode,
    UploadResult,
    Webhook,
    WebhookTestResult,
)

__version__ = "0.1.1"
__author__ = "pageserve"
__license__ = "Apache-2.0"

__all__ = [
    # Clients
    "PageServeClient",
    "AsyncPageServeClient",
    # Models
    "Document",
    "DocumentList",
    "UploadResult",
    "StructureNode",
    "Page",
    "QueryResult",
    "QuerySource",
    "RetrieveResult",
    "RetrieveDocResult",
    "Section",
    "SSEEvent",
    "IndexProgress",
    "ApiKey",
    "CreatedApiKey",
    "Stats",
    "Webhook",
    "WebhookTestResult",
    "HealthResult",
    # Exceptions
    "PageServeError",
    "AuthError",
    "NotFoundError",
    "DocumentNotReadyError",
    "FileTooLargeError",
    "ServiceUnavailableError",
    "InsufficientStorageError",
    "RateLimitError",
    "ServiceError",
    "TimeoutError",
]
