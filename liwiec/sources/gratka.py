"""Gratka.pl scraper.

Gratka is a Nuxt 3 SSR app. All listing data is embedded in a
<script id="__NUXT_DATA__"> tag as a flat JSON array where integer
values are cross-references to other positions in the same array.
"""
import json
import re
import time

import pandas as pd

from liwiec.http import fetch
from liwiec.listings import to_dataframe, to_float

NAME = "Gratka"
BASE_URL = "https://gratka.pl/nieruchomosci/dzialki-grunty"

# Powiaty covering the places in miejscowosci_liwiec.csv — one search pass each
SEARCH_REGIONS = [
    "mazowieckie/wegrowski",     # Nadkole, Pogorzelec
    "mazowieckie/wyszkowski",    # Kamieńczyk, Świniotop, Brańszczyk
    "mazowieckie/wolominski",    # Starowola
]
PAGE_SIZE = 35
MAX_PAGES = 8

_NUXT_RE = re.compile(r'<script[^>]+id="__NUXT_DATA__"[^>]*>([\s\S]*?)</script>')


def _resolve(val, data, depth=0, seen=frozenset()):
    """Recursively resolve Nuxt 3 compact index references."""
    if depth > 40:
        return val
    if isinstance(val, int):
        if val in seen or val < 0 or val >= len(data):
            return val
        return _resolve(data[val], data, depth + 1, seen | {val})
    if isinstance(val, list):
        # Nuxt wraps reactive objects as [TypeName, index] — unwrap them
        if len(val) == 2 and isinstance(val[0], str) and isinstance(val[1], int):
            return _resolve(val[1], data, depth + 1, seen)
        return [_resolve(v, data, depth + 1, seen) for v in val]
    if isinstance(val, dict):
        return {k: _resolve(v, data, depth + 1, seen) for k, v in val.items()}
    return val


def _parse_count(text) -> int | None:
    """'143 ogłoszenia' / '1 204 ogłoszeń' → 143 / 1204."""
    m = re.match(r"\s*(\d[\d\s\xa0]*)", text) if isinstance(text, str) else None
    return int(re.sub(r"\D", "", m.group(1))) if m else None


def parse_page(html: str | None) -> tuple[list[dict], int]:
    """Return (rows, total_pages) from one Gratka results page."""
    if not html:
        return [], 1
    m = _NUXT_RE.search(html)
    if not m:
        return [], 1
    try:
        data = json.loads(m.group(1))
    except json.JSONDecodeError:
        return [], 1
    if not isinstance(data, list):
        return [], 1

    rows, total_pages = [], 1
    for raw in data:
        if not isinstance(raw, dict):
            continue
        if "count" in raw and "header" in raw:      # {'count': '143 ogłoszenia', ...}
            total = _parse_count(_resolve(raw["count"], data))
            if total:
                total_pages = max(total_pages, -(-total // PAGE_SIZE))
        if "idOnFrontend" not in raw:
            continue
        try:
            row = _parse_item(_resolve(raw, data))
        except Exception:
            continue
        if row:
            rows.append(row)
    return rows, total_pages


def _parse_item(item) -> dict | None:
    if not isinstance(item, dict):
        return None
    id_fe = item.get("idOnFrontend", "")
    if not id_fe or not isinstance(id_fe, str):
        return None

    price_obj = item.get("price") or {}
    price = to_float(price_obj.get("amount")) if isinstance(price_obj, dict) else None

    # location.location = [voivodeship, county, gmina, city] — last is most specific
    city = ""
    loc = item.get("location") or {}
    if isinstance(loc, dict):
        loc_arr = loc.get("location") or []
        if isinstance(loc_arr, list) and loc_arr:
            city = str(loc_arr[-1]).strip()

    title = item.get("advertisementText") or item.get("title") or ""
    url_path = item.get("url", "")
    return {
        "id": f"gratka_{id_fe}",
        "tytul": str(title).strip()[:120],
        "cena_pln": price,
        "powierzchnia_m2": to_float(item.get("area")),   # string like "2 472"
        "miejscowosc": city,
        "url": f"https://gratka.pl{url_path}" if url_path else "",
        "data_dodania": (item.get("addedAt") or "")[:10],
    }


def _fetch_page(url: str, page: int) -> str | None:
    return fetch(url, params={"page": page} if page > 1 else None, referer="https://gratka.pl/")


def scrape(progress_callback=None) -> pd.DataFrame:
    rows = []
    n = len(SEARCH_REGIONS)
    for i, region in enumerate(SEARCH_REGIONS):
        label = region.split("/")[-1]
        if progress_callback:
            progress_callback(f"🔍 Gratka: powiat {label}…", i / n)

        url = f"{BASE_URL}/{region}"
        page_rows, total_pages = parse_page(_fetch_page(url, 1))
        rows.extend(page_rows)

        pages = min(MAX_PAGES, total_pages)
        for page in range(2, pages + 1):
            time.sleep(0.7)
            if progress_callback:
                progress_callback(f"🔍 Gratka: {label} str. {page}/{pages}…", (i + page / pages) / n)
            more, _ = parse_page(_fetch_page(url, page))
            rows.extend(more)

        time.sleep(0.5)

    return to_dataframe(rows, NAME)
