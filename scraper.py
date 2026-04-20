"""
Bot de búsqueda de departamentos en CABA
- Zonaprop + Argenprop
- Venta, terminados (no pozo), 10k-50k USD, más de 30m2
- Notificación por Telegram
- Historial en Supabase
- Ignora publicaciones sin precio
"""

import os
import re
import time
import hashlib
import requests
import cloudscraper
import urllib3
urllib3.disable_warnings()

from bs4 import BeautifulSoup
from supabase import create_client, Client
from dataclasses import dataclass
from typing import Optional

# ── Config ────────────────────────────────────────────────────────────────────

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_KEY"]
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-AR,es;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://www.google.com/",
}

SEARCH_URLS = [
    (
        "zonaprop",
        "https://www.zonaprop.com.ar/departamentos-venta-capital-federal-"
        "mas-de-30-m2-cubiertos-10000-50000-dolares-sin-emprendimiento-"
        "orden-publicado-descendente.html",
    ),
    (
        "argenprop",
        "https://www.argenprop.com/departamento-venta-en-capital-federal-"
        "desde-10000-hasta-50000-dolares-desde-30-metros-cuadrados-"
        "a-estrenar-orden-masnuevos",
    ),
]

TABLE_NAME = "depto_listings_seen"


# ── Data ──────────────────────────────────────────────────────────────────────

@dataclass
class Listing:
    id: str
    url: str
    title: str
    price: str
    location: str
    surface: str
    source: str
    image_url: Optional[str] = None


def has_price(price: str) -> bool:
    if not price:
        return False
    low = price.lower().strip()
    if low in ("", "consultar", "a consultar", "precio a consultar", "-", "—"):
        return False
    return bool(re.search(r"\d", low))


# ── Supabase ──────────────────────────────────────────────────────────────────

def get_supabase() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def load_seen_ids(sb: Client) -> set[str]:
    res = sb.table(TABLE_NAME).select("listing_id").execute()
    return {row["listing_id"] for row in res.data}


def mark_seen(sb: Client, listings: list[Listing]):
    if not listings:
        return
    rows = [{"listing_id": l.id, "source": l.source, "url": l.url} for l in listings]
    sb.table(TABLE_NAME).upsert(rows).execute()


# ── HTTP ──────────────────────────────────────────────────────────────────────

def make_id(url: str) -> str:
    return hashlib.sha1(url.encode()).hexdigest()


SCRAPERAPI_KEY = os.environ.get("SCRAPERAPI_KEY", "")

def fetch_html(url: str) -> str:
    if "zonaprop" in url and SCRAPERAPI_KEY:
        proxy_url = f"http://scraperapi:{SCRAPERAPI_KEY}@proxy-server.scraperapi.com:8001"
        proxies = {"http": proxy_url, "https": proxy_url}
        resp = requests.get(url, proxies=proxies, verify=False, timeout=30)
    else:
        resp = requests.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    return resp.text



# ── Parsers ───────────────────────────────────────────────────────────────────

def parse_zonaprop(html: str) -> list[Listing]:
    soup = BeautifulSoup(html, "lxml")
    listings = []

    for card in soup.select("[data-id]"):
        link_tag = card.select_one("a[href]")
        if not link_tag:
            continue

        href = link_tag.get("href", "")
        url = f"https://www.zonaprop.com.ar{href}" if href.startswith("/") else href
        if not url or ".html" not in url:
            continue

        price_tag = (
            card.select_one("div.firstPrice") or
            card.select_one("[class*='price']") or
            card.select_one("[class*='Price']")
        )
        price = price_tag.get_text(strip=True) if price_tag else ""

        if not has_price(price):
            continue

        title_tag = card.select_one("h2") or card.select_one("[class*='title']")
        location_tag = (
            card.select_one("[class*='location']") or
            card.select_one("[class*='address']")
        )
        surface_tag = card.select_one("[class*='surface']") or card.select_one("li")
        image_tag = card.select_one("img")

        listings.append(Listing(
            id=make_id(url),
            url=url,
            title=(title_tag.get_text(strip=True) if title_tag else "Departamento en venta"),
            price=price,
            location=(location_tag.get_text(strip=True) if location_tag else "CABA"),
            surface=(surface_tag.get_text(strip=True) if surface_tag else "—"),
            source="zonaprop",
            image_url=(image_tag.get("src") if image_tag else None),
        ))

    return listings


