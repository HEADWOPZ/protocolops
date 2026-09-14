from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from protocolops.cli import app
from protocolops.desk.app import create_app

runner = CliRunner()


def test_cli_weekly(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("PROTOCOLOPS_MOCK", "true")
    monkeypatch.setenv("PROTOCOLOPS_OUTPUT_DIR", str(tmp_path / "output"))
    monkeypatch.setenv("PROTOCOLOPS_DOCS_PATH", str(Path(__file__).resolve().parents[1] / "fixtures" / "docs"))
    monkeypatch.setenv("PROTOCOLOPS_FIXTURES_DIR", str(Path(__file__).resolve().parents[1] / "fixtures"))
    result = runner.invoke(app, ["run", "--weekly"])
    assert result.exit_code == 0, result.output
    assert "weekly-brief.md" in result.output
    assert "draft" in result.output.lower()
    assert any(tmp_path.joinpath("output").rglob("*.mdx"))


def test_cli_version():
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert result.output.strip()


def test_desk_status_before_and_after_run(settings):
    from fastapi.testclient import TestClient

    from protocolops.jobs.weekly import run_weekly

    app_ = create_app(settings)
    client = TestClient(app_)
    empty = client.get("/api/status").json()
    assert empty["ok"] is False
    run_weekly(settings, telegram_dry_run=True)
    status = client.get("/api/status").json()
    assert status["ok"] is True
    assert status["drafts"]
    brief = client.get("/api/brief").json()
    assert brief["ok"] is True
    home = client.get("/")
    assert home.status_code == 200
    assert "ProtocolOps" in home.text


def test_run_without_weekly_flag():
    result = runner.invoke(app, ["run"])
    assert result.exit_code == 2
