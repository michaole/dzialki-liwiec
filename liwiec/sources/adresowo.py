"""Adresowo.pl scraper — server-rendered HTML cards, searched per powiat.

Each listing is a <div data-offer-card data-id=...>. Price and area are
<p> elements holding a bold value <span> followed by a small unit <span>
("zł", "m²", "ha"); the place name is the first line of the /o/... link.
Selectors deliberately avoid colour/weight utility classes, which change
with site redesigns.
"""
import time

import pandas as pd
from bs4 import BeautifulSoup

from liwiec.http import fetch
from liwiec.listings import to_dataframe

NAME = "Adresowo"
BASE_URL = "https://adresowo.pl"

SEARCH_REGIONS = [
    "/dzialki/powiat-wyszkowski/",   # Kamieńczyk, Świniotop, Brańszczyk
    "/dzialki/powiat-wegrowski/",    # Nadkole, Pogorzelec
    "/dzialki/powiat-wolominski/",   # Starowola
]
MAX_PAGES = 10  # 39 listings/page


def parse_number(raw: str) -> float | None:
    """'1 598 454' / '1\xa0598\xa0454' → 1598454.0, '2,03' → 2.03."""
    if not raw:
        return None
    cleaned = raw.replace("\xa0", "").replace(" ", "").replace(".", "").replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return None


def _has_class(fragment: str):
    return lambda c: c is not None and fragment in c


def _parse_card(card) -> dict | None:
    data_id = card.get("data-id", "")
    link = card.find("a", href=lambda h: h and h.startswith("/o/"))
    if not data_id or not link:
        return None

    # First non-empty line-clamped span is the place name; older markup used font-bold
    name_span = next(
        (s for s in link.find_all("span", class_=_has_class("line-clamp-1"))
         if s.get_text(strip=True)),
        None,
    ) or link.find("span", class_=_has_class("font-bold"))

    price = area = None
    for p in card.find_all("p"):
        spans = p.find_all("span", recursive=False)
        if len(spans) < 2:
            continue
        value = parse_number(spans[0].get_text(strip=True))
        unit = spans[1].get_text(strip=True)
        if value is None:
            continue
        if unit == "zł":
            price = value
        elif unit == "m²":
            area = value
        elif unit == "ha":
            area = value * 10_000

    return {
        "id": f"adresowo_{data_id}",
        "tytul": link.get_text(separator=" ", strip=True),
        "miejscowosc": name_span.get_text(strip=True) if name_span else "",
        "cena_pln": price,
        "powierzchnia_m2": area,
        "url": BASE_URL + link["href"],
    }


def parse_page(html: str | None) -> tuple[list[dict], bool]:
    """Return (rows, has_next_page) from one Adresowo results page."""
    if not html:
        return [], False
    soup = BeautifulSoup(html, "html.parser")
    rows = [r for card in soup.find_all("div", attrs={"data-offer-card": True})
            if (r := _parse_card(card))]
    return rows, bool(soup.find("link", rel="next"))


def _page_url(region_path: str, page: int) -> str:
    """/dzialki/powiat-X/ → page 1 as-is, then /dzialki/powiat-X/_l2, _l3, ..."""
    if page == 1:
        return BASE_URL + region_path
    return f"{BASE_URL}{region_path.rstrip('/')}/_l{page}"


def scrape(progress_callback=None) -> pd.DataFrame:
    rows = []
    n = len(SEARCH_REGIONS)
    for i, region in enumerate(SEARCH_REGIONS):
        for page in range(1, MAX_PAGES + 1):
            if progress_callback:
                progress_callback(f"Adresowo: region {i + 1}/{n}, strona {page}…",
                                  (i + page / MAX_PAGES) / n)
            if page > 1:
                time.sleep(0.5)
            page_rows, has_next = parse_page(
                fetch(_page_url(region, page), referer="https://adresowo.pl/"))
            rows.extend(page_rows)
            if not has_next:
                break
        time.sleep(1)

    return to_dataframe(rows, NAME)
