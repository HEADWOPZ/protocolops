from __future__ import annotations

from datetime import UTC, datetime

from protocolops.config import Settings
from protocolops.models import Analysis, DocsIndex, GA4Snapshot, GSCSnapshot, SitemapReport


def render_brief(
    analysis: Analysis,
    snapshot: GSCSnapshot,
    index: DocsIndex,
    sitemap: SitemapReport,
    settings: Settings,
    *,
    draft_slugs: list[str],
    ga4: GA4Snapshot | None = None,
) -> str:
    generated = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    totals = analysis.totals
    mode = "MOCK (fixtures)" if snapshot.mock else "LIVE Search Console"
    lines = [
        f"# Weekly SEO brief — {analysis.brand}",
        "",
        f"- Generated: {generated}",
        f"- Property: `{analysis.site_url}`",
        f"- Window: {snapshot.start_date.isoformat()} → {snapshot.end_date.isoformat()}",
        f"- Compare: {snapshot.compare_start} → {snapshot.compare_end}",
        f"- Source: {mode}",
        f"- Docs indexed: {len(index.pages)} pages from `{index.source}`",
        "",
        "> Drafts only. A human must review copy, claims, and any PR before merge. "
        "ProtocolOps does not buy links, generate traffic, or publish automatically.",
        "",
        "## Performance",
        "",
        "| Clicks | Impressions | Avg position | Avg CTR |",
        "| ---: | ---: | ---: | ---: |",
        f"| {int(totals.get('clicks', 0))} | {int(totals.get('impressions', 0))} | "
        f"{totals.get('avg_position', 0)} | {totals.get('avg_ctr', 0):.2%} |",
        "",
    ]
    if snapshot.notes:
        lines.append("Notes:")
        lines.extend(f"- {note}" for note in snapshot.notes)
        lines.append("")

    if ga4:
        lines.extend(
            [
                "## GA4 (stub)",
                "",
                f"- Enabled: {ga4.enabled} · mock: {ga4.mock} · property: `{ga4.property_id or 'n/a'}`",
                f"- Sessions: {ga4.sessions} · engaged: {ga4.engaged_sessions} · views: {ga4.views}",
                f"- {ga4.note}",
                "",
            ]
        )
        if ga4.top_pages:
            lines.append("| Page | Views |")
            lines.append("| --- | ---: |")
            for page in ga4.top_pages[:6]:
                lines.append(f"| {page.get('path', '')} | {page.get('views', 0)} |")
            lines.append("")

    lines.extend(["## Ranking drops", ""])
    if analysis.ranking_drops:
        lines.append("| Query | Page | Prev pos | Pos | Δ | Impr | Clicks Δ |")
        lines.append("| --- | --- | ---: | ---: | ---: | ---: | ---: |")
        for drop in analysis.ranking_drops[:12]:
            click_delta = "—" if drop.clicks_delta is None else str(drop.clicks_delta)
            lines.append(
                f"| {drop.query} | `{_short(drop.page)}` | {drop.position_prev:.1f} | "
                f"{drop.position:.1f} | +{drop.position_delta:.1f} | {drop.impressions} | {click_delta} |"
            )
        lines.extend(
            [
                "",
                "Refresh the existing page first: retitle to the query, add a definition paragraph, "
                "and tighten the H2s that Google is already ranking. Do not spawn a duplicate URL.",
                "",
            ]
        )
    else:
        lines.append("No ranking drops crossed the +3 position / 40 impression threshold.")
        lines.append("")

    lines.extend(["## Keyword gaps", ""])
    if analysis.keyword_gaps:
        lines.append("| Query | Impr | CTR | Pos | Best existing doc | Score |")
        lines.append("| --- | ---: | ---: | ---: | --- | ---: |")
        for gap in analysis.keyword_gaps[:15]:
            lines.append(
                f"| {gap.query} | {gap.impressions} | {gap.ctr:.1%} | {gap.position:.1f} | "
                f"{gap.best_doc or '—'} | {gap.match_score:.2f} |"
            )
        lines.extend(["", "These queries have demand and no close doc. Draft MDX stubs target the top gaps.", ""])
        for gap in analysis.keyword_gaps[:5]:
            lines.append(f"### {gap.query}")
            lines.append("")
            lines.append(gap.reason)
            lines.append("")
            lines.append("Recommended outline")
            lines.append("")
            lines.append("1. One-sentence definition a wallet user can trust.")
            lines.append("2. Step-by-step (or state machine) with expected waits and failure modes.")
            lines.append("3. Limits, risks, and what the protocol will *not* do.")
            lines.append("4. Internal links to the closest existing guides.")
            lines.append("")
    else:
        lines.append("No keyword gaps crossed the coverage threshold.")
        lines.append("")

    lines.extend(["## CTR / snippet opportunities", ""])
    if analysis.opportunities:
        lines.append("| Query | Impr | CTR | Pos | Why |")
        lines.append("| --- | ---: | ---: | ---: | --- |")
        for opp in analysis.opportunities[:10]:
            lines.append(
                f"| {opp.query} | {opp.impressions} | {opp.ctr:.1%} | {opp.position:.1f} | {opp.reason} |"
            )
        lines.append("")
    else:
        lines.append("No high-impression low-CTR queries this window.")
        lines.append("")

    lines.extend(
        [
            "## Sitemap / index check",
            "",
            f"- Sitemap URLs: {len(sitemap.sitemap_urls)}",
            f"- Crawled slugs: {len(sitemap.indexed_slugs)}",
            f"- In docs, not sitemap: {len(sitemap.in_docs_not_sitemap)}",
            f"- In sitemap, not docs: {len(sitemap.in_sitemap_not_docs)}",
            "",
        ]
    )
    for note in sitemap.notes:
        lines.append(f"- {note}")
    if sitemap.in_docs_not_sitemap:
        lines.append("")
        lines.append("Add to sitemap:")
        lines.extend(f"- `{url}`" for url in sitemap.in_docs_not_sitemap[:12])
    if sitemap.in_sitemap_not_docs:
        lines.append("")
        lines.append("Sitemap orphans (404 risk or uncrawlable source):")
        lines.extend(f"- `{url}`" for url in sitemap.in_sitemap_not_docs[:12])
    lines.append("")

    lines.extend(
        [
            "## Drafts this week",
            "",
        ]
    )
    if draft_slugs:
        lines.extend(f"- `{slug}.mdx` (status: draft — do not merge unreviewed)" for slug in draft_slugs)
    else:
        lines.append("- None — analysis found no gap large enough to justify a new URL.")
    lines.extend(
        [
            "",
            "## Suggested next actions",
            "",
            "1. Review ranking-drop pages before writing net-new URLs.",
            "2. Edit the draft MDX files in this week's output folder; keep protocol facts sourced.",
            "3. Open a human-reviewed PR using `suggested-pr.md`.",
            "4. After publish, request indexing in Search Console for the new slugs only.",
            "",
            "## Out of scope (v1)",
            "",
            "- Multi-client content calendars",
            "- Link buying or paid placements",
            "- Fake traffic, cloaking, or doorway pages",
            "- Auto-merge to docs without review",
            "",
            f"_ProtocolOps {settings.brand} · operator Kevin Lance Murray_",
            "",
        ]
    )
    return "\n".join(lines)


def _short(url: str) -> str:
    return url.replace("https://", "").replace("http://", "")
