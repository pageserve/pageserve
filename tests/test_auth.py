import base64

from pageserve._auth import build_auth_header, build_headers


def test_build_auth_header_format():
    header = build_auth_header("pub-key", "sec-key")
    assert header.startswith("Basic ")
    decoded = base64.b64decode(header[6:]).decode()
    assert decoded == "pub-key:sec-key"


def test_build_auth_header_encoding():
    header = build_auth_header("pub-key-abcdef", "sec-key-uvwxyz")
    assert "Basic " in header
    decoded = base64.b64decode(header[6:]).decode()
    assert "pub-key-abcdef" in decoded
    assert "sec-key-uvwxyz" in decoded


def test_build_headers():
    headers = build_headers("pub-key", "sec-key")
    assert "Authorization" in headers
    assert headers["Authorization"].startswith("Basic ")
    assert headers["Content-Type"] == "application/json"
