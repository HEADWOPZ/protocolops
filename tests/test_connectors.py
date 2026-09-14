from __future__ import annotations

from protocolops.connectors.ga4 import fetch_ga4
from protocolops.connectors.gsc import fetch_gsc, summarize_gsc
from protocolops.connectors.telegram import format_report_card, send_telegram
from protocolops.crawler.docs import crawl_docs
from protocolops.seo.analysis import analyze


def test_mock_gsc_loads_fixture_rows(settings):
    snapshot = fetch_gsc(settings)
    assert snapshot.mock is True
    assert snapshot.site_url.endswith("docs.helios.example/")
    queries = {row.query for row in snapshot.rows}
    assert "helios withdrawal queue time" in queries
    assert "helios stake hls" in queries
    summary = summarize_gsc(snapshot)
    assert summary["totals"]["impressions"] > 1000
    assert summary["mock"] is True


def test_ga4_disabled_by_default(settings):
    assert fetch_ga4(settings) is None


def test_ga4_stub_when_enabled(settings):
    settings = settings.model_copy(update={"ga4_enabled": True})
    snap = fetch_ga4(settings)
    assert snap is not None
    assert snap.enabled is True
    assert snap.sessions > 0
    assert "stub" in snap.note.lower() or "fixture" in snap.note.lower()


def test_telegram_dry_run_without_token(settings):
    snapshot = fetch_gsc(settings)
    index = crawl_docs(settings)
    analysis = analyze(snapshot, index, settings)
    card = format_report_card(analysis, drafts=["drafts/demo.mdx"], mock=True)
    result = send_telegram(card, settings, dry_run=True)
    assert result.dry_run is True
    assert result.ok is True
    assert "ProtocolOps" in result.text
    assert "Human review" in result.text
