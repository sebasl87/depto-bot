"""
Bot de búsqueda de departamentos en CABA
- Zonaprop + Argenprop
- Venta, terminados (no pozo), 10k-50k USD, más de 30m2
- Notificación por Telegram
- Historial en Supabase
"""

import os
import time
import hashlib
import requests
import cloudscraper
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

# URLs de búsqueda — ordenadas por más nuevas, sin pozo, CABA, venta, USD
# Zonaprop filtra "a estrenar" (terminados) y excluye en pozo con el parámetro
SEARCH_URLS = [
    # Zonaprop: deptos venta CABA, 10k-50k USD, +30m2, terminados/a estrenar
    (
        "zonaprop",
        "https://www.zonaprop.com.ar/departamentos-venta-capital-federal-"
        "mas-de-30-m2-cubiertos-10000-50000-dolares-sin-emprendimiento-"
        "orden-publicado-descendente.html",
    ),
    # Argenprop: deptos venta CABA, 10k-50k USD, +30m2, a estrenar
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
    id: str          # hash de la URL
    url: str
    title: str
    price: str
    location: str
    surface: str
    source: str
    image_url: Optional[str] = None


# ── Supabase ──────────────────────────────────────────────────────────────────

def get_supabase() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def ensure_table(sb: Client):
    """Crea la tabla si no existe (ejecutar una sola vez o via migration)."""
    # Supabase no expone DDL por client, esto es solo documentativo.
    # Crear manualmente en el dashboard o con la migration de abajo.
    pass


def load_seen_ids(sb: Client) -> set[str]:
    res = sb.table(TABLE_NAME).select("listing_id").execute()
    return {row["listing_id"] for row in res.data}


def mark_seen(sb: Client, listings: list[Listing]):
    if not listings:
        return
    rows = [{"listing_id": l.id, "source": l.source, "url": l.url} for l in listings]
    sb.table(TABLE_NAME).upsert(rows).execute()


# ── Scrapers ──────────────────────────────────────────────────────────────────

def make_id(url: str) -> str:
    return hashlib.sha1(url.encode()).hexdigest()


def fetch_html(url: str) -> str:
    if "zonaprop" in url:
        scraper = cloudscraper.create_scraper(
            browser={"browser": "chrome", "platform": "windows", "mobile": False}
        )
        resp = scraper.get(url, timeout=30)
    else:
        resp = requests.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    return resp.text


def parse_zonaprop(html: str) -> list[Listing]:
    soup = BeautifulSoup(html, "lxml")
    listings = []

    for card in soup.select("div[data-id]"):
        link_tag = card.select_one("a.go-to-posting")
        if not link_tag:
            continue

        href = link_tag.get("href", "")
        url = f"https://www.zonaprop.com.ar{href}" if href.startswith("/") else href
        if not url:
            continue

        title = card.select_one("h2.postingCardTitle")
        price = card.select_one("div.firstPrice")
        location = card.select_one("div.postingCardLocation span")
        surface = card.select_one("span[aria-label*='m²'], li.mainFeatures-feature")
        image = card.select_one("img")

        listings.append(Listing(
            id=make_id(url),
            url=url,
            title=(title.get_text(strip=True) if title else "Sin título"),
            price=(price.get_text(strip=True) if price else "Consultar"),
            location=(location.get_text(strip=True) if location else "CABA"),
            surface=(surface.get_text(strip=True) if surface else "—"),
            source="zonaprop",
            image_url=(image.get("src") if image else None),
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

        title = card.select_one("p.card__title")
        price = card.select_one("p.card__price")
        location = card.select_one("p.card__address")
        surface = card.select_one("li.card__common-data span")
        image = card.select_one("img")

        listings.append(Listing(
            id=make_id(url),
            url=url,
            title=(title.get_text(strip=True) if title else "Sin título"),
            price=(price.get_text(strip=True) if price else "Consultar"),
            location=(location.get_text(strip=True) if location else "CABA"),
            surface=(surface.get_text(strip=True) if surface else "—"),
            source="argenprop",
            image_url=(image.get("src") if image else None),
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
            print(f"[{source}] Scrapeando {url[:80]}...")
            html = fetch_html(url)
            parse_fn = PARSERS[source]
            found = parse_fn(html)
            print(f"[{source}] {len(found)} publicaciones encontradas")
            results.extend(found)
            time.sleep(2)  # pausa cortés entre requests
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
        text = f"🔍 Sin novedades — se revisaron {total_scraped} publicaciones."
    else:
        text = f"✅ Se encontraron *{new_count} publicaciones nuevas* de {total_scraped} revisadas."

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
