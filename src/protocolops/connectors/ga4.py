from __future__ import annotations

import json

from protocolops.config import Settings
from protocolops.models import GA4Snapshot


def fetch_ga4(settings: Settings) -> GA4Snapshot | None:
    """Optional, env-gated GA4 snapshot. Live path is a documented stub."""
    if not settings.ga4_enabled:
        return None

    fixture = settings.fixture_dir() / "ga4" / "engagement.json"
    payload = json.loads(fixture.read_text(encoding="utf-8")) if fixture.is_file() else {}

    if settings.mock or not settings.ga4_property_id:
        return GA4Snapshot(
            enabled=True,
            mock=True,
            property_id=settings.ga4_property_id,
            sessions=int(payload.get("sessions") or 0),
            engaged_sessions=int(payload.get("engaged_sessions") or 0),
            views=int(payload.get("views") or 0),
            top_pages=list(payload.get("top_pages") or []),
            note="GA4 stub using fixture data (PROTOCOLOPS_GA4=true, mock or missing property id).",
        )

    # Live GA4 Data API is intentionally a stub in v1 — we do not pull production traffic
    # without an explicit future adapter. Return fixture-shaped data plus a warning.
    return GA4Snapshot(
        enabled=True,
        mock=True,
        property_id=settings.ga4_property_id,
        sessions=int(payload.get("sessions") or 0),
        engaged_sessions=int(payload.get("engaged_sessions") or 0),
        views=int(payload.get("views") or 0),
        top_pages=list(payload.get("top_pages") or []),
        note=(
            "GA4 live runReport is not wired in v1. Property "
            f"{settings.ga4_property_id} was set; serving fixture metrics only."
        ),
    )
