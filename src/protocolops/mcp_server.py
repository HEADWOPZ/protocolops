"""MCP server exposing ProtocolOps tools.

Compatible with MCP Python SDK v1 (FastMCP) and v2 (MCPServer). Tool logic
lives in `protocolops.tools` so tests do not need a live stdio session.
"""

from __future__ import annotations

from typing import Any

from protocolops.tools import (
    TOOL_NAMES,
    docs_index,
    draft_mdx,
    dump,
    gsc_summary,
    send_report,
    seo_brief,
)

TOOL_SPECS: list[dict[str, Any]] = [
    {
        "name": "gsc_summary",
        "description": "Summarize Google Search Console performance for the configured property (mock-safe).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "days": {"type": "integer", "description": "Lookback window in days.", "default": 28},
            },
        },
    },
    {
        "name": "docs_index",
        "description": "Crawl the local docs folder or public docs site and return titles, headings, and slugs.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "seo_brief",
        "description": "Build a weekly SEO brief from ranking drops and keyword gaps. Set write=true to persist files.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "write": {
                    "type": "boolean",
                    "default": False,
                    "description": "Persist brief + drafts under output/.",
                },
            },
        },
    },
    {
        "name": "draft_mdx",
        "description": "Draft an MDX docs stub for a query, or the top keyword gap if query is omitted.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Target search query."},
                "write": {"type": "boolean", "default": False},
            },
        },
    },
    {
        "name": "send_report",
        "description": "Send the Telegram weekly report card. Defaults to dry-run and is safe without a bot token.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "dry_run": {"type": "boolean", "default": True},
            },
        },
    },
]


def list_tool_names() -> list[str]:
    return list(TOOL_NAMES)


def create_mcp_server() -> Any:
    server = _make_server("protocolops")

    @server.tool(name="gsc_summary")
    def _gsc_summary(days: int = 28) -> str:
        """Summarize Google Search Console performance for the configured property (mock-safe)."""
        return dump(gsc_summary(days=days))

    @server.tool(name="docs_index")
    def _docs_index() -> str:
        """Crawl the local docs folder or public docs site and return titles, headings, and slugs."""
        return dump(docs_index())

    @server.tool(name="seo_brief")
    def _seo_brief(write: bool = False) -> str:
        """Build a weekly SEO brief from ranking drops and keyword gaps."""
        return dump(seo_brief(write=write))

    @server.tool(name="draft_mdx")
    def _draft_mdx(query: str | None = None, write: bool = False) -> str:
        """Draft an MDX docs stub for a query or the top keyword gap."""
        return dump(draft_mdx(query=query, write=write))

    @server.tool(name="send_report")
    def _send_report(dry_run: bool = True) -> str:
        """Send the Telegram weekly report card. Defaults to dry-run."""
        return dump(send_report(dry_run=dry_run))

    return server


def _make_server(name: str) -> Any:
    try:
        from mcp.server import MCPServer

        return MCPServer(name)
    except Exception:
        from mcp.server.fastmcp import FastMCP

        return FastMCP(name)


def run_stdio() -> None:
    server = create_mcp_server()
    runner = getattr(server, "run", None)
    if callable(runner):
        try:
            runner(transport="stdio")
            return
        except TypeError:
            runner()
            return
    raise RuntimeError("Installed MCP SDK does not expose a stdio run() on the server object.")


if __name__ == "__main__":
    run_stdio()
