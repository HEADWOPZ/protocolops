from __future__ import annotations

from protocolops.crawler.docs import crawl_docs, parse_markdown_text
from protocolops.crawler.sitemap import check_sitemap, load_sitemap, parse_sitemap_xml


def test_local_docs_index_titles_headings_slugs(settings):
    index = crawl_docs(settings)
    slugs = {page.slug for page in index.pages}
    assert slugs == {"getting-started", "connect-wallet", "stake-hls", "governance", "faq"}
    stake = next(page for page in index.pages if page.slug == "stake-hls")
    assert stake.title == "Stake HLS"
    assert any(h.text == "Deposit" for h in stake.headings)
    assert stake.word_count > 40


def test_frontmatter_and_heading_fallback():
    page = parse_markdown_text(
        "# Wallet errors\n\nUser rejected the request.\n\n## Code 4001\n",
        rel_path="errors.mdx",
        site_url="https://docs.helios.example/",
    )
    assert page.title == "Wallet errors"
    assert page.slug == "errors"
    assert page.headings[0].text == "Wallet errors"
    assert page.headings[1].slug == "code-4001"


def test_sitemap_alignment(settings):
    index = crawl_docs(settings)
    urls = load_sitemap(settings)
    locs = {item.loc for item in urls}
    assert "https://docs.helios.example/getting-started" in locs
    report = check_sitemap(index, urls, settings)
    assert any("faq" in url for url in report.in_docs_not_sitemap)
    assert any(url.endswith("/bridge") for url in report.in_sitemap_not_docs)


def test_parse_sitemap_index_and_urlset():
    xml = """<?xml version="1.0"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <url><loc>https://docs.helios.example/a</loc></url>
    </urlset>"""
    assert parse_sitemap_xml(xml)[0].loc.endswith("/a")
