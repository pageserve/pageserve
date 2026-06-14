# MCP Server

The MCP server lets Claude Desktop, Cursor, and other [Model Context Protocol](https://modelcontextprotocol.io/) agents query your PageIndex documents directly — no prompt glue required.

Credentials live in environment variables on the local machine and never appear in tool arguments or the model's context window.

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

That's all. The agent will see five tools under the `pageindex` namespace.

## Available tools

| Tool | Signature | Returns |
| --- | --- | --- |
| `list_documents` | `()` | `[{doc_id, name, page_count, description, tags}]` |
| `retrieve_document` | `(doc_id_or_ids, question, max_sections=6, include_content=True)` | `{doc_ids, question, elapsed_ms, cached, results: [{doc_id, doc_name, doc_description, sections: [{title, node_id, page_start, page_end, summary, pages: [{page, content}] \| null}]}]}` |
| `get_page_content` | `(doc_id, pages)` | `[{page, content}]` — instant, no LLM call |
| `get_document_structure` | `(doc_id, depth=2)` | `[{title, node_id, start_index, end_index, page_range, summary, has_children, nodes}]` |
| `get_service_health` | `()` | `{status, healthy, queue, system}` |

**Notes**

- The MCP host is itself an LLM agent, so the server exposes **`retrieve_document` as the primitive** — it returns raw section content for the host to read, with no second answer-synthesis pass. The old `query_document` / `query_multiple_documents` tools were removed in 0.1.2 (they ran PageServe's internal agent loop, roughly doubling backend token cost). Call `retrieve_document` instead and let the host compose the answer.
- `retrieve_document` with `include_content=False` returns section metadata + `summary` only (cheap on tokens). Follow up with `get_page_content` on the exact `page_range` you need — the "hybrid" pattern.
- `get_page_content` page spec: `"5"` (single), `"5-7"` (range), `"3,8,12"` (list).
- `get_document_structure` depth: `1` = chapters only, `2` = chapters + sections (default), `0` = full tree.
- A typical agent flow is `list_documents` → `retrieve_document` → optionally `get_page_content` to surface full source text.

## SSE transport (remote / web agents)

```bash
PAGESERVE_URL=https://pageindex.company.com \
PAGESERVE_PUBLIC_KEY=<your-public-key> \
PAGESERVE_SECRET_KEY=<your-secret-key> \
pageserve mcp --transport sse --host 0.0.0.0 --port 3000
```

`--host` defaults to `127.0.0.1` and `--port` to `3000`. Connect with:

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

`--transport streamable-http` is also supported (served at `/mcp`).

## Embedding in Python

The host and port must be set **when the server is created** — `FastMCP.run()` does not accept a `port` argument:

```python
import os
from pageserve.mcp import create_mcp_server

mcp = create_mcp_server(
    base_url   = os.environ["PAGESERVE_URL"],
    public_key = os.environ["PAGESERVE_PUBLIC_KEY"],
    secret_key = os.environ["PAGESERVE_SECRET_KEY"],
    host       = "127.0.0.1",   # used by sse / streamable-http only
    port       = 3000,
)

mcp.run()                              # stdio (default)
mcp.run(transport="sse")               # SSE on the host:port set above
mcp.run(transport="streamable-http")   # Streamable HTTP
```

## Using it from the Claude API

The Anthropic Messages API can connect to **remote** MCP servers via the `mcp_servers` parameter — those entries must be `type: "url"` pointing at an HTTP/SSE endpoint, so first run the server with `--transport sse` (or `streamable-http`) and expose it at a reachable URL:

```python
import anthropic

client = anthropic.Anthropic()

response = client.beta.messages.create(
    model="claude-opus-4-8",
    max_tokens=4096,
    mcp_servers=[{
        "type": "url",
        "name": "pageindex",
        "url":  "https://your-host.example.com/sse",
    }],
    betas=["mcp-client-2025-04-04"],
    messages=[{
        "role": "user",
        "content": "Does our employment contract comply with labor law on probation pay?",
    }],
)
print(response.content[-1].text)
```

> The Messages API connector does **not** launch local `stdio` servers — it only connects to remote URLs. For a local server (the `pageserve mcp` stdio default), drive it through an MCP-capable client such as Claude Desktop, Cursor, or the Claude Agent SDK, or use the Anthropic SDK's MCP tool-conversion helpers (`anthropic.lib.tools.mcp`) to bridge a local stdio session into a tool runner.

## Security note

**Prefer stdio for local use.** With stdio, the keys live in the local process environment and never travel over the network. With SSE / Streamable HTTP, the keys must still be present in the server process, and requests reach it over the network — fine for local development behind localhost, but put it behind TLS and authentication before exposing it beyond your machine.

---

**See also:** [CLI Reference](cli.md) · [Authentication](authentication.md) · [Back to docs index](../README.md#documentation)
