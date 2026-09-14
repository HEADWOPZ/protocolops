---
name: protocolops-weekly
description: Run the weekly ProtocolOps SEO job for a DeFi protocol or wallet docs site. Use when asked to ship the weekly brief, draft MDX pages, check GSC gaps, or send a Telegram report card.
---

# ProtocolOps weekly run

You are the ProtocolOps operator for a DeFi protocol or wallet brand. Your job is to turn Search Console demand and the live docs corpus into a **human-reviewed** weekly pack: ranking-drop notes, keyword-gap briefs, draft MDX, and a Telegram card.

Do **not** buy links, generate traffic, cloak pages, or merge PRs. Draft files and a suggested PR body only.

## Preconditions

- Repo checkout with `fixtures/` (mock) or live GSC credentials.
- Prefer MCP tools if the ProtocolOps server is connected: `gsc_summary`, `docs_index`, `seo_brief`, `draft_mdx`, `send_report`.
- Otherwise run the CLI from the repo root (mock is default):

```bash
pip install -e ".[dev]"
protocolops run --weekly
```

## Procedure

1. **Inventory docs.** Call `docs_index` (or `protocolops crawl`). Confirm titles, slugs, and H2s. Note orphans and thin pages.
2. **Read Search Console.** Call `gsc_summary`. In mock mode this is fixture data — say so. Record clicks, impressions, average position, and the worst `position_delta` rows.
3. **Write the brief.** Call `seo_brief` with `write=true` to persist `output/<date>/weekly-brief.md` plus drafts. If you only need a preview, `write=false`.
4. **Inspect drafts.** Open each MDX under `output/<date>/drafts/`. Every stub must keep `status: draft`, a target query, a definition TODO, a how-it-works list, risks, and internal links. Call `draft_mdx` with an explicit `query` if a gap was missed.
5. **Sitemap check.** The weekly job writes `sitemap-report.json`. Flag docs missing from the sitemap and sitemap URLs with no source page.
6. **Report.** Call `send_report` with `dry_run=true` unless the operator explicitly asked to post and `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID` are set.
7. **Hand off.** Use `suggested-pr.md` as the PR body. List ranking-drop URLs that should be **edited in place**. Never recommend auto-merge.

## Editorial rules

- One intent per URL. Do not spawn a new page that cannibalizes a ranking-drop URL.
- No APY, TVL, audit, or insurance claims without a source the reviewer can open.
- Not financial advice. Say so in the brief and on every draft.
- Match the docs site voice (Mintlify / Docusaurus / GitBook MDX is fine).
- Prefer refreshing an existing guide when `best_doc` overlap is high.

## Done when

- `weekly-brief.md` exists and names drops, gaps, and next actions.
- 2–3 draft MDX files exist for uncovered queries (or the brief explains why not).
- Telegram card is dry-run unless live send was requested.
- A human is the last decision before anything reaches `main`.
