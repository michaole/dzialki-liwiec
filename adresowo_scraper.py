"""Adresowo.pl scraper for działki near the Liwiec river.

Adresowo is a traditional SSR site. Listings are rendered as HTML cards
with a `data-offer-card` attribute. Price and area are in <span class="font-bold">
elements inside <p class="text-neutral-800">, location in the first
<span class="font-bold"> inside the <a href="/o/..."> link.

Search strategy: scrape by powiat (county) covering the Liwiec valley,
then filter by our liwiec_places list.
"""
import re
import time
import requests
import pandas as pd
from bs4 import BeautifulSoup

from liwiec_places import match_place, load_places

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "pl-PL,pl;q=0.9",
    "Referer": "https://adresowo.pl/",
}

BASE_URL = "https://adresowo.pl"

# Powiaty obejmujące dolinę Liwca
SEARCH_REGIONS = [
    "/dzialki/powiat-wyszkowski/",   # Kamieńczyk, Brańszczyk, Nadkole
    "/dzialki/powiat-wegrowski/",    # Loretto, dolny bieg
    "/dzialki/powiat-siedlecki/",    # ujście Liwca
]

MAX_PAGES = 10  # 39 ogłoszeń/strona → 390 max per region


# ── HTTP helper ───────────────────────────────────────────────────────────────

def _fetch(url: str, retries: int = 3):
    for attempt in range(retries):
        try:
            r = requests.get(url, headers=HEADERS, timeout=20)
            if r.status_code == 200:
                return r.text
            time.sleep(2 ** attempt)
        except requests.RequestException:
            time.sleep(2 ** attempt)
    return None


# ── Parser ────────────────────────────────────────────────────────────────────

def _clean_number(raw: str):
    """'1 598 454' or '1\xa0598\xa0454' → 1598454.0  |  '2,03' → 20300 m²."""
    if not raw:
        return None
    # Remove non-breaking spaces, regular spaces, dots used as thousands sep
    cleaned = raw.replace("\xa0", "").replace(" ", "").replace(".", "")
    # Comma as decimal separator → convert to float
    cleaned = cleaned.replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return None


def _parse_page(html: str):
    """Parse all listing cards from one Adresowo HTML page."""
    if not html:
        return []

    soup = BeautifulSoup(html, "html.parser")
    cards = soup.find_all("div", attrs={"data-offer-card": True})
    listings = []

    for card in cards:
        # ── ID ──────────────────────────────────────────────────────────────
        data_id = card.get("data-id", "")
        if not data_id:
            continue

        # ── URL + Miejscowość ────────────────────────────────────────────────
        a = card.find("a", href=lambda h: h and h.startswith("/o/"))
        if not a:
            continue
        href = a["href"]
        url = BASE_URL + href

        mspan = a.find("span", class_=lambda c: c and "font-bold" in c)
        miejscowosc = mspan.get_text(strip=True) if mspan else ""

        # ── Tytuł (full text of link spans) ─────────────────────────────────
        tytul = a.get_text(separator=" ", strip=True)

        # ── Cena i Powierzchnia ──────────────────────────────────────────────
        # Structure: <p class="...text-neutral-800...">
        #              <span class="font-bold">VALUE</span>
        #              <span class="text-xs ...">UNIT</span>
        #            </p>
        cena_pln = None
        powierzchnia_m2 = None

        paras = card.find_all("p", class_=lambda c: c and "text-neutral-800" in c)
        for p in paras:
            bold = p.find("span", class_=lambda c: c and "font-bold" in c)
            unit_span = p.find("span", class_=lambda c: c and "text-xs" in c)
            if not bold or not unit_span:
                continue
            val_raw = bold.get_text(strip=True)
            unit = unit_span.get_text(strip=True).strip()
            val = _clean_number(val_raw)
            if val is None:
                continue
            if unit == "zł":
                cena_pln = val
            elif unit == "m²":
                powierzchnia_m2 = val
            elif unit == "ha":
                powierzchnia_m2 = val * 10_000  # ha → m²

        listings.append({
            "id":             f"adresowo_{data_id}",
            "tytul":          tytul,
            "miejscowosc":    miejscowosc,
            "cena_pln":       cena_pln,
            "powierzchnia_m2": powierzchnia_m2,
            "cena_za_m2":     round(cena_pln / powierzchnia_m2, 2)
                              if cena_pln and powierzchnia_m2 and powierzchnia_m2 > 0
                              else None,
            "url":            url,
            "zrodlo":         "Adresowo",
        })

    return listings


def _has_next_page(html: str) -> bool:
    """True if the page contains a rel=next link."""
    soup = BeautifulSoup(html, "html.parser")
    return bool(soup.find("link", rel="next"))


def _next_page_url(base_path: str, page: int) -> str:
    """Build paginated URL: /dzialki/powiat-X/ + _l2, _l3, ..."""
    path = base_path.rstrip("/")
    return f"{BASE_URL}{path}/_l{page}"


# ── Public API ────────────────────────────────────────────────────────────────

def scrape_adresowo_region(region_path: str,
                           progress_callback=None) -> list[dict]:
    """Scrape all pages for one region path, return raw listing dicts."""
    all_listings = []

    # Page 1 — base URL
    url = BASE_URL + region_path
    html = _fetch(url)
    if not html:
        return []

    all_listings.extend(_parse_page(html))

    for page in range(2, MAX_PAGES + 1):
        if not _has_next_page(html):
            break
        if progress_callback:
            progress_callback(
                f"Adresowo {region_path} strona {page}…",
                0.5 + page / (MAX_PAGES * 2),
            )
        url = _next_page_url(region_path, page)
        html = _fetch(url)
        if not html:
            break
        all_listings.extend(_parse_page(html))
        time.sleep(0.5)

    return all_listings


def scrape_adresowo_all(progress_callback=None) -> pd.DataFrame:
    """
    Scrape all configured regions, filter to Liwiec towns, return DataFrame.
    Columns: id, tytul, miejscowosc, odcinek, na_liwcu, cena_pln,
             powierzchnia_m2, cena_za_m2, url, zrodlo
    """
    places_df = load_places()
    all_listings = []

    for i, region in enumerate(SEARCH_REGIONS):
        if progress_callback:
            progress_callback(
                f"Adresowo: region {i + 1}/{len(SEARCH_REGIONS)}…",
                i / len(SEARCH_REGIONS),
            )
        listings = scrape_adresowo_region(region, progress_callback)
        all_listings.extend(listings)
        time.sleep(1)

    if not all_listings:
        return pd.DataFrame()

    df = pd.DataFrame(all_listings)
    df = df.drop_duplicates(subset=["id"])

    # Filter + annotate with Liwiec metadata
    rows = []
    for _, row in df.iterrows():
        match = match_place(row["miejscowosc"])
        row = row.copy()
        if match is not None:
            row["na_liwcu"] = True
            row["odcinek"] = match.get("Odcinek", "")
        else:
            row["na_liwcu"] = False
            row["odcinek"] = ""
        rows.append(row)

    result = pd.DataFrame(rows)
    return result


# ── Quick test ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    df = scrape_adresowo_all(progress_callback=lambda msg, _: print(msg))
    print(f"\nWszystkich: {len(df)}")
    on_river = df[df["na_liwcu"] == True]
    print(f"Nad Liwcem: {len(on_river)}")
    if not on_river.empty:
        print(on_river[["miejscowosc", "cena_pln", "powierzchnia_m2", "url"]].to_string())
