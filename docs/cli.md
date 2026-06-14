# CLI Reference

The `pageserve` command exposes the most common operations without writing any Python. Install it with:

```bash
pip install "pageserve[cli]"
```

## Configuration

Every command reads credentials from environment variables, or from the equivalent global option:

| Option | Environment variable |
| --- | --- |
| `--base-url` | `PAGESERVE_URL` |
| `--public-key` | `PAGESERVE_PUBLIC_KEY` |
| `--secret-key` | `PAGESERVE_SECRET_KEY` |

Export them once in your shell profile rather than passing them on every invocation:

```bash
export PAGESERVE_URL=https://pageindex.company.com
export PAGESERVE_PUBLIC_KEY=<your-public-key>
export PAGESERVE_SECRET_KEY=<your-secret-key>
```

Run `pageserve --version` to print the installed version, or `pageserve --help` for the full command list.

---

## `pageserve list`

List documents in the project.

```bash
pageserve list                       # completed documents (default)
pageserve list --status all          # every status
pageserve list --status indexing     # filter by status
pageserve list --json                # machine-readable output
```

`--status` accepts `completed` (default), `pending`, `indexing`, `failed`, or `all`. Default output is a table with a status icon (✅ / ⏳ / ⏸ / ❌) per document.

## `pageserve query`

Ask a question against a single document. `DOC_ID` and `QUESTION` are positional arguments.

```bash
pageserve query <doc_id> "What are the probation terms?"
pageserve query <doc_id> "Summarize the termination clause" --stream
pageserve query <doc_id> "What are the probation terms?" --json
```

| Flag | Effect |
| --- | --- |
| `--stream` | Stream tokens as they arrive, with live tool-call and source indicators |
| `--json` | Print the full `QueryResult` as JSON |

Without flags, the answer is printed to stdout and the citation + elapsed time to stderr, so you can pipe just the answer:

```bash
pageserve query <doc_id> "..." > answer.txt
```

## `pageserve retrieve`

Retrieve the **raw content** of the sections relevant to a question — no answer is synthesized. Cheaper than `query` (one LLM call per document just to navigate the tree). `DOC_ID` and `QUESTION` are positional arguments.

```bash
pageserve retrieve <doc_id> "What are the probation terms?"
pageserve retrieve <doc_id> "..." --json
pageserve retrieve _ "Compare the two contracts" --docs <doc_a>,<doc_b>
```

| Flag | Effect |
| --- | --- |
| `--docs` | Retrieve across multiple documents (comma-separated). When set, the positional `DOC_ID` is ignored — pass `_` as a placeholder. |
| `--json` | Print the full `RetrieveResult` as JSON |

Without flags, each matching section is printed with its title, page range, and page text.

## `pageserve upload`

Upload a PDF and start indexing.

```bash
pageserve upload ./report.pdf            # upload and return immediately
pageserve upload ./report.pdf --watch    # upload + live progress bar
pageserve upload ./report.pdf --wait     # upload + wait until indexing completes
```

`--watch` and `--wait` both stream indexing progress (a `[████░░] 72%` bar) until the document reaches `completed` or `failed`.

## `pageserve health`

Check service status, queue depth, and capacity.

```bash
pageserve health
pageserve health --json
```

## `pageserve keys`

Manage API keys.

```bash
# List keys (name, public-key prefix, type, request count, last used)
pageserve keys list
pageserve keys list --json

# Create a key — the secret is printed once and cannot be retrieved again
pageserve keys create "Production"
pageserve keys create "Read-only CI" --type test --scopes read
pageserve keys create "Temp" --expires 2027-01-01T00:00:00Z

# Revoke a key (prompts for confirmation unless --yes is passed)
pageserve keys revoke <key_id>
pageserve keys revoke <key_id> --yes
```

`keys create` options: `--type` (`live` | `test`, default `live`), `--scopes` (comma-separated, default `read,write`), `--expires` (ISO 8601 datetime).

## `pageserve mcp`

Run the [MCP server](mcp-server.md).

```bash
pageserve mcp                                       # stdio (default) — Claude Desktop / Cursor
pageserve mcp --transport sse --port 3000           # SSE
pageserve mcp --transport streamable-http --host 0.0.0.0 --port 3000
pageserve mcp --name my-docs                         # custom server name
```

`--transport` accepts `stdio` (default), `sse`, or `streamable-http`. `--host` (default `127.0.0.1`) and `--port` (default `3000`) apply only to the `sse` / `streamable-http` transports. See the [MCP Server guide](mcp-server.md) for client setup.

---

**See also:** [MCP Server](mcp-server.md) · [Authentication](authentication.md) · [Back to docs index](../README.md#documentation)
