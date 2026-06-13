from pageserve._sse import parse_sse_line


def test_parse_token_event():
    result = parse_sse_line('data: {"type":"token","content":"Hợp"}')
    assert result == {"type": "token", "content": "Hợp"}


def test_parse_tool_start():
    result = parse_sse_line(
        'data: {"type":"tool_start","id":"abc","name":"query_document","args":{}}'
    )
    assert result["type"] == "tool_start"
    assert result["name"] == "query_document"


def test_parse_done():
    assert parse_sse_line("data: [DONE]") == {"type": "done"}


def test_skip_empty():
    assert parse_sse_line("") is None
    assert parse_sse_line("   ") is None


def test_skip_comment():
    assert parse_sse_line(": heartbeat") is None


def test_skip_non_data():
    assert parse_sse_line("event: message") is None
    assert parse_sse_line("retry: 3000") is None


def test_parse_progress_event():
    result = parse_sse_line('data: {"status":"indexing","progress":45}')
    assert result["status"] == "indexing"
    assert result["progress"] == 45


def test_parse_sources_event():
    line = (
        'data: {"type":"sources","sources":[{"doc_id":"uuid-1","page_refs":[5,6],"raw_pages":[]}]}'
    )
    result = parse_sse_line(line)
    assert result["type"] == "sources"
    assert len(result["sources"]) == 1
    assert result["sources"][0]["page_refs"] == [5, 6]


def test_invalid_json_returns_raw():
    result = parse_sse_line("data: not-valid-json")
    assert result is not None
    assert result["type"] == "raw"
