def create_mcp_server(
    base_url: str | None = None,
    public_key: str | None = None,
    secret_key: str | None = None,
    name: str = "pageindex",
):
    try:
        from pageserve.mcp._server import _create_server
    except ImportError:
        raise ImportError("MCP support cần cài thêm:\n    pip install 'pageserve[mcp]'")
    return _create_server(
        base_url=base_url, public_key=public_key, secret_key=secret_key, name=name
    )


__all__ = ["create_mcp_server"]
