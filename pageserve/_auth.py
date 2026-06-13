import base64


def build_auth_header(public_key: str, secret_key: str) -> str:
    """Return the Authorization header value for HTTP Basic Auth.

    Usage:
        headers = {"Authorization": build_auth_header(pk, sk)}
    """
    credential = f"{public_key}:{secret_key}"
    encoded = base64.b64encode(credential.encode()).decode()
    return f"Basic {encoded}"


def build_headers(public_key: str, secret_key: str) -> dict[str, str]:
    """Return a complete headers dict ready to pass to httpx."""
    return {
        "Authorization": build_auth_header(public_key, secret_key),
        "Content-Type": "application/json",
    }
