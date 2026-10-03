"""
Known Liwiec-bank places from miejscowosci_liwiec.csv and matching portal
city names against them.
"""
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

CSV_PATH = Path(__file__).resolve().parent.parent / "miejscowosci_liwiec.csv"


@dataclass(frozen=True)
class Place:
    nazwa: str
    odcinek: str
    lat: float
    lon: float
    uwagi: str


def normalize(name: str) -> str:
    """Lowercase + strip accents for comparison ('Nakieł' → 'nakiel')."""
    # NFKD does not decompose ł, so map it explicitly
    nfkd = unicodedata.normalize("NFKD", name.strip().lower().replace("ł", "l"))
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def load_places() -> pd.DataFrame:
    """Return DataFrame with columns: Nazwa, Odcinek, lat, lon, Uwagi."""
    df = pd.read_csv(CSV_PATH, sep=";")
    if len(df.columns) < 3:          # file saved with comma separator
        df = pd.read_csv(CSV_PATH)

    lat_names = {"Szerokosc_geo", "Szerokość_geo", "Szerokosc geo"}
    lon_names = {"Dlugosc_geo", "Długość_geo", "Dlugosc geo"}
    rename = {}
    for col in df.columns:
        if col in lat_names:
            rename[col] = "lat"
        elif col in lon_names:
            rename[col] = "lon"
    return df.rename(columns=rename)


_PLACES_DF = load_places()
_LOOKUP: dict[str, Place] = {
    normalize(r["Nazwa"]): Place(
        nazwa=r["Nazwa"],
        odcinek=r["Odcinek"],
        lat=float(r["lat"]),
        lon=float(r["lon"]),
        uwagi="" if pd.isna(r.get("Uwagi")) else str(r["Uwagi"]),
    )
    for _, r in _PLACES_DF.iterrows()
}

# Portal spelling variants → normalised CSV key
_ALIASES: dict[str, str] = {
    "bransczczyk-nakiel": "branszczyk-nakiel",
}


def match_place(city_name: str) -> Place | None:
    """
    Match a portal city name against the Liwiec places list.
    Exact matching only (+ manual aliases) to avoid false positives
    like 'Wyszków' (city on Bug) matching 'Wyszków Węgrowski' (village on Liwiec).
    """
    if not city_name:
        return None
    key = normalize(city_name)
    return _LOOKUP.get(_ALIASES.get(key, key))


def place_names() -> list[str]:
    return _PLACES_DF["Nazwa"].tolist()


def odcinek_options() -> list[str]:
    return ["Wszystkie"] + sorted(_PLACES_DF["Odcinek"].unique().tolist())
