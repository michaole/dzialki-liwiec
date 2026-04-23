import requests
import json
import time
from bs4 import BeautifulSoup
import pandas as pd

from liwiec_places import match_place

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "pl-PL,pl;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Referer": "https://www.otodom.pl/",
}

# Ścieżki gmin na Otodom pokrywające wszystkie miejscowości z miejscowosci_liwiec.csv
# Format: ścieżka po /pl/oferty/sprzedaz/dzialka/
# Odkryte automatycznie przez sprawdzenie redirectów Otodom dla każdej miejscowości z CSV.
SEARCH_PATHS = [
    "mazowieckie/siedlecki/mokobody",       # Mokobody, Pruszyn, Grodzisk (górny bieg)
    "mazowieckie/wegrowski/liw",            # Liw, Jarnice, Borzychy, Paplin, Zawiszyn
    "mazowieckie/wegrowski/wegrow",         # Węgrów, Starawieś, Sekłak
    "mazowieckie/wegrowski/lochow",         # Łochów, Barchów, Wólka Paplińska, Nadkole
    "mazowieckie/siedlecki/siedlce",         # Pruszyn, górny bieg
    "mazowieckie/wyszkowski/wyszkow",       # Kamieńczyk, Świniotop (ujście)
    "mazowieckie/wyszkowski/branszczyk",    # Brańszczyk (ujście)
    "mazowieckie/wolominski/jadow",         # Urle, Starowola, Zawiszyn
]

SUBTYPES = ["building-plot", "recreational"]
MAX_PAGES = 5   # max stron na gminę (36 ogłoszeń/strona)


# ── Nominatim geocoder (fallback for cities not in CSV) ──────────────────────

_geocache: dict = {}


def _geocode_city(city: str):
    """Return (lat, lon) for a Polish city/village name via Nominatim."""
    if not city:
        return None
    key = city.lower().strip()
    if key in _geocache:
        return _geocache[key]

    try:
        url = "https://nominatim.openstreetmap.org/search"
        params = {
            "q": city,
            "countrycodes": "pl",
            "format": "json",
            "limit": 1,
            "addressdetails": 0,
        }
        r = requests.get(url, params=params, headers=NOM_HEADERS, timeout=10)
        results = r.json()
        if results:
            lat = float(results[0]["lat"])
            lon = float(results[0]["lon"])
            _geocache[key] = (lat, lon)
            time.sleep(0.5)   # Nominatim rate-limit: 1 req/s
            return (lat, lon)
    except Exception:
        pass

    _geocache[key] = None
    return None


# ── Otodom scraping ───────────────────────────────────────────────────────────

def _build_url(path: str) -> str:
    """path = e.g. 'mazowieckie/wegrowski/lochow'"""
    return f"https://www.otodom.pl/pl/wyniki/sprzedaz/dzialka/{path}"


def _fetch_html(url, params, retries=3):
    for attempt in range(retries):
        try:
            r = requests.get(url, headers=HEADERS, params=params, timeout=20)
            if r.status_code == 200:
                return r.text
            time.sleep(2 ** attempt)
        except requests.RequestException:
            time.sleep(2 ** attempt)
    return None


