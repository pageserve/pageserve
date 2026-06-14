from __future__ import annotations

import json
import os
import sys

import click


@click.group()
@click.version_option(package_name="pageserve")
@click.option("--base-url", envvar="PAGESERVE_URL", default=None)
@click.option("--public-key", envvar="PAGESERVE_PUBLIC_KEY", default=None)
@click.option("--secret-key", envvar="PAGESERVE_SECRET_KEY", default=None)
@click.pass_context
def cli(ctx, base_url, public_key, secret_key):
    """pageserve — CLI cho PageIndex Self-Host Service."""
    ctx.ensure_object(dict)
    ctx.obj["base_url"] = base_url
    ctx.obj["public_key"] = public_key
    ctx.obj["secret_key"] = secret_key


def _make_client(ctx):
    """Tạo client từ context. Raise nếu thiếu credentials."""
    from pageserve import PageServeClient

    base_url = ctx.obj.get("base_url")
    public_key = ctx.obj.get("public_key")
    secret_key = ctx.obj.get("secret_key")

    missing = []
    if not base_url:
        missing.append("--base-url / PAGESERVE_URL")
    if not public_key:
        missing.append("--public-key / PAGESERVE_PUBLIC_KEY")
    if not secret_key:
        missing.append("--secret-key / PAGESERVE_SECRET_KEY")
    if missing:
        raise click.UsageError("Thiếu credentials:\n" + "\n".join(f"  {m}" for m in missing))

    return PageServeClient(base_url=base_url, public_key=public_key, secret_key=secret_key)


@cli.command()
@click.option(
    "--transport",
    default="stdio",
    type=click.Choice(["stdio", "sse", "streamable-http"]),
    help="MCP transport protocol",
)
@click.option("--host", default="127.0.0.1", help="Host cho SSE/streamable-http transport")
@click.option("--port", default=3000, help="Port cho SSE/streamable-http transport")
@click.option("--name", default="pageindex", help="Tên MCP server")
@click.pass_context
def mcp(ctx, transport, host, port, name):
    """Chạy MCP server expose PageIndex tools cho agent frameworks."""
    from pageserve.mcp import create_mcp_server

    base_url = ctx.obj.get("base_url") or os.environ.get("PAGESERVE_URL", "")
    public_key = ctx.obj.get("public_key") or os.environ.get("PAGESERVE_PUBLIC_KEY", "")
    secret_key = ctx.obj.get("secret_key") or os.environ.get("PAGESERVE_SECRET_KEY", "")

    # host/port phải set lúc khởi tạo FastMCP — run() không nhận tham số port.
    server = create_mcp_server(
        base_url=base_url,
        public_key=public_key,
        secret_key=secret_key,
        name=name,
        host=host,
        port=port,
    )

    if transport == "stdio":
        click.echo(f"PageServe MCP [stdio] → {base_url}", err=True)
        server.run(transport="stdio")
    else:
        click.echo(
            f"PageServe MCP [{transport}] listening on http://{host}:{port}  → {base_url}",
            err=True,
        )
        server.run(transport=transport)


@cli.command("list")
@click.option(
    "--status",
    default="completed",
    type=click.Choice(["completed", "pending", "indexing", "failed", "all"]),
)
@click.option("--json", "as_json", is_flag=True, help="Output raw JSON")
@click.pass_context
def list_docs(ctx, status, as_json):
    """List tất cả documents trong project."""
    client = _make_client(ctx)
    docs = client.list_documents(status=None if status == "all" else status)

    if as_json:
        click.echo(
            json.dumps([d.model_dump() for d in docs], ensure_ascii=False, indent=2, default=str)
        )
        return

    if not docs:
        click.echo("Không có document nào.")
        return

    # Table output
    click.echo(f"{'ID':<12}  {'Tên':<45}  {'Trang':>5}  {'Status':<12}  {'Mô tả'}")
    click.echo("─" * 100)
    for d in docs:
        doc_id_short = d.doc_id[:8] + "..."
        name_short = d.name[:43] + ".." if len(d.name) > 45 else d.name
        desc_short = (d.description or "")[:30]
        status_icon = {"completed": "✅", "indexing": "⏳", "pending": "⏸", "failed": "❌"}.get(
            d.status, "?"
        )
        click.echo(
            f"{doc_id_short:<12}  {name_short:<45}  {d.page_count or '?':>5}  "
            f"{status_icon} {d.status:<10}  {desc_short}"
        )


