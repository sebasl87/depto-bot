# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project does

A Python scraper that runs twice daily via GitHub Actions, fetches apartment listings from Zonaprop and Argenprop (CABA, USD 10k–50k, 30m²+, finished/new units), deduplicates against a Supabase table, and sends new listings to a Telegram chat.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run locally (requires env vars)
SUPABASE_URL=... SUPABASE_KEY=... TELEGRAM_TOKEN=... TELEGRAM_CHAT_ID=... python scraper.py

# Optional: use ScraperAPI for Zonaprop (bypasses bot detection)
SCRAPERAPI_KEY=... python scraper.py
```

## Architecture

Single-file script (`scraper.py`) with this flow:

1. **Scrape** — `scrape_all()` iterates `SEARCH_URLS`, calls `fetch_html()`, dispatches to the matching parser in `PARSERS` dict
2. **Deduplicate** — listing IDs are `sha1(url)` hashes; `load_seen_ids()` fetches all known IDs from Supabase
3. **Notify** — new listings are sent one-by-one via Telegram Bot API (`send_telegram()`), then `mark_seen()` upserts them to Supabase
4. **Summary** — `send_summary()` sends a final count message

**Parsers:** `parse_zonaprop()` selects on `[data-id]` cards; `parse_argenprop()` selects on `div.listing__item`. Both skip listings where `has_price()` returns False (no price or "consultar").

**Fetch strategy:** Zonaprop uses ScraperAPI proxy when `SCRAPERAPI_KEY` is set (bot protection); Argenprop uses plain `requests` with a browser User-Agent.

## Required secrets (GitHub Actions / local env)

| Variable | Description |
|---|---|
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_KEY` | **service_role** key (not anon) |
| `TELEGRAM_TOKEN` | BotFather token |
| `TELEGRAM_CHAT_ID` | Numeric chat ID |
| `SCRAPERAPI_KEY` | Optional — enables proxy for Zonaprop |

## Database

Table `depto_listings_seen` in Supabase. Schema in `supabase_migration.sql`. RLS is enabled; only the service_role key can write.

## Updating search filters

Modify `SEARCH_URLS` in `scraper.py`. The easiest approach: set filters on zonaprop.com.ar or argenprop.com visually, then copy the resulting URL.

## Fixing broken parsers

If listings stop appearing, the site's HTML likely changed. Inspect the listing cards in browser DevTools and update the CSS selectors in `parse_zonaprop()` or `parse_argenprop()`.
