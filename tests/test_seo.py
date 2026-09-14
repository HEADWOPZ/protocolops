from __future__ import annotations

from protocolops.connectors.gsc import fetch_gsc
from protocolops.crawler.docs import crawl_docs
from protocolops.seo.analysis import analyze
from protocolops.seo.drafts import pick_draft_targets, render_mdx


def test_ranking_drops_and_keyword_gaps(settings):
    snapshot = fetch_gsc(settings)
    index = crawl_docs(settings)
    analysis = analyze(snapshot, index, settings)

    drop_queries = {item.query for item in analysis.ranking_drops}
    assert "helios stake hls" in drop_queries
    assert "helios connect metamask" in drop_queries
    assert "helios unstake period" in drop_queries

    gap_queries = {item.query for item in analysis.keyword_gaps}
    assert "helios withdrawal queue time" in gap_queries
    assert "helios restaking slashing" in gap_queries
    assert "helios walletconnect error 4001" in gap_queries
    assert "helios getting started" not in gap_queries
    assert "helios connect wallet" not in gap_queries


def test_draft_targets_cover_gaps(settings):
    snapshot = fetch_gsc(settings)
    index = crawl_docs(settings)
    analysis = analyze(snapshot, index, settings)
    targets = pick_draft_targets(analysis, index, settings)
    assert 2 <= len(targets) <= 3
    slugs = {spec.slug for spec in targets}
    assert "helios-withdrawal-queue-time" in slugs
    mdx = render_mdx(targets[0], settings)
    assert mdx.startswith("---")
    assert "status: draft" in mdx
    assert "Human review" in mdx or "human review" in mdx.lower()
    assert targets[0].target_query in mdx
