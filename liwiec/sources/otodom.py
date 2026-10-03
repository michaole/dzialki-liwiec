"""Otodom scraper — listings come from the page's __NEXT_DATA__ JSON."""
import json
import time

import pandas as pd
from bs4 import BeautifulSoup

from liwiec.http import fetch
from liwiec.listings import to_dataframe, to_float

NAME = "Otodom"
BASE_URL = "https://www.otodom.pl/pl/wyniki/sprzedaz/dzialka"

# Gminy on Otodom covering the places in miejscowosci_liwiec.csv
# (dolny bieg + ujście). Upper-course gminy were dropped with the places list.
SEARCH_PATHS = [
    "mazowieckie/wegrowski/lochow",         # Nadkole, Pogorzelec
    "mazowieckie/wyszkowski/wyszkow",       # Kamieńczyk, Świniotop
    "mazowieckie/wyszkowski/branszczyk",    # Brańszczyk, Brańszczyk-Nakieł
    "mazowieckie/wolominski/jadow",         # Starowola
]
SUBTYPES = ["building-plot", "recreational"]
MAX_PAGES = 5   # 36 listings/page


def parse_page(html: str | None) -> tuple[list[dict], int]:
    """Return (rows, total_pages) from one Otodom results page."""
    if not html:
        return [], 0
    tag = BeautifulSoup(html, "html.parser").find("script", id="__NEXT_DATA__")
    if not tag or not tag.string:
        return [], 0
    try:
        ads = json.loads(tag.string)["props"]["pageProps"]["data"]["searchAds"]
    except (json.JSONDecodeError, KeyError, TypeError):
        return [], 0

    total_pages = int((ads.get("pagination") or {}).get("totalPages", 1) or 1)
    rows = []
    for item in ads.get("items", []):
        try:
            rows.append(_parse_item(item))
        except Exception:
            continue
    return rows, total_pages


def _parse_item(item: dict) -> dict:
    location = item.get("location") or {}
    city_node = (location.get("address") or {}).get("city", {})
    city = city_node.get("name", "") if isinstance(city_node, dict) else str(city_node)

    county = next(
        (loc.get("name", "")
         for loc in (location.get("reverseGeocoding") or {}).get("locations", [])
         if loc.get("locationLevel") == "county"),
        "",
    )
    slug = item.get("slug", "")
    return {
        "id": str(item.get("id", "")),
        "tytul": item.get("title", "").strip(),
        "opis": (item.get("shortDescription") or "").strip()[:300],
        "cena_pln": to_float((item.get("totalPrice") or {}).get("value")),
        "cena_za_m2": to_float((item.get("pricePerSquareMeter") or {}).get("value")),
        "powierzchnia_m2": to_float(item.get("areaInSquareMeters")),
        "miejscowosc": city,
        "powiat": county,
        "url": f"https://www.otodom.pl/pl/oferta/{slug}" if slug else "",
        "typ": item.get("estate", ""),
        "data_dodania": (item.get("dateCreated") or "")[:10],
    }


def scrape(progress_callback=None) -> pd.DataFrame:
    rows = []
    for i, path in enumerate(SEARCH_PATHS):
        if progress_callback:
            progress_callback(f"📥 Otodom: gmina {path.split('/')[-1]}…", i / len(SEARCH_PATHS))

        url = f"{BASE_URL}/{path}"
        params = {
            "subType": ",".join(SUBTYPES), "limit": 36, "page": 1,
            "by": "DEFAULT", "direction": "DESC", "viewType": "listing",
        }
        page_rows, total_pages = parse_page(fetch(url, params=params, referer="https://www.otodom.pl/"))
        rows.extend(page_rows)

        for page in range(2, min(MAX_PAGES, total_pages) + 1):
            time.sleep(0.8)
            params["page"] = page
            page_rows, _ = parse_page(fetch(url, params=params, referer="https://www.otodom.pl/"))
            rows.extend(page_rows)

    return to_dataframe(rows, NAME)
