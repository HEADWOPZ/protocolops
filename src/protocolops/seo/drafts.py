from __future__ import annotations

from protocolops.config import Settings
from protocolops.models import Analysis, DocsIndex, DraftSpec
from protocolops.textutil import slugify


def pick_draft_targets(analysis: Analysis, index: DocsIndex, settings: Settings) -> list[DraftSpec]:
    existing = {page.slug for page in index.pages}
    existing.update(slugify(page.title) for page in index.pages)
    picked: list[DraftSpec] = []
    seen_slugs: set[str] = set()

    for gap in analysis.keyword_gaps:
        spec = spec_for_query(gap.query, gap.reason, index, settings)
        if spec.slug in existing or spec.slug in seen_slugs:
            continue
        picked.append(spec)
        seen_slugs.add(spec.slug)
        if len(picked) >= settings.draft_count:
            return picked

    for opp in analysis.opportunities:
        spec = spec_for_query(opp.query, opp.reason, index, settings)
        if spec.slug in existing or spec.slug in seen_slugs:
            continue
        picked.append(spec)
        seen_slugs.add(spec.slug)
        if len(picked) >= settings.draft_count:
            return picked

    for drop in analysis.ranking_drops:
        spec = spec_for_query(drop.query, f"Ranking drop +{drop.position_delta:.1f} positions.", index, settings)
        if spec.slug in existing or spec.slug in seen_slugs:
            continue
        picked.append(spec)
        seen_slugs.add(spec.slug)
        if len(picked) >= settings.draft_count:
            return picked

    return picked


def render_mdx(spec: DraftSpec, settings: Settings) -> str:
    keywords = ", ".join(spec.keywords)
    related = "\n".join(f"- [{slug}](/{slug})" for slug in spec.related_slugs) or "- Add internal links after review."
    return f"""---
title: {spec.title}
description: {spec.description}
slug: {spec.slug}
keywords:
{os_yaml_list(spec.keywords)}
status: draft
protocolops: true
target_query: {spec.target_query}
---

{{/* ProtocolOps draft — human review required before publish. Not financial advice. */}}

# {spec.title}

{spec.description}

This page is a **draft stub** produced by ProtocolOps for `{settings.brand}`. Replace every
placeholder with sourced protocol facts. Do not ship marketing claims Google will treat as
doorway copy.

## Why this page exists

Search demand for **{spec.target_query}** is not covered by the current docs index
({spec.reason}).

## Definition

> TODO: one sentence a wallet user can repeat. Name the asset, the wait, and the risk.

{_definition_prompt(spec, settings)}

## How it works

1. TODO: precondition (wallet connected, network, balance).
2. TODO: the action the user takes in the app or contract.
3. TODO: what they see while waiting (queue, epoch, challenge period).
4. TODO: success state and how to verify it on-chain.

```mdx
<Callout type="info">
  Confirm finality rules with protocol engineering before publishing timings.
</Callout>
```

## Limits and risks

- TODO: caps, pauses, oracle or sequencer assumptions.
- TODO: slashing / liquidation / failed-tx paths.
- This is not an offer to buy, stake, or use any token.

## Related docs

{related}

## SEO checklist (reviewer)

- [ ] Title ≤ 60 chars and matches the query intent
- [ ] Meta description is unique and honest
- [ ] H2s answer the query; no keyword stuffing
- [ ] At least two internal links to live docs
- [ ] No unverified APY, TVL, or audit claims
- [ ] Added to sitemap **after** merge

<!-- target keywords: {keywords} -->
"""


def spec_for_query(query: str, reason: str, index: DocsIndex, settings: Settings) -> DraftSpec:
    title = _title_case(query)
    if settings.brand.split()[0].lower() not in query.lower():
        title = f"{title} — {settings.brand}"
    slug = slugify(query)
    related = [page.slug for page in index.pages[:4]]
    keywords = [query] + [page.title.lower() for page in index.pages[:2]]
    return DraftSpec(
        slug=slug,
        title=title,
        description=f"Draft guide covering “{query}” for {settings.brand} docs. Review before publish.",
        target_query=query,
        keywords=keywords,
        related_slugs=related,
        path=f"drafts/{slug}.mdx",
        reason=reason,
    )


def _definition_prompt(spec: DraftSpec, settings: Settings) -> str:
    return (
        f"{settings.brand} should explain **{spec.target_query}** in operator language: "
        "what the user is waiting on, who can fail the action, and how to recover."
    )


def _title_case(query: str) -> str:
    small = {"a", "an", "the", "and", "or", "of", "for", "to", "in", "on", "vs"}
    words = query.split()
    out: list[str] = []
    for i, word in enumerate(words):
        if i > 0 and word.lower() in small:
            out.append(word.lower())
        else:
            out.append(word[:1].upper() + word[1:])
    return " ".join(out)


def os_yaml_list(items: list[str]) -> str:
    return "\n".join(f"  - {item}" for item in items) or "  - []"
