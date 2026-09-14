from __future__ import annotations

from datetime import datetime, timezone

from protocolops.config import Settings
from protocolops.models import (
    Analysis,
    DocsIndex,
    GA4Snapshot,
    GSCSnapshot,
    KeywordGap,
    Opportunity,
    QueryRow,
    RankingDrop,
)
from protocolops.textutil import overlap_score

DROP_POSITION_DELTA = 3.0
DROP_MIN_IMPRESSIONS = 40
GAP_SCORE = 0.32
GAP_MIN_IMPRESSIONS = 60
OPP_MIN_IMPRESSIONS = 180
OPP_MAX_CTR = 0.035
OPP_MIN_POSITION = 4.0


def analyze(
    snapshot: GSCSnapshot,
    index: DocsIndex,
    settings: Settings,
    ga4: GA4Snapshot | None = None,
) -> Analysis:
    drops: list[RankingDrop] = []
    gaps: list[KeywordGap] = []
    opportunities: list[Opportunity] = []
    covered: list[str] = []

    for row in snapshot.rows:
        best_title, score = best_doc_match(row.query, index)
        if score >= GAP_SCORE:
            covered.append(row.query)
        else:
            if row.impressions >= GAP_MIN_IMPRESSIONS:
                gaps.append(
                    KeywordGap(
                        query=row.query,
                        impressions=row.impressions,
                        clicks=row.clicks,
                        ctr=row.ctr,
                        position=row.position,
                        best_doc=best_title,
                        match_score=score,
                        reason=_gap_reason(row, score, best_title),
                    )
                )

        if (
            row.position_prev is not None
            and (row.position - row.position_prev) >= DROP_POSITION_DELTA
            and row.impressions >= DROP_MIN_IMPRESSIONS
        ):
            drops.append(
                RankingDrop(
                    query=row.query,
                    page=row.page,
                    position=row.position,
                    position_prev=row.position_prev,
                    position_delta=row.position - row.position_prev,
                    impressions=row.impressions,
                    clicks=row.clicks,
                    clicks_delta=row.clicks_delta,
                )
            )

        if (
            row.impressions >= OPP_MIN_IMPRESSIONS
            and row.ctr <= OPP_MAX_CTR
            and row.position >= OPP_MIN_POSITION
        ):
            opportunities.append(
                Opportunity(
                    query=row.query,
                    page=row.page,
                    impressions=row.impressions,
                    ctr=row.ctr,
                    position=row.position,
                    reason=(
                        f"High impressions ({row.impressions}) with CTR {row.ctr:.1%} at position "
                        f"{row.position:.1f} — snippet or title likely underperforming."
                    ),
                )
            )

    drops.sort(key=lambda item: (item.position_delta, item.impressions), reverse=True)
    gaps.sort(key=lambda item: item.impressions, reverse=True)
    opportunities.sort(key=lambda item: item.impressions, reverse=True)

    # Keep GA4 in the totals bag so the brief can mention it without a schema change.
    totals = dict(snapshot.totals)
    if ga4:
        totals["ga4_sessions"] = float(ga4.sessions)
        totals["ga4_views"] = float(ga4.views)

    return Analysis(
        generated_at=datetime.now(timezone.utc),
        site_url=snapshot.site_url,
        brand=settings.brand,
        totals=totals,
        ranking_drops=drops,
        keyword_gaps=gaps,
        opportunities=opportunities,
        covered_queries=covered,
    )


def best_doc_match(query: str, index: DocsIndex) -> tuple[str | None, float]:
    best_title: str | None = None
    best_score = 0.0
    for page in index.pages:
        heading_text = " ".join(h.text for h in page.headings)
        score = overlap_score(query, page.title, page.slug, page.description, heading_text, " ".join(page.keywords))
        if score > best_score:
            best_score = score
            best_title = page.title
    return best_title, best_score


def _gap_reason(row: QueryRow, score: float, best_title: str | None) -> str:
    if best_title is None:
        return f"No indexed doc overlaps with '{row.query}' ({row.impressions} impressions)."
    return (
        f"Best overlap is '{best_title}' at {score:.2f} — below {GAP_SCORE:.2f}. "
        f"Query earns {row.impressions} impressions at position {row.position:.1f}."
    )
