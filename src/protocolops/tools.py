from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from protocolops.config import Settings, load_settings
from protocolops.connectors.gsc import fetch_gsc, summarize_gsc
from protocolops.connectors.telegram import format_report_card, send_telegram
from protocolops.crawler.docs import crawl_docs, index_to_dict
from protocolops.crawler.sitemap import check_sitemap, load_sitemap
from protocolops.jobs.weekly import latest_run_dir, run_weekly
from protocolops.seo.analysis import analyze
from protocolops.seo.brief import render_brief
from protocolops.seo.drafts import pick_draft_targets, render_mdx

TOOL_NAMES = ("gsc_summary", "docs_index", "seo_brief", "draft_mdx", "send_report")


def gsc_summary(days: int = 28, settings: Settings | None = None) -> dict[str, Any]:
    """Summarize Google Search Console performance (mock or live)."""
    settings = settings or load_settings()
    snapshot = fetch_gsc(settings, days=days)
    payload = summarize_gsc(snapshot)
    payload["tool"] = "gsc_summary"
    return payload


def docs_index(settings: Settings | None = None) -> dict[str, Any]:
    """Crawl the configured docs folder or public docs site and return the index."""
    settings = settings or load_settings()
    index = crawl_docs(settings)
    payload = index_to_dict(index)
    payload["tool"] = "docs_index"
    return payload


def seo_brief(write: bool = False, settings: Settings | None = None) -> dict[str, Any]:
    """Build the weekly SEO brief from GSC + docs index. Optionally persist it."""
    settings = settings or load_settings()
    if write:
        artifacts = run_weekly(settings, telegram_dry_run=True)
        return {
            "tool": "seo_brief",
            "written": True,
            "brief_path": artifacts.brief_path,
            "draft_paths": artifacts.draft_paths,
            "run_id": artifacts.run_id,
            "markdown": Path(artifacts.brief_path).read_text(encoding="utf-8"),
        }
    snapshot = fetch_gsc(settings)
    index = crawl_docs(settings)
    sitemap = check_sitemap(index, load_sitemap(settings), settings)
    analysis = analyze(snapshot, index, settings)
    targets = pick_draft_targets(analysis, index, settings)
    markdown = render_brief(
        analysis,
        snapshot,
        index,
        sitemap,
        settings,
        draft_slugs=[spec.slug for spec in targets],
    )
    return {
        "tool": "seo_brief",
        "written": False,
        "run_id": None,
        "draft_slugs": [spec.slug for spec in targets],
        "drops": len(analysis.ranking_drops),
        "gaps": len(analysis.keyword_gaps),
        "markdown": markdown,
    }


def draft_mdx(query: str | None = None, write: bool = False, settings: Settings | None = None) -> dict[str, Any]:
    """Draft one MDX stub for a query, or the top keyword gap if query is omitted."""
    settings = settings or load_settings()
    snapshot = fetch_gsc(settings)
    index = crawl_docs(settings)
    analysis = analyze(snapshot, index, settings)
    targets = pick_draft_targets(analysis, index, settings)
    spec = None
    if query:
        from protocolops.seo.drafts import spec_for_query

        spec = spec_for_query(query, f"Manual draft requested for '{query}'.", index, settings)
    elif targets:
        spec = targets[0]
    if spec is None:
        return {"tool": "draft_mdx", "error": "No keyword gap to draft and no query provided."}

    markdown = render_mdx(spec, settings)
    path = None
    if write:
        dest = settings.out_dir() / "manual-drafts"
        dest.mkdir(parents=True, exist_ok=True)
        file = dest / f"{spec.slug}.mdx"
        file.write_text(markdown, encoding="utf-8")
        path = str(file)
    return {
        "tool": "draft_mdx",
        "slug": spec.slug,
        "title": spec.title,
        "target_query": spec.target_query,
        "path": path,
        "markdown": markdown,
    }


def send_report(dry_run: bool = True, settings: Settings | None = None) -> dict[str, Any]:
    """Send (or dry-run) the Telegram weekly report card. Default is dry-run."""
    settings = settings or load_settings()
    run_dir = latest_run_dir(settings.out_dir())
    if run_dir and (run_dir / "telegram-report.md").is_file():
        text = (run_dir / "telegram-report.md").read_text(encoding="utf-8")
    else:
        snapshot = fetch_gsc(settings)
        index = crawl_docs(settings)
        sitemap = check_sitemap(index, load_sitemap(settings), settings)
        analysis = analyze(snapshot, index, settings)
        targets = pick_draft_targets(analysis, index, settings)
        text = format_report_card(
            analysis,
            drafts=[spec.path for spec in targets],
            sitemap=sitemap,
            mock=snapshot.mock,
            brand=settings.brand,
        )
    result = send_telegram(text, settings, dry_run=dry_run)
    return {
        "tool": "send_report",
        **result.model_dump(),
    }


def dispatch(name: str, arguments: dict[str, Any] | None = None, settings: Settings | None = None) -> dict[str, Any]:
    arguments = dict(arguments or {})
    if settings is not None:
        arguments["settings"] = settings
    handlers = {
        "gsc_summary": gsc_summary,
        "docs_index": docs_index,
        "seo_brief": seo_brief,
        "draft_mdx": draft_mdx,
        "send_report": send_report,
    }
    if name not in handlers:
        raise KeyError(f"Unknown tool {name!r}. Expected one of {TOOL_NAMES}.")
    return handlers[name](**arguments)


def dump(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2, default=str)
