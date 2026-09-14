from __future__ import annotations

from protocolops.config import Settings
from protocolops.models import Analysis, SitemapReport, TelegramResult, WeeklyArtifacts


def format_report_card(
    analysis: Analysis,
    *,
    drafts: list[str],
    sitemap: SitemapReport | None = None,
    mock: bool = True,
    brand: str | None = None,
) -> str:
    brand_name = brand or analysis.brand
    totals = analysis.totals
    drops = analysis.ranking_drops[:3]
    gaps = analysis.keyword_gaps[:3]
    lines = [
        f"ProtocolOps · {brand_name}",
        f"{'MOCK' if mock else 'LIVE'} weekly SEO card",
        "",
        f"Clicks {int(totals.get('clicks', 0))} · Impr {int(totals.get('impressions', 0))} · "
        f"Avg pos {totals.get('avg_position', 0)} · CTR {totals.get('avg_ctr', 0):.2%}",
        "",
        "Ranking drops",
    ]
    if drops:
        for drop in drops:
            lines.append(
                f"• {drop.query}  {drop.position_prev:.1f} → {drop.position:.1f}  "
                f"({drop.impressions} impr)"
            )
    else:
        lines.append("• none above threshold")

    lines.extend(["", "Keyword gaps"])
    if gaps:
        for gap in gaps:
            lines.append(f"• {gap.query}  ({gap.impressions} impr, score {gap.match_score})")
    else:
        lines.append("• none above threshold")

    lines.extend(["", "Draft MDX"])
    if drafts:
        for path in drafts:
            lines.append(f"• {path.split('/')[-1]}")
    else:
        lines.append("• none")

    if sitemap:
        lines.extend(
            [
                "",
                "Sitemap",
                f"• docs missing from sitemap: {len(sitemap.in_docs_not_sitemap)}",
                f"• sitemap URLs missing docs: {len(sitemap.in_sitemap_not_docs)}",
            ]
        )
    lines.extend(["", "Human review required. Do not auto-merge."])
    return "\n".join(lines)


def send_telegram(
    text: str,
    settings: Settings,
    *,
    dry_run: bool = True,
) -> TelegramResult:
    if dry_run or not settings.telegram_bot_token or not settings.telegram_chat_id:
        reason = "dry_run=true" if dry_run else "TELEGRAM_BOT_TOKEN/CHAT_ID unset"
        return TelegramResult(
            dry_run=True,
            ok=True,
            destination=f"dry-run ({reason})",
            text=text,
        )

    import httpx

    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    try:
        response = httpx.post(
            url,
            json={
                "chat_id": settings.telegram_chat_id,
                "text": text,
                "disable_web_page_preview": True,
            },
            timeout=20,
        )
        response.raise_for_status()
        payload = response.json()
        if not payload.get("ok"):
            return TelegramResult(
                dry_run=False,
                ok=False,
                destination=str(settings.telegram_chat_id),
                text=text,
                error=str(payload),
            )
        return TelegramResult(
            dry_run=False,
            ok=True,
            destination=str(settings.telegram_chat_id),
            text=text,
        )
    except Exception as exc:  # noqa: BLE001
        return TelegramResult(
            dry_run=False,
            ok=False,
            destination=str(settings.telegram_chat_id),
            text=text,
            error=str(exc),
        )


def report_from_artifacts(artifacts: WeeklyArtifacts, settings: Settings, *, dry_run: bool = True) -> TelegramResult:
    # analysis is already on artifacts; sitemap details live in the written report file
    text = format_report_card(
        artifacts.analysis,
        drafts=artifacts.draft_paths,
        mock=artifacts.mock,
        brand=settings.brand,
    )
    return send_telegram(text, settings, dry_run=dry_run)
