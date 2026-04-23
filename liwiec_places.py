"""
Utilities for matching Otodom listing cities against the known
Liwiec-bank places from miejscowosci_liwiec.csv.
"""
import os
import unicodedata
import pandas as pd

_CSV_PATH = os.path.join(os.path.dirname(__file__), "miejscowosci_liwiec.csv")


def _normalize(name: str) -> str:
    """Lowercase + strip accents for fuzzy comparison."""
    nfkd = unicodedata.normalize("NFKD", name.strip().lower())
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def load_places() -> pd.DataFrame:
    """Return DataFrame with columns: Nazwa, Odcinek, lat, lon, Uwagi, _key."""
    df = pd.read_csv(_CSV_PATH)
    df = df.rename(columns={
        "Szerokość_geo": "lat",
        "Długość_geo":   "lon",
    })
    df["_key"] = df["Nazwa"].apply(_normalize)
    return df


# Build lookup dict once at import time
_PLACES_DF = load_places()
_LOOKUP: dict = {row["_key"]: row for _, row in _PLACES_DF.iterrows()}


# Manual aliases: Otodom spelling variants → normalised CSV key
# Add here when Otodom uses a different name than the CSV
_ALIASES: dict = {
    "pruszyn-pienki":  "pruszyn",
    "pruszyn pienki":  "pruszyn",
    "wyszkow wegrowski": "wyszkow wegrowski",  # explicit – never match bare "wyszkow"
}


def match_place(city_name: str):
    """
    Match an Otodom city name against the Liwiec places list.
    Returns the matching DataFrame row (Series) or None.
    Uses exact matching only (+ manual aliases) to avoid false positives
    like 'Wyszków' (city on Bug) matching 'Wyszków Węgrowski' (village on Liwiec).
    """
    if not city_name:
        return None
    key = _normalize(city_name)

    # 1. Check alias table first
    alias_key = _ALIASES.get(key)
    if alias_key and alias_key in _LOOKUP:
        return _LOOKUP[alias_key]

    # 2. Exact match
    if key in _LOOKUP:
        return _LOOKUP[key]

    return None


def all_place_names() -> list:
    return _PLACES_DF["Nazwa"].tolist()


def odcinek_options() -> list:
    return ["Wszystkie"] + sorted(_PLACES_DF["Odcinek"].unique().tolist())
