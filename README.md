# pageserve

Python SDK and MCP server for [PageIndex](https://github.com/VectifyAI/PageIndex) self-hosted RAG service.

PageIndex is a reasoning-based RAG engine that navigates document structure rather than doing vector similarity search — it reads the table of contents, picks the right sections, and synthesizes answers with page-level citations.

## Installation

```bash
pip install pageserve              # SDK only (sync + async)
pip install "pageserve[mcp]"       # + MCP server for agent frameworks
pip install "pageserve[cli]"       # + CLI commands
pip install "pageserve[all]"       # everything
```

## Quick start

```python
from pageserve import PageServeClient

client = PageServeClient(
    base_url   = "https://pageindex.company.com",
    public_key = "<your-public-key>",
    secret_key = "<your-secret-key>",
)

# List indexed documents
docs = client.list_documents()

# Ask a question
result = client.query(docs[0].doc_id, "What are the probation terms?")
print(result.answer)
print(result.citation)   # "Employment Contract p.5, 6"
print(result.page_refs)  # [5, 6]

# Upload and wait for indexing to complete
upload = client.upload("./contract.pdf", wait=True)

# Read specific pages (no LLM, instant)
pages = client.get_pages(docs[0].doc_id, "22-24")
```

## Async usage

```python
import asyncio
from pageserve import AsyncPageServeClient

async def main():
    async with AsyncPageServeClient(
        base_url   = "https://pageindex.company.com",
        public_key = "<your-public-key>",
        secret_key = "<your-secret-key>",
    ) as client:
        docs = await client.list_documents()

        # Query multiple documents concurrently
        results = await client.query_many([
            (docs[0].doc_id, "What are the probation terms?"),
            (docs[1].doc_id, "What does the law say about probation?"),
        ])
        for r in results:
            print(r.answer)

asyncio.run(main())
```

## Streaming

```python
for event in client.query_stream(doc_id, "What are the key clauses?"):
    if event.type == "token":
        print(event.content, end="", flush=True)
    elif event.type == "sources":
        for src in event.sources:
            print(f"\nSource: {src.citation}")
    elif event.type == "done":
        break
```

## MCP server (Claude Desktop / Cursor)

Run the MCP server so Claude or any MCP-compatible agent can query your documents:

```json
{
  "mcpServers": {
    "pageindex": {
      "command": "pageserve",
      "args": ["mcp"],
      "env": {
        "PAGESERVE_URL":        "https://pageindex.company.com",
        "PAGESERVE_PUBLIC_KEY": "<your-public-key>",
        "PAGESERVE_SECRET_KEY": "<your-secret-key>"
      }
    }
  }
}
```

The MCP server exposes five tools:
- `list_documents` — see what documents are available
- `query_document` — ask a question against one document
- `query_multiple_documents` — cross-reference multiple documents
- `get_page_content` — read raw page text (no LLM, instant)
- `get_document_structure` — browse the table of contents

Keys live in env vars and never appear in tool arguments or the model's context window.

## CLI

```bash
export PAGESERVE_URL=https://pageindex.company.com
export PAGESERVE_PUBLIC_KEY=<your-public-key>
export PAGESERVE_SECRET_KEY=<your-secret-key>

pageserve list                                      # list documents
pageserve query <doc_id> "question"                 # ask a question
pageserve query <doc_id> "question" --stream        # streaming output
pageserve upload ./report.pdf --watch               # upload + progress bar
pageserve health                                    # service status
pageserve keys list                                 # list API keys
pageserve keys create "My App"                      # create a key
pageserve mcp                                       # run MCP server (stdio)
pageserve mcp --transport sse --port 3000           # MCP over SSE
```

## Error handling

```python
from pageserve import (
    AuthError,
    NotFoundError,
    DocumentNotReadyError,
    FileTooLargeError,
    RateLimitError,
    ServiceUnavailableError,
    ServiceError,
)

try:
    result = client.query(doc_id, "question")
except AuthError:
    print("Invalid or expired API key")
except NotFoundError:
    print("Document not found")
except RateLimitError as e:
    import time; time.sleep(e.retry_after)
except ServiceError as e:
    print(f"Server error [{e.status_code}]")
```

## Documentation

- [Getting Started](docs/getting-started.md)
- [Authentication](docs/authentication.md)
- [Sync Client Reference](docs/sync-client.md)
- [Async Client Reference](docs/async-client.md)
- [Streaming (SSE)](docs/streaming.md)
- [MCP Server](docs/mcp-server.md)
- [CLI Reference](docs/cli.md)
- [Data Models](docs/models.md)
- [Error Handling](docs/error-handling.md)

## Related

- [PageIndex OSS](https://github.com/VectifyAI/PageIndex) — the self-hosted service this SDK wraps
- [PageIndex Cloud](https://pageindex.ai) — hosted version
