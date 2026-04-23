"""Gratka.pl scraper for działki near the Liwiec river.

Gratka is a Nuxt 3 SSR app. All listing data is embedded in a
<script id="__NUXT_DATA__"> tag as a flat JSON array where integer
values are cross-references to other positions in the same array.
"""
import re
import json
import time
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
    "Referer": "https://gratka.pl/",
}

# Powiats covering the Liwiec valley — each gets its own search pass
SEARCH_REGIONS = [
    "mazowieckie/wegrowski",
    "mazowieckie/siedlecki",
    "mazowieckie/wyszkowski",
    "mazowieckie/wolominski",
]

GRATKA_BASE = "https://gratka.pl/nieruchomosci/dzialki-grunty"
MAX_PAGES = 8   # 35 listings/page → 280 per region max


# ── Nuxt 3 __NUXT_DATA__ resolver ─────────────────────────────────────────────

def _resolve(val, data, depth=0, _seen=None):
    """Recursively resolve Nuxt 3 compact index-reference format."""
    if _seen is None:
        _seen = set()
    if depth > 40:
        return val
    if isinstance(val, int):
        if val in _seen or val < 0 or val >= len(data):
            return val
        _seen = _seen | {val}
        return _resolve(data[val], data, depth + 1, _seen)
    if isinstance(val, list):
        # Nuxt wraps reactive objects as [TypeName, index] — unwrap them
        if (len(val) == 2
                and isinstance(val[0], str)
                and isinstance(val[1], int)):
            return _resolve(val[1], data, depth + 1, _seen)
        return [_resolve(v, data, depth + 1, _seen) for v in val]
    if isinstance(val, dict):
        return {k: _resolve(v, data, depth + 1, _seen) for k, v in val.items()}
    return val


# ── HTTP helpers ──────────────────────────────────────────────────────────────

def _fetch(url: str, page: int = 1, retries: int = 3) -> str | None:
    params = {"strona": page} if page > 1 else {}
    for attempt in range(retries):
        try:
            r = requests.get(url, headers=HEADERS, params=params, timeout=20)
            if r.status_code == 200:
                return r.text
            time.sleep(2 ** attempt)
        except requests.RequestException:
            time.sleep(2 ** attempt)
    return None


# ── Parser ────────────────────────────────────────────────────────────────────

def _parse_gratka(html: str):
    """
    Extract listings from Gratka's __NUXT_DATA__ script tag.
    Returns (list_of_dicts, total_pages).
    """
    if not html:
        return [], 1

    m = re.search(
        r'<script[^>]+id="__NUXT_DATA__"[^>]*>([\s\S]*?)</script>', html
    )
    if not m:
        return [], 1

    try:
        data = json.loads(m.group(1))
    except json.JSONDecodeError:
        return [], 1

    if not isinstance(data, list):
        return [], 1

    rows = []
    total_pages = 1

    for raw in data:
        if not isinstance(raw, dict):
            continue

        # ── Pagination: look for totalCount alongside numberOfPages ──
        if "totalCount" in raw or "numberOfResults" in raw:
            tc = raw.get("totalCount") or raw.get("numberOfResults")
            if isinstance(tc, int) and tc > 35:
                total_pages = max(total_pages, (tc + 34) // 35)

        # ── Listings have an 'idOnFrontend' key ──────────────────────
        if "idOnFrontend" not in raw:
            continue

        try:
            item = _resolve(raw, data)
            if not isinstance(item, dict):
                continue

            id_fe = item.get("idOnFrontend", "")
            if not id_fe or not isinstance(id_fe, str):
                continue

            # Title: prefer advertisementText (short subject line)
            title = (
                item.get("advertisementText")
                or item.get("title")
                or ""
            )

            # Price
            price = None
            price_obj = item.get("price") or {}
            if isinstance(price_obj, dict):
                amt = price_obj.get("amount")
                try:
                    price = float(
                        str(amt).replace(" ", "").replace(",", ".")
                    )
                except (ValueError, TypeError):
                    pass

            # Area — stored as string like "2 472"
            area = None
            area_raw = item.get("area")
            if area_raw is not None:
                try:
                    area = float(
                        str(area_raw).replace(" ", "").replace(",", ".")
                    )
                except (ValueError, TypeError):
                    pass

            # Location: array [voivodeship, county, gmina, city]
            city = ""
            loc = item.get("location") or {}
            if isinstance(loc, dict):
                loc_arr = loc.get("location") or []
                if isinstance(loc_arr, list) and loc_arr:
                    # Last element is most specific
                    city = str(loc_arr[-1]).strip()

            # URL
            url_path = item.get("url", "")
            full_url = (
                f"https://gratka.pl{url_path}" if url_path else ""
            )

            rows.append({
                "id":              f"gratka_{id_fe}",
                "zrodlo":          "Gratka",
                "tytul":           str(title).strip()[:120],
                "cena_pln":        price,
                "powierzchnia_m2": area,
                "miejscowosc":     city,
                "lat":             None,
                "lon":             None,
                "url":             full_url,
                "data_dodania":    (item.get("addedAt") or "")[:10],
            })
        except Exception:
            continue

    return rows, total_pages


# ── Public API ────────────────────────────────────────────────────────────────

def scrape_gratka_all(progress_callback=None):
    """
    Scrape Gratka.pl for działki across Liwiec-area powiats.
    Returns DataFrame with same schema as other scrapers.
    """
    all_rows  = []
    seen_ids  = set()
    n_regions = len(SEARCH_REGIONS)

    for reg_idx, region in enumerate(SEARCH_REGIONS):
        url = f"{GRATKA_BASE}/{region}"

        if progress_callback:
            label = region.split("/")[-1]
            progress_callback(
                f"🔍 Gratka: powiat {label}…",
                reg_idx / n_regions,
            )

        html = _fetch(url, page=1)
        rows, total_pages = _parse_gratka(html)

        pages_to_fetch = min(MAX_PAGES, total_pages)
        for row in rows:
            if row["id"] not in seen_ids:
                seen_ids.add(row["id"])
                all_rows.append(row)

        for page in range(2, pages_to_fetch + 1):
            time.sleep(0.7)
            if progress_callback:
                progress_callback(
                    f"🔍 Gratka: {region.split('/')[-1]} str. {page}/{pages_to_fetch}…",
                    (reg_idx + page / pages_to_fetch) / n_regions,
                )
            more, _ = _parse_gratka(_fetch(url, page=page))
            for row in more:
                if row["id"] not in seen_ids:
                    seen_ids.add(row["id"])
                    all_rows.append(row)

        time.sleep(0.5)

    if not all_rows:
        return pd.DataFrame()

    # Match against Liwiec CSV
    result = []
    for row in all_rows:
        place = match_place(row["miejscowosc"])
        if place is not None:
            row["odcinek"]  = place["Odcinek"]
            row["na_liwcu"] = True
            row["lat"]      = float(place["lat"])
            row["lon"]      = float(place["lon"])
        else:
            row["odcinek"]  = "—"
            row["na_liwcu"] = False
        result.append(row)

    df = pd.DataFrame(result)
    df["cena_za_m2"] = df.apply(
        lambda r: round(r["cena_pln"] / r["powierzchnia_m2"])
        if r.get("cena_pln") and r.get("powierzchnia_m2")
           and r["powierzchnia_m2"] > 0
        else None,
        axis=1,
    )
    return df
