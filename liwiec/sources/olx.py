"""OLX scraper — listings come from window.__PRERENDERED_STATE__, searched per place."""
import json
import re
import time

import pandas as pd

from liwiec.http import fetch
from liwiec.listings import to_dataframe, to_float
from liwiec.places import normalize, place_names

NAME = "OLX"
BASE_URL = "https://www.olx.pl/nieruchomosci/dzialki/sprzedaz"
MAX_PAGES = 5

# Bounding box of the Liwiec area (generous margin). Listings with GPS outside
# it come from a different place with the same name.
_LAT_MIN, _LAT_MAX = 52.20, 52.70
_LON_MIN, _LON_MAX = 21.40, 22.25

_STATE_RE = re.compile(r'window\.__PRERENDERED_STATE__= ("(?:[^"\\]|\\.)*")')


def city_slug(name: str) -> str:
    """'Brańszczyk-Nakieł' → 'branszczyk-nakiel' (OLX URL slug)."""
    return re.sub(r"[^a-z0-9]+", "-", normalize(name)).strip("-")


def in_liwiec_bbox(lat, lon) -> bool:
    if lat is None or lon is None:
        return True   # no GPS — city matching decides
    return _LAT_MIN <= lat <= _LAT_MAX and _LON_MIN <= lon <= _LON_MAX


def parse_page(html: str | None) -> tuple[list[dict], int]:
    """Return (rows, total_pages) from one OLX results page."""
    if not html:
        return [], 0
    m = _STATE_RE.search(html)
    if not m:
        return [], 0
    try:
        # The state is a JSON string containing JSON — decode twice
        listing = json.loads(json.loads(m.group(1)))["listing"]["listing"]
    except (json.JSONDecodeError, KeyError, TypeError):
        return [], 0

    total_pages = int(listing.get("totalPages", 1) or 1)
    rows = []
    for ad in listing.get("ads", []):
        try:
            rows.append(_parse_ad(ad))
        except Exception:
            continue
    return rows, total_pages


def _parse_ad(ad: dict) -> dict:
    map_data = ad.get("map") or {}
    lat, lon = map_data.get("lat"), map_data.get("lon")
    price_node = (ad.get("price") or {}).get("regularPrice") or {}

    area, plot_type = None, ""
    for p in ad.get("params") or []:
        if p.get("key") == "m":
            area = to_float(p.get("value", ""))
        elif p.get("key") == "type":
            plot_type = p.get("value", "")

    return {
        "id": f"olx_{ad.get('id', '')}",
        "tytul": (ad.get("title") or "").strip(),
        "cena_pln": to_float(price_node.get("value")),
        "cena_negocjowalna": price_node.get("negotiable", False),
        "powierzchnia_m2": area,
        "miejscowosc": (ad.get("location") or {}).get("cityName", ""),
        "lat": float(lat) if lat is not None else None,
        "lon": float(lon) if lon is not None else None,
        "gps_dokladny": bool(lat and lon and not map_data.get("radius", 0) > 5),
        "url": ad.get("url", ""),
        "typ": plot_type,
        "data_dodania": (ad.get("createdTime") or "")[:10],
    }


def _fetch_page(url: str, page: int) -> str | None:
    return fetch(url, params={"page": page} if page > 1 else None, referer="https://www.olx.pl/")


def scrape(progress_callback=None) -> pd.DataFrame:
    cities = place_names()
    rows = []
    for i, city in enumerate(cities):
        if progress_callback:
            progress_callback(f"🔍 OLX: {city}…", i / len(cities))

        url = f"{BASE_URL}/{city_slug(city)}/"
        city_rows, total_pages = parse_page(_fetch_page(url, 1))
        for page in range(2, min(MAX_PAGES, total_pages) + 1):
            time.sleep(0.8)
            more, _ = parse_page(_fetch_page(url, page))
            city_rows.extend(more)

        rows.extend(r for r in city_rows if in_liwiec_bbox(r["lat"], r["lon"]))
        time.sleep(0.4)

    return to_dataframe(rows, NAME)
