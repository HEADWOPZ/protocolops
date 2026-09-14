from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse

from protocolops.config import Settings, load_settings
from protocolops.jobs.weekly import latest_run_dir

STATIC_DIR = Path(__file__).resolve().parent / "static"


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()
    app = FastAPI(title="ProtocolOps desk", version="0.1.0")

    @app.get("/", response_class=HTMLResponse)
    def home() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/api/status")
    def status() -> JSONResponse:
        run_dir = latest_run_dir(settings.out_dir())
        if run_dir is None:
            return JSONResponse(
                {
                    "ok": False,
                    "brand": settings.brand,
                    "mock": settings.use_mock_gsc(),
                    "message": "No weekly run yet. Run protocolops run --weekly",
                }
            )
        run_json = run_dir / "run.json"
        payload = {
            "ok": True,
            "brand": settings.brand,
            "mock": settings.use_mock_gsc(),
            "run_dir": str(run_dir),
        }
        if run_json.is_file():
            import json

            payload.update(json.loads(run_json.read_text(encoding="utf-8")))
        brief = run_dir / "weekly-brief.md"
        payload["has_brief"] = brief.is_file()
        payload["drafts"] = sorted(p.name for p in (run_dir / "drafts").glob("*.mdx")) if (run_dir / "drafts").is_dir() else []
        payload["files"] = sorted(p.name for p in run_dir.iterdir() if p.is_file())
        return JSONResponse(payload)

    @app.get("/api/brief")
    def brief() -> JSONResponse:
        run_dir = latest_run_dir(settings.out_dir())
        if run_dir is None or not (run_dir / "weekly-brief.md").is_file():
            return JSONResponse({"ok": False, "markdown": ""}, status_code=404)
        return JSONResponse({"ok": True, "markdown": (run_dir / "weekly-brief.md").read_text(encoding="utf-8")})

    @app.get("/api/drafts/{slug}")
    def draft(slug: str) -> JSONResponse:
        run_dir = latest_run_dir(settings.out_dir())
        if run_dir is None:
            return JSONResponse({"ok": False, "error": "no run"}, status_code=404)
        path = run_dir / "drafts" / f"{slug}.mdx"
        if not path.is_file():
            path = run_dir / "drafts" / slug
        if not path.is_file():
            return JSONResponse({"ok": False, "error": "missing draft"}, status_code=404)
        return JSONResponse({"ok": True, "slug": slug, "markdown": path.read_text(encoding="utf-8")})

    @app.get("/api/report")
    def report() -> JSONResponse:
        run_dir = latest_run_dir(settings.out_dir())
        if run_dir is None or not (run_dir / "telegram-report.md").is_file():
            return JSONResponse({"ok": False, "text": ""}, status_code=404)
        return JSONResponse({"ok": True, "text": (run_dir / "telegram-report.md").read_text(encoding="utf-8")})

    return app
