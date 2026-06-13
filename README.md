<div align="center">

# PageServe

**Python SDK and MCP server for [PageIndex](https://github.com/VectifyAI/PageIndex) — the self-hosted, reasoning-based RAG engine.**

[![PyPI version](https://img.shields.io/pypi/v/pageserve.svg)](https://pypi.org/project/pageserve/)
[![Python versions](https://img.shields.io/pypi/pyversions/pageserve.svg)](https://pypi.org/project/pageserve/)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![Checked with mypy](https://img.shields.io/badge/mypy-checked-2a6db2.svg)](http://mypy-lang.org/)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

[Installation](#installation) · [Quick Start](#quick-start) · [MCP Server](#mcp-server) · [CLI](#cli) · [Documentation](#documentation)

</div>

---

PageServe is a typed, batteries-included client for [PageIndex](https://github.com/VectifyAI/PageIndex), a **reasoning-based RAG engine** that navigates document structure instead of doing vector similarity search. It reads the table of contents, picks the right sections, and synthesizes answers with **page-level citations** — no embeddings, no vector database, no chunking heuristics.

One install gives you three ways to talk to your PageIndex deployment:

- 🐍 **A Python SDK** — synchronous and asynchronous clients, fully typed with Pydantic models.
- 🤖 **An MCP server** — drop your documents into Claude Desktop, Cursor, or any MCP-compatible agent.
- ⌨️ **A CLI** — query, upload, and manage documents straight from the terminal.

## Features

- **Vector-free retrieval** — answers come with exact page references (`Employment Contract p.5, 6`), not opaque similarity scores.
- **Sync & async** — `PageServeClient` and `AsyncPageServeClient`, including concurrent `query_many`.
- **Streaming** — token-by-token responses over Server-Sent Events.
- **Model Context Protocol** — expose your corpus to LLM agents with keys kept out of the model's context.
- **Fully typed** — Pydantic v2 models and strict, descriptive exceptions for every failure mode.
- **Minimal core** — only `httpx` and `pydantic` required; MCP and CLI are opt-in extras.

## Installation

```bash
pip install pageserve              # SDK only (sync + async)
pip install "pageserve[mcp]"       # + MCP server for agent frameworks
pip install "pageserve[cli]"       # + CLI commands
pip install "pageserve[all]"       # everything
```

Requires **Python 3.10+**.

## Quick Start

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

## Async Usage

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

## MCP Server

Run the MCP server so Claude Desktop, Cursor, or any MCP-compatible agent can query your documents:

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

The server exposes five tools:

| Tool | Description |
| --- | --- |
| `list_documents` | See what documents are available |
| `query_document` | Ask a question against one document |
| `query_multiple_documents` | Cross-reference multiple documents |
| `get_page_content` | Read raw page text (no LLM, instant) |
| `get_document_structure` | Browse the table of contents |

> Keys live in environment variables and never appear in tool arguments or the model's context window.

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

## Error Handling

Every failure mode maps to a specific, catchable exception:

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

| Guide | |
| --- | --- |
| [Getting Started](docs/getting-started.md) | Install, configure, and run your first query |
| [Authentication](docs/authentication.md) | API keys and credential handling |
| [Sync Client Reference](docs/sync-client.md) | `PageServeClient` API |
| [Async Client Reference](docs/async-client.md) | `AsyncPageServeClient` API |
| [Streaming (SSE)](docs/streaming.md) | Token-by-token responses |
| [MCP Server](docs/mcp-server.md) | Tools, transports, and agent setup |
| [CLI Reference](docs/cli.md) | All commands and flags |
| [Data Models](docs/models.md) | Pydantic response models |
| [Error Handling](docs/error-handling.md) | Exception hierarchy |

## Contributing

Contributions are welcome! To set up a development environment:

```bash
git clone https://github.com/pageserve/pageserve.git
cd pageserve
pip install -e ".[all,dev]"

pytest          # run the test suite
ruff check .    # lint
mypy pageserve  # type-check
```

Please open an issue to discuss substantial changes before submitting a pull request.

## License

Licensed under the [Apache License 2.0](LICENSE). © 2026 PageServe.

## Related

- [PageIndex OSS](https://github.com/VectifyAI/PageIndex) — the self-hosted service this SDK wraps
- [PageIndex Cloud](https://pageindex.ai) — hosted version
