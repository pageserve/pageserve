# MCP Server

The MCP server lets Claude, Cursor, and other MCP-compatible agents query your PageIndex documents directly — without you having to write any prompt glue.

Keys are stored in environment variables on the local machine and never appear in tool arguments or the model's context window.

## Installation

```bash
pip install "pageserve[mcp]"
```

## Claude Desktop / Cursor (stdio transport)

Add this to your `claude_desktop_config.json` or Cursor MCP config:

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

That's all. Claude will see five tools under the `pageindex` namespace.

## Available tools

### `list_documents`

List all indexed documents. Call this first to discover what's available and get doc IDs.

**Returns:** `[{doc_id, name, page_count, description, tags}]`

### `query_document(doc_id, question)`

Ask a question against one document. The LLM navigates the structure and synthesizes an answer.

**Returns:** `{answer, page_refs, sources (citation string), raw_pages, elapsed_ms, cached}`

### `query_multiple_documents(doc_ids, question)`

Cross-reference multiple documents in one call. Good for compliance checks ("does this contract match the law?").

**Returns:** `{answer, sources: [{doc_id, doc_name, page_refs, citation, raw_pages}]}`

### `get_page_content(doc_id, pages)`

Get raw text for specific pages. Instant, no LLM involved. Use after a `query_document` call to read the full source pages.

**pages format:** `"5"` (single), `"5-7"` (range), `"3,8,12"` (multiple)

**Returns:** `[{page, content}]`

### `get_document_structure(doc_id, depth=2)`

Get the hierarchical table of contents. Use to understand what sections a document contains before asking questions.

**depth:** 1 = chapters only, 2 = chapters + sections (default), 0 = full tree

**Returns:** `[{title, node_id, start_index, end_index, page_range, summary, has_children, nodes}]`

### `get_service_health`

Check if the service is up and how much capacity remains.

**Returns:** `{status, healthy, queue: {pending, workers}, system: {ram_available_gb, max_file_mb}}`

## Typical agent workflow

Claude will usually:
1. Call `list_documents` to see what's available
2. Call `query_document` or `query_multiple_documents` with the user's question
3. Optionally call `get_page_content` to show the full source text

## SSE transport (for web agents)

Start the MCP server with SSE transport for browser-based or remote agents:

```bash
PAGESERVE_URL=https://pageindex.company.com \
PAGESERVE_PUBLIC_KEY=<your-public-key> \
PAGESERVE_SECRET_KEY=<your-secret-key> \
pageserve mcp --transport sse --port 3000
```

Connect with:

```json
{
  "mcpServers": {
    "pageindex": {
      "type": "sse",
      "url":  "http://localhost:3000/sse"
    }
  }
}
```

## Embed in Python

```python
import os
from pageserve.mcp import create_mcp_server

mcp = create_mcp_server(
    base_url   = os.environ["PAGESERVE_URL"],
    public_key = os.environ["PAGESERVE_PUBLIC_KEY"],
    secret_key = os.environ["PAGESERVE_SECRET_KEY"],
)

mcp.run()                                     # stdio (default)
mcp.run(transport="sse", port=3000)           # SSE
mcp.run(transport="streamable-http", port=3000)
```

## Anthropic Messages API

```python
import os
import anthropic

client = anthropic.Anthropic()

response = client.messages.create(
    model      = "claude-sonnet-4-6",
    max_tokens = 4096,
    mcp_servers = [{
        "type":    "stdio",
        "command": "pageserve",
        "args":    ["mcp"],
        "env": {
            "PAGESERVE_URL":        "https://pageindex.company.com",
            "PAGESERVE_PUBLIC_KEY": os.environ["PAGESERVE_PUBLIC_KEY"],
            "PAGESERVE_SECRET_KEY": os.environ["PAGESERVE_SECRET_KEY"],
        },
    }],
    messages = [{
        "role":    "user",
        "content": "Does our employment contract comply with labor law on probation pay?",
    }],
)
print(response.content[0].text)
```

## Security note

**stdio > HTTP for local use.** With stdio, the keys live in the process environment and never travel over the network. With SSE/HTTP, the keys must be present in the server process but requests still go over localhost — which is fine for local dev but worth thinking about in shared environments.
