from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from protocolops.config import Settings, load_settings
from protocolops.connectors.ga4 import fetch_ga4
from protocolops.connectors.gsc import fetch_gsc
from protocolops.connectors.telegram import format_report_card, send_telegram
from protocolops.crawler.docs import crawl_docs, index_to_dict
from protocolops.crawler.sitemap import check_sitemap, load_sitemap
from protocolops.models import WeeklyArtifacts
from protocolops.seo.analysis import analyze
from protocolops.seo.brief import render_brief
from protocolops.seo.drafts import pick_draft_targets, render_mdx


def run_weekly(settings: Settings | None = None, *, telegram_dry_run: bool = True) -> WeeklyArtifacts:
    settings = settings or load_settings()
    started = datetime.now(timezone.utc)
    run_id = started.strftime("%Y-%m-%d")
    out = settings.out_dir() / run_id
    drafts_dir = out / "drafts"
    drafts_dir.mkdir(parents=True, exist_ok=True)

    snapshot = fetch_gsc(settings)
    ga4 = fetch_ga4(settings)
    index = crawl_docs(settings)
    sitemap_urls = load_sitemap(settings)
    sitemap = check_sitemap(index, sitemap_urls, settings)
    analysis = analyze(snapshot, index, settings, ga4=ga4)
    targets = pick_draft_targets(analysis, index, settings)

    draft_paths: list[str] = []
    for spec in targets:
        text = render_mdx(spec, settings)
        dest = drafts_dir / f"{spec.slug}.mdx"
        dest.write_text(text, encoding="utf-8")
        spec.path = str(dest)
        draft_paths.append(str(dest))

    brief = render_brief(
        analysis,
        snapshot,
        index,
        sitemap,
        settings,
        draft_slugs=[spec.slug for spec in targets],
        ga4=ga4,
    )
    brief_path = out / "weekly-brief.md"
    brief_path.write_text(brief, encoding="utf-8")

    sitemap_path = out / "sitemap-report.json"
    sitemap_path.write_text(sitemap.model_dump_json(indent=2), encoding="utf-8")

    index_path = out / "docs-index.json"
    index_path.write_text(json.dumps(index_to_dict(index), indent=2), encoding="utf-8")

    pr_body = _suggested_pr(settings, run_id, targets, analysis.ranking_drops[:5])
    pr_path = out / "suggested-pr.md"
    pr_path.write_text(pr_body, encoding="utf-8")

    card = format_report_card(
        analysis,
        drafts=draft_paths,
        sitemap=sitemap,
        mock=snapshot.mock,
        brand=settings.brand,
    )
    report_path = out / "telegram-report.md"
    report_path.write_text(card + "\n", encoding="utf-8")
    telegram = send_telegram(card, settings, dry_run=telegram_dry_run)

    finished = datetime.now(timezone.utc)
    artifacts = WeeklyArtifacts(
        run_id=run_id,
        started_at=started,
        finished_at=finished,
        mock=snapshot.mock,
        output_dir=str(out),
        brief_path=str(brief_path),
        draft_paths=draft_paths,
        sitemap_path=str(sitemap_path),
        report_path=str(report_path),
        suggested_pr_path=str(pr_path),
        analysis=analysis,
        telegram_dry_run=telegram.dry_run,
    )

    run_path = out / "run.json"
    run_path.write_text(artifacts.model_dump_json(indent=2), encoding="utf-8")
    _write_latest_pointer(settings.out_dir(), artifacts)
    return artifacts


def latest_run_dir(output_dir: Path) -> Path | None:
    latest = output_dir / "latest.json"
    if latest.is_file():
        payload = json.loads(latest.read_text(encoding="utf-8"))
        path = Path(payload.get("output_dir") or "")
        if path.is_dir():
            return path
    dated = sorted(
        (p for p in output_dir.iterdir() if p.is_dir() and (p / "weekly-brief.md").is_file()),
        reverse=True,
    )
    return dated[0] if dated else None


def _write_latest_pointer(output_dir: Path, artifacts: WeeklyArtifacts) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "latest.json").write_text(
        json.dumps(
            {
                "run_id": artifacts.run_id,
                "output_dir": artifacts.output_dir,
                "brief_path": artifacts.brief_path,
                "draft_paths": artifacts.draft_paths,
                "mock": artifacts.mock,
                "finished_at": artifacts.finished_at.isoformat(),
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def _suggested_pr(settings: Settings, run_id: str, targets, drops) -> str:
    files = "\n".join(f"- `docs/{spec.slug}.mdx` (from draft `{spec.slug}.mdx`)" for spec in targets)
    drop_lines = "\n".join(f"- `{d.query}` dropped {d.position_prev:.1f} → {d.position:.1f}" for d in drops)
    return f"""# docs: ProtocolOps weekly pack {run_id}

**Do not auto-merge.** Review every draft for protocol accuracy before merging to the docs site.

## Summary

Weekly SEO run for {settings.brand}. Draft MDX pages target Search Console keyword gaps.
Ranking-drop URLs should be edited in place rather than duplicated.

## Draft files

{files or "- (no new drafts this week)"}

## Ranking drops to patch on existing pages

{drop_lines or "- none"}

## Reviewer checklist

- [ ] Facts checked with protocol engineering / legal
- [ ] No APY, TVL, or audit claims without a source
- [ ] Internal links resolve
- [ ] Frontmatter `status` flipped from `draft` to `published` only after edit
- [ ] Sitemap updated after merge
- [ ] Search Console URL inspection requested post-deploy

## Out of scope

Link acquisition, traffic generation, and unattended merges are not part of this PR.
"""