@cli.command()
@click.argument("doc_id")
@click.argument("question")
@click.option("--stream", is_flag=True, help="Streaming output")
@click.option("--json", "as_json", is_flag=True, help="Output raw JSON")
@click.pass_context
def query(ctx, doc_id, question, stream, as_json):
    """Query một document.

    \b
    Examples:
        pageserve query uuid-xxx "thử việc quy định thế nào?"
        pageserve query uuid-xxx "điều 25 là gì?" --stream
    """
    client = _make_client(ctx)

    if stream:
        # Streaming output
        for event in client.query_stream(doc_id, question):
            if event.type == "tool_start":
                click.echo(f"\n[🔍 {event.name}...]", nl=False, err=True)
            elif event.type == "tool_done":
                elapsed = f" {event.elapsed:.1f}s" if event.elapsed else ""
                click.echo(f" ✓{elapsed}", err=True)
            elif event.type == "token":
                click.echo(event.content or "", nl=False)
            elif event.type == "sources":
                click.echo("\n\nNguồn:", err=True)
                for src in event.sources or []:
                    click.echo(f"  📄 {src.citation}", err=True)
            elif event.type == "done":
                click.echo()
                break
            elif event.type == "error":
                click.echo(f"\n❌ {event.message}", err=True)
                sys.exit(1)
    else:
        result = client.query(doc_id, question)
        if as_json:
            click.echo(json.dumps(result.model_dump(), ensure_ascii=False, indent=2, default=str))
        else:
            click.echo(f"\n{result.answer}\n")
            click.echo(f"Nguồn: {result.citation}", err=True)
            if result.elapsed_ms:
                click.echo(f"Thời gian: {result.elapsed_ms}ms", err=True)


@cli.command()
@click.argument("doc_id")
@click.argument("question")
@click.option(
    "--docs",
    default=None,
    help="Retrieve nhiều doc cùng lúc (comma-separated). Bỏ qua nếu chỉ 1 doc_id.",
)
@click.option("--json", "as_json", is_flag=True, help="Output raw JSON")
@click.pass_context
def retrieve(ctx, doc_id, question, docs, as_json):
    """Lấy nội dung gốc các section liên quan (KHÔNG synthesize answer).

    Rẻ hơn query — chỉ 1 LLM call/doc để điều hướng tree.

    \b
    Examples:
        pageserve retrieve uuid-xxx "thử việc quy định thế nào?"
        pageserve retrieve _ "so sánh" --docs uuid-a,uuid-b
    """
    client = _make_client(ctx)
    target: str | list[str] = (
        [d.strip() for d in docs.split(",")] if docs else doc_id
    )
    result = client.retrieve(target, question)

    if as_json:
        click.echo(json.dumps(result.model_dump(), ensure_ascii=False, indent=2, default=str))
        return

    if not result.results:
        click.echo("Không tìm thấy section liên quan.")
        return

    for r in result.results:
        click.echo(f"\n📄 {r.doc_name or r.doc_id}")
        for s in r.sections:
            rng = f" (tr.{s.page_range})" if s.page_range else ""
            click.echo(f"\n  ── {s.title}{rng} ──")
            click.echo(s.text)
    if result.elapsed_ms:
        click.echo(f"\nThời gian: {result.elapsed_ms}ms", err=True)


@cli.command()
@click.argument("file_path", type=click.Path(exists=True))
@click.option("--wait", is_flag=True, help="Chờ đến khi index xong")
@click.option("--watch", is_flag=True, help="Show progress stream khi đang index")
@click.pass_context
def upload(ctx, file_path, wait, watch):
    """Upload PDF và bắt đầu index.

    \b
    Examples:
        pageserve upload ./report.pdf
        pageserve upload ./report.pdf --wait
        pageserve upload ./report.pdf --watch
    """
    client = _make_client(ctx)

    click.echo(f"Đang upload {file_path}...", err=True)
    result = client.upload(file_path, wait=False)

    click.echo(f"✅ Đã upload: {result.doc_id}")
    click.echo(f"   Status: {result.status}")
    if result.queue_position:
        click.echo(f"   Vị trí trong queue: {result.queue_position}")

    if watch or wait:
        click.echo("Đang theo dõi tiến trình...", err=True)
        for progress in client.watch_progress(result.doc_id):
            if progress.status == "indexing":
                bar_len = 30
                filled = int(bar_len * progress.progress / 100)
                bar = "█" * filled + "░" * (bar_len - filled)
                click.echo(f"\r  [{bar}] {progress.progress}%", nl=False, err=True)
            elif progress.status == "completed":
                click.echo("\r  ✅ Index hoàn tất!                    ", err=True)
                break
            elif progress.status == "failed":
                click.echo(f"\r  ❌ Index thất bại: {progress.error}", err=True)
                sys.exit(1)


