"""OLX scraper for działki budowlane/rekreacyjne near the Liwiec river."""
import re
import json
import time
import unicodedata
import requests
import pandas as pd

from liwiec_places import match_place, load_places

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "pl-PL,pl;q=0.9",
    "Referer": "https://www.olx.pl/",
}

OLX_BASE = "https://www.olx.pl/nieruchomosci/dzialki/sprzedaz"
MAX_PAGES = 5

# Bounding box of the Liwiec river area (generous margin)
# Any listing outside this box is from a different region with the same city name
_LAT_MIN, _LAT_MAX = 52.20, 52.70
_LON_MIN, _LON_MAX = 21.40, 22.25


def _in_liwiec_bbox(lat, lon) -> bool:
    if lat is None or lon is None:
        return True   # no GPS — keep it, city-level filtering will handle it
    return _LAT_MIN <= lat <= _LAT_MAX and _LON_MIN <= lon <= _LON_MAX


# ── helpers ───────────────────────────────────────────────────────────────────

_PL_MAP = str.maketrans({
    "ł": "l", "Ł": "L",
    "ą": "a", "ę": "e", "ó": "o",
    "ś": "s", "ź": "z", "ż": "z",
    "ć": "c", "ń": "n",
    "Ą": "A", "Ę": "E", "Ó": "O",
    "Ś": "S", "Ź": "Z", "Ż": "Z",
    "Ć": "C", "Ń": "N",
})

def _city_slug(name: str) -> str:
    """Normalise a Polish place name to OLX URL slug."""
    name = name.translate(_PL_MAP)          # handle Ł/ł and other specials
    nfkd = unicodedata.normalize("NFKD", name.strip().lower())
    ascii_name = "".join(c for c in nfkd if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "-", ascii_name).strip("-")


def _fetch_olx(url: str, page: int = 1, retries: int = 3):
    params = {"page": page} if page > 1 else {}
    for attempt in range(retries):
        try:
            r = requests.get(url, headers=HEADERS, params=params, timeout=20)
            if r.status_code == 200:
                return r.text
            time.sleep(2 ** attempt)
        except requests.RequestException:
            time.sleep(2 ** attempt)
    return None


def _parse_olx_state(html: str):
    """
    Extract listings from OLX's window.__PRERENDERED_STATE__ JS variable.
    Returns (list_of_dicts, total_pages).
    """
    if not html:
        return [], 0

    m = re.search(r'window\.__PRERENDERED_STATE__= ("(?:[^"\\]|\\.)*")', html)
    if not m:
        return [], 0

    try:
        inner = json.loads(m.group(1))   # unescape outer string
        data  = json.loads(inner)         # parse actual JSON
        listing = data["listing"]["listing"]
    except (json.JSONDecodeError, KeyError, TypeError):
        return [], 0

    total_pages = int(listing.get("totalPages", 1) or 1)
    ads = listing.get("ads", [])

    rows = []
    for ad in ads:
        try:
            # GPS — OLX provides exact coordinates!
            map_data = ad.get("map") or {}
            lat = map_data.get("lat")
            lon = map_data.get("lon")
            gps_exact = bool(lat and lon and not map_data.get("radius", 0) > 5)

            # Price
            price_node = (ad.get("price") or {}).get("regularPrice") or {}
            price = price_node.get("value")
            negotiable = price_node.get("negotiable", False)

            # Area from params
            area = None
            plot_type = ""
            for p in ad.get("params") or []:
                if p.get("key") == "m":
                    try:
                        area = float(str(p.get("value", "")).replace(" ", "").replace(",", "."))
                    except ValueError:
                        pass
                if p.get("key") == "type":
                    plot_type = p.get("value", "")

            # Location
            loc = ad.get("location") or {}
            city = loc.get("cityName", "")

            rows.append({
                "id":          f"olx_{ad.get('id', '')}",
                "zrodlo":      "OLX",
                "tytul":       (ad.get("title") or "").strip(),
                "cena_pln":    float(price) if price is not None else None,
                "cena_negocjowalna": negotiable,
                "powierzchnia_m2": area,
                "miejscowosc": city,
                "lat":         float(lat) if lat is not None else None,
                "lon":         float(lon) if lon is not None else None,
                "gps_dokladny": gps_exact,
                "url":         ad.get("url", ""),
                "typ":         plot_type,
                "data_dodania": (ad.get("createdTime") or "")[:10],
            })
        except Exception:
            continue

    return rows, total_pages


def _scrape_city(city_name: str):
    """Scrape OLX listings for one city. Returns list of raw dicts."""
    slug = _city_slug(city_name)
    url  = f"{OLX_BASE}/{slug}/"

    html = _fetch_olx(url)
    rows, total_pages = _parse_olx_state(html)

    pages_to_fetch = min(MAX_PAGES, total_pages)
    for page in range(2, pages_to_fetch + 1):
        time.sleep(0.8)
        more, _ = _parse_olx_state(_fetch_olx(url, page=page))
        rows.extend(more)

    return rows


# ── public API ────────────────────────────────────────────────────────────────

def scrape_olx_all(progress_callback=None):
    """
    Scrape OLX for działki in all CSV Liwiec places.
    Returns DataFrame with same schema as Otodom scraper.
    """
    places_df = load_places()
    all_rows   = []
    seen_ids   = set()

    cities = places_df["Nazwa"].tolist()
    n = len(cities)

    for i, city in enumerate(cities):
        if progress_callback:
            progress_callback(f"🔍 OLX: {city}…", i / n)

        rows = _scrape_city(city)

        # Filter: only listings in the Liwiec geographic bbox + city match
        for row in rows:
            if row["id"] in seen_ids:
                continue
            seen_ids.add(row["id"])

            # Discard listings from a different region with the same city name
            if not _in_liwiec_bbox(row["lat"], row["lon"]):
                continue

            place = match_place(row["miejscowosc"])
            if place is not None:
                row["odcinek"]  = place["Odcinek"]
                row["na_liwcu"] = True
                # Use listing GPS if available, otherwise fall back to CSV coords
                if row["lat"] is None or row["lon"] is None:
                    row["lat"] = float(place["lat"])
                    row["lon"] = float(place["lon"])
            else:
                row["odcinek"]  = "—"
                row["na_liwcu"] = False

            all_rows.append(row)

        time.sleep(0.4)

    if not all_rows:
        return pd.DataFrame()

    df = pd.DataFrame(all_rows)
    df["cena_za_m2"] = df.apply(
        lambda r: round(r["cena_pln"] / r["powierzchnia_m2"])
        if r.get("cena_pln") and r.get("powierzchnia_m2") and r["powierzchnia_m2"] > 0
        else None,
        axis=1,
    )
    return df
