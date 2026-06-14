# Authentication

## Key format

PageIndex uses a public/secret key pair:

```
Public key:  pk_live_<your-public-key>
Secret key:  sk_live_<your-secret-key>
```

Both keys are passed together via HTTP Basic Auth. The SDK handles encoding automatically.

## How the SDK authenticates

Under the hood, every request includes:

```
Authorization: Basic base64("<your-public-key>:<your-secret-key>")
```

You pass the raw keys to the client constructor — no manual encoding needed:

```python
from pageserve import PageServeClient

client = PageServeClient(
    base_url   = "https://pageindex.company.com",
    public_key = "<your-public-key>",
    secret_key = "<your-secret-key>",
)
```

## Best practice: use environment variables

Never hardcode credentials in source code. Read them from environment variables instead:

```python
import os
from pageserve import PageServeClient

client = PageServeClient(
    base_url   = os.environ["PAGESERVE_URL"],
    public_key = os.environ["PAGESERVE_PUBLIC_KEY"],
    secret_key = os.environ["PAGESERVE_SECRET_KEY"],
)
```

The CLI and MCP server also read these same env var names automatically.

## Managing API keys

### List keys

```python
keys = client.list_keys()
for k in keys:
    print(k.name, k.key_type, k.request_count)
```

### Create a key

```python
new_key = client.create_key(
    name       = "My App",
    key_type   = "live",
    scopes     = ["read", "write"],
    expires_at = None,             # or "2027-01-01T00:00:00Z"
)

# The secret_key is only shown once — save it now
print(new_key.public_key)
print(new_key.secret_key)
```

### Revoke a key

```python
client.revoke_key(key_id)
```

## Auth errors

| Error | Meaning |
|---|---|
| `AuthError` (401) | Invalid or expired key |
| `AuthError` (403) | Key exists but lacks the required scope |

```python
from pageserve import AuthError

try:
    docs = client.list_documents()
except AuthError as e:
    print(f"Auth failed: {e}")
```

---

**See also:** [Getting Started](getting-started.md) · [Error Handling](error-handling.md) · [Back to docs index](../README.md#documentation)