@cli.command()
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def health(ctx, as_json):
    """Kiểm tra trạng thái service."""
    client = _make_client(ctx)
    h = client.health()

    if as_json:
        click.echo(json.dumps(h.model_dump(), ensure_ascii=False, indent=2, default=str))
        return

    status_icon = "✅" if h.is_healthy else "⚠️"
    click.echo(f"{status_icon} Status: {h.status}")
    if h.version:
        click.echo(f"   Version: {h.version}")

    if h.checks:
        click.echo("\nServices:")
        for name, check in h.checks.items():
            icon = "✅" if check.status == "ok" else "❌"
            latency = f" ({check.latency_ms}ms)" if check.latency_ms else ""
            click.echo(f"  {icon} {name}{latency}")

    if h.queue:
        click.echo(f"\nQueue: {h.queue.pending} pending")

    if h.system:
        avail = f"{h.system.ram_available_gb:.1f}"
        total = f"{h.system.ram_total_gb:.1f}"
        click.echo(f"\nRAM: {avail}GB available / {total}GB total")
        if h.system.max_file_mb:
            click.echo(f"Max file size: {h.system.max_file_mb}MB")


@cli.group()
@click.pass_context
def keys(ctx):
    """Quản lý API keys."""
    pass


@keys.command("list")
@click.option("--json", "as_json", is_flag=True)
@click.pass_context
def keys_list(ctx, as_json):
    """List tất cả API keys."""
    client = _make_client(ctx)
    keylist = client.list_keys()

    if as_json:
        click.echo(
            json.dumps([k.model_dump() for k in keylist], ensure_ascii=False, indent=2, default=str)
        )
        return

    if not keylist:
        click.echo("Không có API key nào.")
        return

    header = f"{'Tên':<25}  {'Public Key (prefix)':<25}  {'Type':<6}  {'Requests':>10}"
    click.echo(header)
    click.echo("─" * 90)
    for k in keylist:
        last_used = str(k.last_used_at)[:10] if k.last_used_at else "Chưa dùng"
        status = "" if k.is_active else " [revoked]"
        click.echo(
            f"{k.name[:25]:<25}  {k.secret_prefix:<25}  {k.key_type:<6}  "
            f"{k.request_count:>10}  {last_used}{status}"
        )


@keys.command("create")
@click.argument("name")
@click.option("--type", "key_type", default="live", type=click.Choice(["live", "test"]))
@click.option("--scopes", default="read,write")
@click.option("--expires", default=None, help="ISO 8601 datetime")
@click.pass_context
def keys_create(ctx, name, key_type, scopes, expires):
    """Tạo API key mới.

    \b
    Examples:
        pageserve keys create "Production"
        pageserve keys create "Read-only CI" --scopes read
        pageserve keys create "Temp" --expires 2027-01-01T00:00:00Z
    """
    client = _make_client(ctx)
    scopes = [s.strip() for s in scopes.split(",")]
    new_key = client.create_key(name=name, key_type=key_type, scopes=scopes, expires_at=expires)

    click.echo(f"\n✅ Key đã tạo: {name}")
    click.echo("\n⚠️  Lưu thông tin sau — KHÔNG THỂ xem lại secret_key!\n")
    click.echo(f"Public Key:  {new_key.public_key}")
    click.echo(f"Secret Key:  {new_key.secret_key}")
    click.echo("\nDùng trong code:")
    click.echo("    client = PageServeClient(")
    click.echo(f'        base_url   = "{ctx.obj.get("base_url", "https://...")}",')
    click.echo(f'        public_key = "{new_key.public_key}",')
    click.echo(f'        secret_key = "{new_key.secret_key}",')
    click.echo("    )")


@keys.command("revoke")
@click.argument("key_id")
@click.option("--yes", is_flag=True, help="Bỏ qua confirm")
@click.pass_context
def keys_revoke(ctx, key_id, yes):
    """Revoke API key — vô hiệu hóa ngay lập tức."""
    if not yes:
        click.confirm(f"Revoke key {key_id}?", abort=True)
    client = _make_client(ctx)
    client.revoke_key(key_id)
    click.echo(f"✅ Key {key_id} đã bị revoke.")
