from __future__ import annotations

import re
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse

import yaml

from protocolops.config import Settings
from protocolops.models import DocPage, DocsIndex, Heading
from protocolops.textutil import first_paragraph, slugify, word_count

MD_EXTS = {".md", ".mdx", ".markdown"}
FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?", re.DOTALL)
HEADING_RE = re.compile(r"^(#{1,3})\s+(.+?)\s*$", re.MULTILINE)


def crawl_docs(settings: Settings) -> DocsIndex:
    """Crawl a local docs folder and optionally a public docs origin."""
    pages: list[DocPage] = []
    sources: list[str] = []

    docs_dir = settings.docs_dir()
    if docs_dir.is_dir():
        pages.extend(_crawl_local(docs_dir, settings.site_url))
        sources.append(str(docs_dir))

    if settings.docs_url:
        remote = _crawl_remote(settings.docs_url)
        pages.extend(remote)
        sources.append(settings.docs_url)

    if not pages:
        raise FileNotFoundError(
            f"No markdown/MDX docs found at {docs_dir} and no remote pages from {settings.docs_url!r}."
        )

    deduped = _dedupe(pages)
    return DocsIndex(
        source=" + ".join(sources),
        crawled_at=datetime.now(timezone.utc),
        pages=deduped,
    )


def parse_markdown_file(path: Path, root: Path, site_url: str) -> DocPage:
    text = path.read_text(encoding="utf-8")
    return parse_markdown_text(
        text,
        rel_path=path.relative_to(root).as_posix(),
        site_url=site_url,
        source="local",
    )


def parse_markdown_text(
    text: str,
    *,
    rel_path: str,
    site_url: str,
    source: str = "local",
) -> DocPage:
    frontmatter, body = split_frontmatter(text)
    title = str(frontmatter.get("title") or _first_heading(body) or Path(rel_path).stem)
    slug = str(frontmatter.get("slug") or _slug_from_path(rel_path, title))
    description = str(frontmatter.get("description") or first_paragraph(body))
    raw_keywords = frontmatter.get("keywords") or frontmatter.get("tags") or []
    if isinstance(raw_keywords, str):
        keywords = [part.strip() for part in raw_keywords.split(",") if part.strip()]
    else:
        keywords = [str(item) for item in raw_keywords]
    headings = extract_headings(body)
    url = _join_url(site_url, slug)
    return DocPage(
        path=rel_path,
        slug=slug,
        url=url,
        title=title,
        description=description,
        headings=headings,
        keywords=keywords,
        word_count=word_count(body),
        source=source,
    )


def split_frontmatter(text: str) -> tuple[dict, str]:
    match = FRONTMATTER_RE.match(text)
    if not match:
        return {}, text
    raw = match.group(1)
    loaded = yaml.safe_load(raw) or {}
    if not isinstance(loaded, dict):
        return {}, text[match.end() :]
    return loaded, text[match.end() :]


def extract_headings(markdown: str) -> list[Heading]:
    headings: list[Heading] = []
    for match in HEADING_RE.finditer(markdown):
        level = len(match.group(1))
        text = re.sub(r"[#*`]+", "", match.group(2)).strip()
        text = re.sub(r"\{#[^}]+\}", "", text).strip()
        if text:
            headings.append(Heading(level=level, text=text, slug=slugify(text)))
    return headings


def index_to_dict(index: DocsIndex) -> dict:
    return {
        "source": index.source,
        "crawled_at": index.crawled_at.isoformat(),
        "page_count": len(index.pages),
        "pages": [
            {
                "title": page.title,
                "slug": page.slug,
                "path": page.path,
                "url": page.url,
                "description": page.description,
                "headings": [h.model_dump() for h in page.headings],
                "keywords": page.keywords,
                "word_count": page.word_count,
                "source": page.source,
            }
            for page in index.pages
        ],
    }


def _crawl_local(root: Path, site_url: str) -> list[DocPage]:
    pages: list[DocPage] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in MD_EXTS:
            continue
        if any(part.startswith(".") for part in path.relative_to(root).parts):
            continue
        pages.append(parse_markdown_file(path, root, site_url))
    return pages


