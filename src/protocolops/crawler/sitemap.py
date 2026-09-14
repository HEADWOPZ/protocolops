from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urljoin, urlparse

from protocolops.config import Settings
from protocolops.models import DocsIndex, SitemapReport, SitemapUrl
from protocolops.textutil import slugify

NS = {
    "sm": "http://www.sitemaps.org/schemas/sitemap/0.9",
}


def load_sitemap(settings: Settings, *, remote_url: str | None = None) -> list[SitemapUrl]:
    fixture = settings.fixture_dir() / "sitemap.xml"
    urls: list[SitemapUrl] = []
    if fixture.is_file():
        urls.extend(parse_sitemap_xml(fixture.read_text(encoding="utf-8")))

    target = remote_url or settings.docs_url
    if target and not settings.use_mock_gsc():
        urls.extend(discover_sitemap_entries(target))
    elif target and not urls:
        urls.extend(discover_sitemap_entries(target))

    dedup: dict[str, SitemapUrl] = {}
    for item in urls:
        dedup[item.loc] = item
    return list(dedup.values())


def parse_sitemap_xml(xml_text: str) -> list[SitemapUrl]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []

    tag = _local(root.tag)
    results: list[SitemapUrl] = []
    if tag == "sitemapindex":
        for node in root.findall("sm:sitemap", NS) + list(root):
            loc = _child_text(node, "loc")
            if loc:
                results.append(SitemapUrl(loc=loc, lastmod=_child_text(node, "lastmod")))
        return results
    for node in root.findall("sm:url", NS) + [el for el in root if _local(el.tag) == "url"]:
        loc = _child_text(node, "loc")
        if loc:
            results.append(SitemapUrl(loc=loc, lastmod=_child_text(node, "lastmod")))
    return results


def discover_urls(base_url: str) -> list[str]:
    entries = discover_sitemap_entries(base_url)
    locs = [item.loc for item in entries]
    if locs:
        return locs
    return [base_url]


def discover_sitemap_entries(base_url: str) -> list[SitemapUrl]:
    import httpx

    candidates = _sitemap_candidates(base_url)
    found: list[SitemapUrl] = []
    with httpx.Client(follow_redirects=True, timeout=15.0, headers={"User-Agent": "ProtocolOps/0.1"}) as client:
        try:
            robots = client.get(urljoin(base_url, "/robots.txt"))
            if robots.status_code == 200:
                for line in robots.text.splitlines():
                    if line.lower().startswith("sitemap:"):
                        candidates.append(line.split(":", 1)[1].strip())
        except Exception:
            pass
        seen: set[str] = set()
        for candidate in candidates:
            if candidate in seen:
                continue
            seen.add(candidate)
            try:
                response = client.get(candidate)
                if response.status_code != 200:
                    continue
                parsed = parse_sitemap_xml(response.text)
                # sitemap index → fetch children
                if parsed and all(_looks_like_sitemap(item.loc) for item in parsed):
                    for child in parsed:
                        if child.loc in seen:
                            continue
                        seen.add(child.loc)
                        try:
                            child_resp = client.get(child.loc)
                            if child_resp.status_code == 200:
                                found.extend(parse_sitemap_xml(child_resp.text))
                        except Exception:
                            continue
                else:
                    found.extend(parsed)
            except Exception:
                continue
    return found


def check_sitemap(index: DocsIndex, sitemap_urls: list[SitemapUrl], settings: Settings) -> SitemapReport:
    site = settings.site_url.rstrip("/")
    sitemap_locs = [item.loc for item in sitemap_urls]
    sitemap_slugs = {_url_slug(loc, site) for loc in sitemap_locs}
    doc_slugs = [page.slug for page in index.pages]
    doc_urls = [page.url or f"{site}/{page.slug}" for page in index.pages]

    in_docs_not_sitemap = [
        url
        for url, slug in zip(doc_urls, doc_slugs, strict=False)
        if slug not in sitemap_slugs and url.rstrip("/") not in {u.rstrip("/") for u in sitemap_locs}
    ]
    in_sitemap_not_docs = [
        loc for loc in sitemap_locs if _url_slug(loc, site) not in set(doc_slugs)
    ]
    notes = []
    if not sitemap_urls:
        notes.append("No sitemap entries found (fixture or remote).")
    if in_docs_not_sitemap:
        notes.append(f"{len(in_docs_not_sitemap)} crawled docs are missing from the sitemap.")
    if in_sitemap_not_docs:
        notes.append(f"{len(in_sitemap_not_docs)} sitemap URLs have no matching crawled doc.")
    if not notes:
        notes.append("Docs index and sitemap are aligned.")
    return SitemapReport(
        sitemap_urls=sitemap_locs,
        indexed_slugs=doc_slugs,
        in_docs_not_sitemap=in_docs_not_sitemap,
        in_sitemap_not_docs=in_sitemap_not_docs,
        notes=notes,
    )


def load_local_sitemap_file(path: Path) -> list[SitemapUrl]:
    return parse_sitemap_xml(path.read_text(encoding="utf-8"))


def _sitemap_candidates(base_url: str) -> list[str]:
    parsed = urlparse(base_url)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    return [
        urljoin(origin + "/", "sitemap.xml"),
        urljoin(origin + "/", "sitemap-0.xml"),
        urljoin(base_url if base_url.endswith("/") else base_url + "/", "sitemap.xml"),
    ]


def _looks_like_sitemap(url: str) -> bool:
    lowered = url.lower()
    return "sitemap" in lowered and lowered.endswith(".xml")


def _url_slug(url: str, site: str) -> str:
    path = urlparse(url).path
    if url.rstrip("/") == site:
        return "index"
    return slugify(path.strip("/").replace("/", "-")) or "index"


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _child_text(node: ET.Element, name: str) -> str | None:
    child = node.find(f"sm:{name}", NS)
    if child is None:
        for item in node:
            if _local(item.tag) == name and item.text:
                return item.text.strip()
        return None
    return (child.text or "").strip() or None
