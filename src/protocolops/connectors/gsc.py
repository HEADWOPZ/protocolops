from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from protocolops.config import Settings
from protocolops.models import GSCSnapshot, QueryRow

GSC_SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]
SEARCHCONSOLE_DISCOVERY = "https://searchconsole.googleapis.com/$discovery/rest?version=v1"


def fetch_gsc(settings: Settings, *, days: int = 28) -> GSCSnapshot:
    if settings.use_mock_gsc():
        return load_mock_gsc(settings, days=days)
    try:
        return fetch_live_gsc(settings, days=days)
    except Exception as exc:  # noqa: BLE001 — fall back so weekly job still ships
        snapshot = load_mock_gsc(settings, days=days)
        snapshot.notes.append(f"Live GSC failed ({exc}); served mock fixture instead.")
        return snapshot


def load_mock_gsc(settings: Settings, *, days: int = 28) -> GSCSnapshot:
    path = settings.fixture_dir() / "gsc" / "search_analytics.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    end = date.fromisoformat(payload.get("end_date") or date.today().isoformat())
    start = date.fromisoformat(payload.get("start_date") or (end - timedelta(days=days)).isoformat())
    compare_end = start - timedelta(days=1)
    compare_start = compare_end - timedelta(days=days - 1)
    rows = [QueryRow.model_validate(row) for row in payload.get("rows", [])]
    return GSCSnapshot(
        site_url=payload.get("site_url") or settings.site_url,
        start_date=start,
        end_date=end,
        compare_start=compare_start,
        compare_end=compare_end,
        mock=True,
        rows=rows,
        notes=list(payload.get("notes", ["Loaded Search Console fixture (mock mode)."])),
    )


def fetch_live_gsc(settings: Settings, *, days: int = 28) -> GSCSnapshot:
    creds = _load_credentials(settings)
    from googleapiclient.discovery import build

    service = build("searchconsole", "v1", credentials=creds, cache_discovery=False)
    end = date.today() - timedelta(days=1)
    start = end - timedelta(days=days - 1)
    compare_end = start - timedelta(days=1)
    compare_start = compare_end - timedelta(days=days - 1)

    current = _query_search_analytics(service, settings.site_url, start, end)
    previous = _query_search_analytics(service, settings.site_url, compare_start, compare_end)
    prev_map = {(row["keys"][0], row["keys"][1]): row for row in previous if len(row.get("keys", [])) >= 2}

    rows: list[QueryRow] = []
    for row in current:
        keys = row.get("keys") or []
        if len(keys) < 2:
            continue
        query, page = keys[0], keys[1]
        prior = prev_map.get((query, page), {})
        impressions = int(row.get("impressions") or 0)
        clicks = int(row.get("clicks") or 0)
        rows.append(
            QueryRow(
                query=query,
                page=page,
                clicks=clicks,
                impressions=impressions,
                ctr=float(row.get("ctr") or (clicks / impressions if impressions else 0.0)),
                position=float(row.get("position") or 0.0),
                clicks_prev=int(prior["clicks"]) if prior else None,
                impressions_prev=int(prior["impressions"]) if prior else None,
                ctr_prev=float(prior["ctr"]) if prior and "ctr" in prior else None,
                position_prev=float(prior["position"]) if prior else None,
            )
        )
    return GSCSnapshot(
        site_url=settings.site_url,
        start_date=start,
        end_date=end,
        compare_start=compare_start,
        compare_end=compare_end,
        mock=False,
        rows=rows,
        notes=["Fetched live Search Console searchAnalytics.query (query + page, two windows)."],
    )


def _query_search_analytics(service: Any, site_url: str, start: date, end: date) -> list[dict[str, Any]]:
    body = {
        "startDate": start.isoformat(),
        "endDate": end.isoformat(),
        "dimensions": ["query", "page"],
        "rowLimit": 25000,
        "dataState": "final",
    }
    response = service.searchanalytics().query(siteUrl=site_url, body=body).execute()
    return list(response.get("rows") or [])


def _load_credentials(settings: Settings) -> Any:
    sa = settings.service_account_path()
    if sa and sa.is_file():
        from google.oauth2 import service_account

        return service_account.Credentials.from_service_account_file(str(sa), scopes=GSC_SCOPES)

    token_path = settings.token_path()
    if token_path.is_file():
        from google.oauth2.credentials import Credentials

        data = json.loads(token_path.read_text(encoding="utf-8"))
        creds = Credentials.from_authorized_user_info(data, scopes=GSC_SCOPES)
        if creds.valid:
            return creds
        if creds.expired and creds.refresh_token:
            from google.auth.transport.requests import Request

            creds.refresh(Request())
            token_path.write_text(creds.to_json(), encoding="utf-8")
            return creds

    client = settings.oauth_client_path()
    if client and client.is_file():
        raise RuntimeError(
            "OAuth client JSON is present but no token file. Run `protocolops auth` once on a machine with a browser."
        )
    raise RuntimeError("No Google credentials found. Set GOOGLE_APPLICATION_CREDENTIALS or run `protocolops auth`.")


def run_oauth_flow(settings: Settings, *, port: int = 0) -> Path:
    """Interactive installed-app OAuth. Saves a refreshable token JSON."""
    client = settings.oauth_client_path()
    if not client or not client.is_file():
        raise FileNotFoundError(
            "Set GSC_OAUTH_CLIENT_FILE to a desktop OAuth client JSON from Google Cloud Console."
        )
    from google_auth_oauthlib.flow import InstalledAppFlow

    flow = InstalledAppFlow.from_client_secrets_file(str(client), scopes=GSC_SCOPES)
    creds = flow.run_local_server(port=port, prompt="consent")
    token_path = settings.token_path()
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(creds.to_json(), encoding="utf-8")
    return token_path


def summarize_gsc(snapshot: GSCSnapshot, *, limit: int = 12) -> dict[str, Any]:
    ranked = sorted(snapshot.rows, key=lambda r: r.impressions, reverse=True)
    return {
        "site_url": snapshot.site_url,
        "range": {"start": snapshot.start_date.isoformat(), "end": snapshot.end_date.isoformat()},
        "compare": {
            "start": snapshot.compare_start.isoformat() if snapshot.compare_start else None,
            "end": snapshot.compare_end.isoformat() if snapshot.compare_end else None,
        },
        "mock": snapshot.mock,
        "totals": snapshot.totals,
        "top_queries": [
            {
                "query": row.query,
                "page": row.page,
                "clicks": row.clicks,
                "impressions": row.impressions,
                "ctr": row.ctr,
                "position": row.position,
                "position_delta": row.position_delta,
            }
            for row in ranked[:limit]
        ],
        "notes": snapshot.notes,
    }
