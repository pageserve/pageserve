# CLI Reference

The `pageserve` CLI gives you access to the most common operations without writing any Python.

## Global options

Every command accepts these options (or the equivalent environment variable):

| Option | Env var | Default |
|---|---|---|
| `--base-url` | `PAGESERVE_URL` | — |
| `--public-key` | `PAGESERVE_PUBLIC_KEY` | — |
| `--secret-key` | `PAGESERVE_SECRET_KEY` | — |

Recommended: put the env vars in your shell profile or a `.env` file rather than passing them on every command.

```bash
export PAGESERVE_URL=https://pageindex.company.com
export PAGESERVE_PUBLIC_KEY=<your-public-key>
export PAGESERVE_SECRET_KEY=<your-secret-key>
```

## `pageserve mcp`

Start the MCP server (stdio by default, for Claude Desktop and Cursor).

```bash
pageserve mcp
pageserve mcp --transport sse --port 3000
pageserve mcp --transport streamable-http --port 3000
```

See [MCP Server](mcp-server.md) for the full setup guide.

## `pageserve list`

List all documents in the index.

```bash
pageserve list
pageserve list --status completed
pageserve list --tag legal --tag contracts
pageserve list --limit 50
```

Output:

```
doc_id                               name                         status      pages
────────────────────────────────────────────────────────────────────────────────────
3f2a1b0c-...                         employment-contract.pdf      completed   24
7e8d9c0b-...                         labor-law-2024.pdf           completed   88
```

## `pageserve query`

Ask a question against one or more documents.

```bash
# Single document
pageserve query --doc-id 3f2a1b0c-... "What are the probation terms?"

# Multiple documents
pageserve query \
  --doc-id 3f2a1b0c-... \
  --doc-id 7e8d9c0b-... \
  "Does the contract comply with labor law on probation pay?"

# Stream tokens as they arrive
pageserve query --doc-id 3f2a1b0c-... --stream "Summarize the termination clause"
```

Output (non-streaming):

```
Answer:
The probation period is 60 days, with pay at 85% of base salary...

Sources:
  employment-contract.pdf p.5, 6
```

## `pageserve upload`

Upload a PDF to PageIndex and optionally wait for indexing to complete.

```bash
# Upload and return immediately
pageserve upload ./report.pdf

# Upload and wait until indexing is done (up to 10 min)
pageserve upload ./report.pdf --wait

# Custom wait timeout
pageserve upload ./report.pdf --wait --max-wait 300
```

Output:

```
Uploaded: 3f2a1b0c-4d5e-6f7a-8b9c-0d1e2f3a4b5c
Status:   pending

Waiting for indexing...
[████████████████████████████░░] 92%
Status:   completed
```

## `pageserve health`

Check whether the service is up and how much capacity is available.

```bash
pageserve health
```

Output:

```
Status:  ok
Queue:   2 pending, 4 workers
Storage: 14.2 GB available
RAM:     3.8 GB free
```

## `pageserve keys`

Manage API keys.

### `pageserve keys list`

```bash
pageserve keys list
```

Output:

```
id          name          type   scopes         requests
──────────────────────────────────────────────────────────
ak_1a2b3c   My App        live   read, write    1,204
ak_9x8y7z   CI Runner     live   read           88
```

### `pageserve keys create`

```bash
pageserve keys create "My App" --type live --scope read --scope write
```

Output:

```
Public key: <your-public-key>
Secret key: <your-secret-key>   ← save this now, it won't be shown again
```

### `pageserve keys revoke`

```bash
pageserve keys revoke ak_1a2b3c
```

## Exit codes

| Code | Meaning |
|---|---|
| 0 | Success |
| 1 | Auth error (invalid or expired key) |
| 2 | Not found |
| 3 | Service error (5xx) |
| 4 | Timeout |
