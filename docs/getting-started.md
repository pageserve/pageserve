# Getting Started

## Prerequisites

- Python 3.10+
- A running PageIndex self-hosted instance
- A project API key pair (public + secret)

## Installation

Install the base SDK:

```bash
pip install pageserve
```

Or install with optional extras:

```bash
pip install "pageserve[mcp]"   # adds MCP server support
pip install "pageserve[cli]"   # adds CLI commands
pip install "pageserve[all]"   # everything
```

## Your first query

```python
from pageserve import PageServeClient

client = PageServeClient(
    base_url   = "https://pageindex.company.com",
    public_key = "<your-public-key>",
    secret_key = "<your-secret-key>",
)

# See what documents are available
docs = client.list_documents()
for doc in docs:
    print(doc.doc_id, doc.name, doc.page_count)

# Ask a question
result = client.query(docs[0].doc_id, "What are the probation terms?")

print(result.answer)
print(result.citation)   # e.g. "Employment Contract p.5, 6"
print(result.page_refs)  # e.g. [5, 6]
```

## Upload a document

```python
# Fire and forget
upload = client.upload("./contract.pdf")
print(f"Uploaded: {upload.doc_id} (status: {upload.status})")

# Or wait until indexing completes
upload = client.upload("./contract.pdf", wait=True)
print("Ready!")
```

## Use as a context manager

The client holds an httpx connection pool. Close it explicitly or use a `with` block:

```python
with PageServeClient(base_url, pk, sk) as client:
    docs = client.list_documents()
# connection pool is closed automatically here
```

## Next steps

- [Authentication](authentication.md) — understand key formats and how auth works
- [Sync Client Reference](sync-client.md) — full method reference
- [Async Client Reference](async-client.md) — for FastAPI and async code
- [Streaming](streaming.md) — stream answers token by token
- [MCP Server](mcp-server.md) — connect Claude or other agents to your documents

---

**See also:** [CLI Reference](cli.md) · [Error Handling](error-handling.md) · [Back to docs index](../README.md#documentation)
