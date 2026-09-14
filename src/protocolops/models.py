from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field


class Heading(BaseModel):
    level: int
    text: str
    slug: str


class DocPage(BaseModel):
    path: str
    slug: str
    url: str | None = None
    title: str
    description: str = ""
    headings: list[Heading] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    word_count: int = 0
    source: str = "local"


class DocsIndex(BaseModel):
    source: str
    crawled_at: datetime
    pages: list[DocPage] = Field(default_factory=list)

    @property
    def titles(self) -> list[str]:
        return [page.title for page in self.pages]


class QueryRow(BaseModel):
    query: str
    page: str
    clicks: int = 0
    impressions: int = 0
    ctr: float = 0.0
    position: float = 0.0
    clicks_prev: int | None = None
    impressions_prev: int | None = None
    ctr_prev: float | None = None
    position_prev: float | None = None

    @property
    def position_delta(self) -> float | None:
        if self.position_prev is None:
            return None
        return round(self.position - self.position_prev, 2)

    @property
    def clicks_delta(self) -> int | None:
        if self.clicks_prev is None:
            return None
        return self.clicks - self.clicks_prev


class GSCSnapshot(BaseModel):
    site_url: str
    start_date: date
    end_date: date
    compare_start: date | None = None
    compare_end: date | None = None
    mock: bool = True
    rows: list[QueryRow] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)

    @property
    def totals(self) -> dict[str, float]:
        return {
            "clicks": float(sum(r.clicks for r in self.rows)),
            "impressions": float(sum(r.impressions for r in self.rows)),
            "avg_position": (
                round(sum(r.position * r.impressions for r in self.rows) / sum(r.impressions for r in self.rows), 2)
                if self.rows and sum(r.impressions for r in self.rows)
                else 0.0
            ),
            "avg_ctr": (
                round(sum(r.clicks for r in self.rows) / sum(r.impressions for r in self.rows), 4)
                if self.rows and sum(r.impressions for r in self.rows)
                else 0.0
            ),
        }


class GA4Snapshot(BaseModel):
    enabled: bool
    mock: bool = True
    property_id: str | None = None
    sessions: int = 0
    engaged_sessions: int = 0
    views: int = 0
    top_pages: list[dict[str, Any]] = Field(default_factory=list)
    note: str = "GA4 stub — enable PROTOCOLOPS_GA4=true to include fixture or live engagement."


class RankingDrop(BaseModel):
    query: str
    page: str
    position: float
    position_prev: float
    position_delta: float
    impressions: int
    clicks: int
    clicks_delta: int | None = None


class KeywordGap(BaseModel):
    query: str
    impressions: int
    clicks: int
    ctr: float
    position: float
    best_doc: str | None = None
    match_score: float = 0.0
    reason: str


class Opportunity(BaseModel):
    query: str
    page: str
    impressions: int
    ctr: float
    position: float
    reason: str


class Analysis(BaseModel):
    generated_at: datetime
    site_url: str
    brand: str
    totals: dict[str, float]
    ranking_drops: list[RankingDrop] = Field(default_factory=list)
    keyword_gaps: list[KeywordGap] = Field(default_factory=list)
    opportunities: list[Opportunity] = Field(default_factory=list)
    covered_queries: list[str] = Field(default_factory=list)


class SitemapUrl(BaseModel):
    loc: str
    lastmod: str | None = None


class SitemapReport(BaseModel):
    sitemap_urls: list[str] = Field(default_factory=list)
    indexed_slugs: list[str] = Field(default_factory=list)
    in_docs_not_sitemap: list[str] = Field(default_factory=list)
    in_sitemap_not_docs: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class DraftSpec(BaseModel):
    slug: str
    title: str
    description: str
    target_query: str
    keywords: list[str] = Field(default_factory=list)
    related_slugs: list[str] = Field(default_factory=list)
    path: str
    reason: str


class WeeklyArtifacts(BaseModel):
    run_id: str
    started_at: datetime
    finished_at: datetime
    mock: bool
    output_dir: str
    brief_path: str
    draft_paths: list[str] = Field(default_factory=list)
    sitemap_path: str
    report_path: str
    suggested_pr_path: str
    analysis: Analysis
    telegram_dry_run: bool = True


class TelegramResult(BaseModel):
    dry_run: bool
    ok: bool
    destination: str
    text: str
    error: str | None = None