def parse_argenprop(html: str) -> list[Listing]:
    soup = BeautifulSoup(html, "lxml")
    listings = []

    for card in soup.select("div.listing__items div.listing__item"):
        link_tag = card.select_one("a")
        if not link_tag:
            continue

        href = link_tag.get("href", "")
        url = f"https://www.argenprop.com{href}" if href.startswith("/") else href
        if not url:
            continue

        price_tag = card.select_one("p.card__price")
        price = price_tag.get_text(strip=True) if price_tag else ""

        if not has_price(price):
            continue

        title_tag = card.select_one("p.card__title")
        location_tag = card.select_one("p.card__address")
        surface_tag = card.select_one("li.card__common-data span")
        image_tag = card.select_one("img")

        listings.append(Listing(
            id=make_id(url),
            url=url,
            title=(title_tag.get_text(strip=True) if title_tag else "Departamento en venta"),
            price=price,
            location=(location_tag.get_text(strip=True) if location_tag else "CABA"),
            surface=(surface_tag.get_text(strip=True) if surface_tag else "—"),
            source="argenprop",
            image_url=(image_tag.get("src") if image_tag else None),
        ))

    return listings


PARSERS = {
    "zonaprop": parse_zonaprop,
    "argenprop": parse_argenprop,
}


def scrape_all() -> list[Listing]:
    results = []
    for source, url in SEARCH_URLS:
        try:
            print(f"[{source}] Scrapeando...")
            html = fetch_html(url)
            print(f"[{source}] HTML snippet: {html[:300].replace(chr(10), ' ')}")
            parse_fn = PARSERS[source]
            found = parse_fn(html)
            print(f"[{source}] {len(found)} publicaciones con precio")
            results.extend(found)
            time.sleep(3)
        except Exception as e:
            print(f"[{source}] ERROR: {e}")
    return results


# ── Telegram ──────────────────────────────────────────────────────────────────

def send_telegram(listing: Listing):
    source_emoji = "🟡" if listing.source == "zonaprop" else "🔵"
    text = (
        f"{source_emoji} *{listing.title}*\n"
        f"💰 {listing.price}\n"
        f"📍 {listing.location}\n"
        f"📐 {listing.surface}\n"
        f"🔗 [Ver publicación]({listing.url})"
    )
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": False,
    }
    resp = requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
        json=payload,
        timeout=10,
    )
    if not resp.ok:
        print(f"Telegram error: {resp.text}")


def send_summary(new_count: int, total_scraped: int):
    if new_count == 0:
        text = f"🔍 Sin novedades — se revisaron {total_scraped} publicaciones con precio."
    else:
        text = f"✅ *{new_count} publicaciones nuevas* de {total_scraped} revisadas."

    requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
        json={"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "Markdown"},
        timeout=10,
    )


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print("=== Depto Bot iniciado ===")
    sb = get_supabase()

    seen_ids = load_seen_ids(sb)
    print(f"IDs ya vistos en Supabase: {len(seen_ids)}")

    all_listings = scrape_all()
    new_listings = [l for l in all_listings if l.id not in seen_ids]

    print(f"Nuevas publicaciones: {len(new_listings)}")

    for listing in new_listings:
        send_telegram(listing)
        time.sleep(0.5)

    mark_seen(sb, new_listings)
    send_summary(len(new_listings), len(all_listings))
    print("=== Fin ===")


if __name__ == "__main__":
    main()