def _parse_next_data(html):
    """Extract listings from Otodom's __NEXT_DATA__ JSON.
    Returns (list_of_dicts, total_pages).
    """
    if not html:
        return [], 0

    soup = BeautifulSoup(html, "html.parser")
    tag = soup.find("script", id="__NEXT_DATA__")
    if not tag or not tag.string:
        return [], 0

    try:
        data = json.loads(tag.string)
    except json.JSONDecodeError:
        return [], 0

    # Navigate to searchAds (known path as of 2025-2026)
    try:
        ads = data["props"]["pageProps"]["data"]["searchAds"]
    except (KeyError, TypeError):
        return [], 0

    items = ads.get("items", [])
    pag = ads.get("pagination", {})
    total_pages = int(pag.get("totalPages", 1) or 1)

    results = []
    for item in items:
        try:
            addr = item.get("location", {}).get("address", {})
            city_node = addr.get("city", {})
            city = city_node.get("name", "") if isinstance(city_node, dict) else str(city_node)

            # Province for display
            prov_node = addr.get("province", {})
            province = prov_node.get("name", "") if isinstance(prov_node, dict) else ""

            # County from reverseGeocoding
            rev_locs = item.get("location", {}).get("reverseGeocoding", {}).get("locations", [])
            county_name = ""
            for loc in rev_locs:
                if loc.get("locationLevel") == "county":
                    county_name = loc.get("name", "")
                    break

            price_node = item.get("totalPrice") or {}
            price = _to_float(price_node.get("value"))

            ppm_node = item.get("pricePerSquareMeter") or {}
            price_per_m2_otodom = _to_float(ppm_node.get("value"))

            area = _to_float(item.get("areaInSquareMeters"))

            # URL: slug is like "tytul-dzialki-IDxxxxxx"
            # Correct Otodom format: /pl/oferty/sprzedaz/dzialka/{slug}
            slug = item.get("slug", "")
            full_url = f"https://www.otodom.pl/pl/oferta/{slug}" if slug else ""

            desc = (item.get("shortDescription") or "").strip()[:300]

            results.append({
                "id": str(item.get("id", "")),
                "tytul": item.get("title", "").strip(),
                "opis": desc,
                "cena_pln": price,
                "cena_za_m2_otodom": price_per_m2_otodom,
                "powierzchnia_m2": area,
                "miejscowosc": city,
                "powiat": county_name,
                "url": full_url,
                "typ": item.get("estate", ""),
                "data_dodania": (item.get("dateCreated") or "")[:10],
                "lat": None,   # filled in later by geocoder
                "lon": None,
            })
        except Exception:
            continue

    return results, total_pages


def _to_float(val):
    if val is None:
        return None
    try:
        return float(str(val).replace(" ", "").replace(",", "."))
    except (ValueError, TypeError):
        return None


def _cena_za_m2(row):
    if row.get("cena_za_m2_otodom"):
        return row["cena_za_m2_otodom"]
    if row["cena_pln"] and row["powierzchnia_m2"] and row["powierzchnia_m2"] > 0:
        return round(row["cena_pln"] / row["powierzchnia_m2"])
    return None


def scrape_all(progress_callback=None):
    """
    Scrape Otodom for działki budowlane + rekreacyjne across Liwiec-area counties.
    Assigns coordinates and metadata from miejscowosci_liwiec.csv where available.
    progress_callback(message, fraction) — optional Streamlit progress hook.
    Returns a DataFrame with only listings whose city is in the Liwiec places list.
    """
    all_rows = []
    seen_ids: set = set()

    n = len(SEARCH_PATHS)
    for task_idx, path in enumerate(SEARCH_PATHS):
        label = path.split("/")[-1]   # e.g. "lochow"
        if progress_callback:
            progress_callback(f"📥 Otodom: gmina {label}…", task_idx / n * 0.9)

        url = _build_url(path)
        params = {
            "subType": ",".join(SUBTYPES),
            "limit": 36,
            "page": 1,
            "by": "DEFAULT",
            "direction": "DESC",
            "viewType": "listing",
        }

        html = _fetch_html(url, params)
        rows, total_pages = _parse_next_data(html)
        all_rows.extend(rows)

        pages_to_fetch = min(MAX_PAGES, total_pages)
        for page in range(2, pages_to_fetch + 1):
            time.sleep(0.8)
            params["page"] = page
            html = _fetch_html(url, params)
            page_rows, _ = _parse_next_data(html)
            all_rows.extend(page_rows)

    if progress_callback:
        progress_callback("🔍 Dopasowuję do miejscowości nad Liwcem…", 0.92)

    # Deduplicate by id
    unique_rows = []
    seen_ids = set()
    for row in all_rows:
        if row["id"] not in seen_ids:
            seen_ids.add(row["id"])
            unique_rows.append(row)

    if not unique_rows:
        return pd.DataFrame()

    # Match each listing city against Liwiec places CSV
    # Listings that don't match any CSV place are kept but flagged as "spoza listy"
    for row in unique_rows:
        place = match_place(row["miejscowosc"])
        if place is not None:  # explicit None check — place is a pandas Series
            row["lat"]      = float(place["lat"])
            row["lon"]      = float(place["lon"])
            row["odcinek"]  = place["Odcinek"]
            row["uwagi"]    = place["Uwagi"]
            row["na_liwcu"] = True
        else:
            row["odcinek"]  = "—"
            row["uwagi"]    = ""
            row["na_liwcu"] = False

    df = pd.DataFrame(unique_rows)
    df["cena_za_m2"] = df.apply(_cena_za_m2, axis=1)
    return df
