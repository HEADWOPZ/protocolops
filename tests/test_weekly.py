from __future__ import annotations

from pathlib import Path

from protocolops.jobs.weekly import latest_run_dir, run_weekly


def test_mock_weekly_run_writes_brief_and_drafts(settings):
    artifacts = run_weekly(settings, telegram_dry_run=True)
    out = Path(artifacts.output_dir)
    assert artifacts.mock is True
    assert artifacts.telegram_dry_run is True
    assert Path(artifacts.brief_path).is_file()
    brief = Path(artifacts.brief_path).read_text(encoding="utf-8")
    assert brief.startswith("# Weekly SEO brief")
    assert "Keyword gaps" in brief
    assert "Ranking drops" in brief
    assert 2 <= len(artifacts.draft_paths) <= 3
    for path in artifacts.draft_paths:
        text = Path(path).read_text(encoding="utf-8")
        assert text.startswith("---")
        assert "status: draft" in text
        assert path.endswith(".mdx")
    assert Path(artifacts.sitemap_path).is_file()
    assert Path(artifacts.report_path).is_file()
    assert Path(artifacts.suggested_pr_path).is_file()
    pr = Path(artifacts.suggested_pr_path).read_text(encoding="utf-8")
    assert "Do not auto-merge" in pr
    assert latest_run_dir(Path(settings.output_dir)) == out
    assert "Human review" in Path(artifacts.report_path).read_text(encoding="utf-8")
