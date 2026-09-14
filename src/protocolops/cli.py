from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer

from protocolops import __version__
from protocolops.config import load_settings

app = typer.Typer(
    name="protocolops",
    help="DeFi docs SEO & content agent — weekly briefs, MDX drafts, MCP tools.",
    no_args_is_help=True,
    add_completion=False,
)


@app.callback()
def _root() -> None:
    """ProtocolOps CLI."""


@app.command("run")
def run_cmd(
    weekly: bool = typer.Option(False, "--weekly", help="Ship the weekly SEO pack (brief + draft MDX)."),
    live_telegram: bool = typer.Option(
        False, "--live-telegram", help="Actually POST to Telegram (requires token + chat id)."
    ),
    output_dir: Optional[Path] = typer.Option(None, "--output-dir", help="Override output directory."),
) -> None:
    """Run ProtocolOps. Use --weekly for the full mock-or-live job."""
    if not weekly:
        typer.echo("Nothing to do. Pass --weekly to generate the SEO pack.")
        raise typer.Exit(code=2)
    settings = load_settings()
    if output_dir is not None:
        settings = settings.model_copy(update={"output_dir": str(output_dir)})
    from protocolops.jobs.weekly import run_weekly

    artifacts = run_weekly(settings, telegram_dry_run=not live_telegram)
    typer.echo(f"ProtocolOps weekly run {artifacts.run_id} ({'mock' if artifacts.mock else 'live'})")
    typer.echo(f"  brief   {artifacts.brief_path}")
    for path in artifacts.draft_paths:
        typer.echo(f"  draft   {path}")
    typer.echo(f"  sitemap {artifacts.sitemap_path}")
    typer.echo(f"  report  {artifacts.report_path}")
    typer.echo(f"  pr      {artifacts.suggested_pr_path}")
    typer.echo(f"  telegram dry-run={artifacts.telegram_dry_run}")


@app.command("crawl")
def crawl_cmd() -> None:
    """Index local or remote docs and print a compact listing."""
    from protocolops.crawler.docs import crawl_docs

    settings = load_settings()
    index = crawl_docs(settings)
    typer.echo(f"{len(index.pages)} pages from {index.source}")
    for page in index.pages:
        heads = ", ".join(h.text for h in page.headings[:4])
        typer.echo(f"  /{page.slug:40} {page.title}  [{heads}]")


@app.command("gsc-summary")
def gsc_summary_cmd(days: int = typer.Option(28, "--days")) -> None:
    """Print a Search Console summary (fixture data unless credentials + mock=false)."""
    from protocolops.tools import dump, gsc_summary

    typer.echo(dump(gsc_summary(days=days)))


@app.command("auth")
def auth_cmd() -> None:
    """Run the Search Console installed-app OAuth flow and save a refresh token."""
    from protocolops.connectors.gsc import run_oauth_flow

    settings = load_settings()
    path = run_oauth_flow(settings)
    typer.echo(f"Saved token to {path}")
    typer.echo("Add the Google account as a Search Console user on the property if you have not already.")


@app.command("desk")
def desk_cmd(
    host: Optional[str] = typer.Option(None, "--host"),
    port: Optional[int] = typer.Option(None, "--port"),
) -> None:
    """Start the dark status desk (last brief + drafts)."""
    import uvicorn

    from protocolops.desk.app import create_app

    settings = load_settings()
    bind_host = host or settings.desk_host
    bind_port = port or settings.desk_port
    typer.echo(f"ProtocolOps desk http://{bind_host}:{bind_port}")
    uvicorn.run(create_app(settings), host=bind_host, port=bind_port, log_level="info")


@app.command("mcp")
def mcp_cmd() -> None:
    """Start the MCP server on stdio."""
    from protocolops.mcp_server import run_stdio

    run_stdio()


@app.command("version")
def version_cmd() -> None:
    typer.echo(__version__)


@app.command("status")
def status_cmd() -> None:
    """Print the latest weekly run pointer as JSON."""
    settings = load_settings()
    latest = settings.out_dir() / "latest.json"
    if not latest.is_file():
        typer.echo(json.dumps({"ok": False, "error": "No weekly run yet. Run: protocolops run --weekly"}))
        raise typer.Exit(code=1)
    typer.echo(latest.read_text(encoding="utf-8"))