def _crawl_remote(base_url: str) -> list[DocPage]:
    import httpx

    from protocolops.crawler.sitemap import discover_urls

    pages: list[DocPage] = []
    try:
        urls = discover_urls(base_url)
    except Exception:
        urls = [base_url]

    with httpx.Client(follow_redirects=True, timeout=20.0, headers={"User-Agent": "ProtocolOps/0.1"}) as client:
        for url in urls[:80]:
            try:
                response = client.get(url)
                response.raise_for_status()
            except Exception:
                continue
            content_type = response.headers.get("content-type", "")
            rel = urlparse(url).path.lstrip("/") or "index"
            if "markdown" in content_type or url.endswith((".md", ".mdx")):
                pages.append(
                    parse_markdown_text(response.text, rel_path=rel, site_url=base_url, source="remote")
                )
                continue
            parsed = _parse_html_doc(response.text, url=url, site_url=base_url)
            if parsed:
                pages.append(parsed)
    return pages


def _parse_html_doc(html: str, *, url: str, site_url: str) -> DocPage | None:
    parser = _DocHTMLParser()
    try:
        parser.feed(html)
    except Exception:
        return None
    title = parser.title or parser.h1 or urlparse(url).path.rsplit("/", 1)[-1]
    if not title:
        return None
    slug = _slug_from_path(urlparse(url).path, title)
    headings = [
        Heading(level=level, text=text, slug=slugify(text)) for level, text in parser.headings if text
    ]
    return DocPage(
        path=url,
        slug=slug,
        url=url,
        title=title.strip(),
        description=(parser.description or "")[:240],
        headings=headings,
        word_count=word_count(parser.text),
        source="remote",
    )


class _DocHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title = ""
        self.h1 = ""
        self.description = ""
        self.headings: list[tuple[int, str]] = []
        self.text_parts: list[str] = []
        self._capture: str | None = None
        self._buf: list[str] = []
        self._skip = 0

    @property
    def text(self) -> str:
        return " ".join(self.text_parts)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_d = {k: v or "" for k, v in attrs}
        if tag in {"script", "style", "nav", "footer"}:
            self._skip += 1
            return
        if tag == "meta" and attrs_d.get("name", "").lower() == "description":
            self.description = attrs_d.get("content", "")
        if tag in {"title", "h1", "h2", "h3"}:
            self._capture = tag
            self._buf = []

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "nav", "footer"} and self._skip:
            self._skip -= 1
            return
        if tag == self._capture:
            text = re.sub(r"\s+", " ", "".join(self._buf)).strip()
            if tag == "title":
                self.title = text
            elif tag == "h1":
                self.h1 = self.h1 or text
                self.headings.append((1, text))
            elif tag == "h2":
                self.headings.append((2, text))
            elif tag == "h3":
                self.headings.append((3, text))
            self._capture = None
            self._buf = []

    def handle_data(self, data: str) -> None:
        if self._skip:
            return
        if self._capture:
            self._buf.append(data)
        stripped = data.strip()
        if stripped:
            self.text_parts.append(stripped)


def _first_heading(markdown: str) -> str | None:
    match = HEADING_RE.search(markdown)
    return match.group(2).strip() if match else None


def _slug_from_path(rel_path: str, title: str) -> str:
    stem = Path(rel_path).as_posix()
    stem = re.sub(r"\.(mdx?|markdown|html?)$", "", stem, flags=re.I)
    stem = stem.strip("/")
    if stem in {"", "index", "docs"}:
        return slugify(title)
    return slugify(stem.replace("/", "-"))


def _join_url(site_url: str, slug: str) -> str:
    base = site_url if site_url.endswith("/") else site_url + "/"
    return urljoin(base, slug)


def _dedupe(pages: list[DocPage]) -> list[DocPage]:
    seen: dict[str, DocPage] = {}
    for page in pages:
        key = page.slug or page.path
        if key not in seen:
            seen[key] = page
    return list(seen.values())
