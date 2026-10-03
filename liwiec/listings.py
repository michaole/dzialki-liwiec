"""
Common listing schema shared by all portal scrapers.

Each scraper produces raw row dicts with at least:
    id, tytul, miejscowosc, cena_pln, powierzchnia_m2, url
and optionally: lat, lon, cena_za_m2, opis, typ, data_dodania, ...

`to_dataframe` turns them into one consistent DataFrame: deduplicated by id,
annotated with Liwiec place metadata and price per m².
"""
import pandas as pd

from liwiec.places import match_place

COLUMNS = [
    "id", "zrodlo", "tytul", "miejscowosc", "cena_pln", "powierzchnia_m2",
    "cena_za_m2", "url", "lat", "lon", "na_liwcu", "odcinek", "uwagi",
]


def to_float(val) -> float | None:
    """'1 598 454' / '1\xa0598,5' / 2472 → float, None if unparseable."""
    if val is None:
        return None
    try:
        return float(str(val).replace("\xa0", "").replace(" ", "").replace(",", "."))
    except (ValueError, TypeError):
        return None


def price_per_m2(price, area) -> float | None:
    if price and area and area > 0:
        return round(price / area)
    return None


def annotate(row: dict) -> dict:
    """Add na_liwcu / odcinek / uwagi and fall back to the place's coordinates."""
    place = match_place(row.get("miejscowosc", ""))
    row.setdefault("lat", None)
    row.setdefault("lon", None)
    if place is None:
        row.update(na_liwcu=False, odcinek="—", uwagi="")
        return row
    row.update(na_liwcu=True, odcinek=place.odcinek, uwagi=place.uwagi)
    if row["lat"] is None or row["lon"] is None:
        row["lat"], row["lon"] = place.lat, place.lon
    return row


def to_dataframe(rows: list[dict], zrodlo: str) -> pd.DataFrame:
    seen, unique = set(), []
    for row in rows:
        if row["id"] in seen:
            continue
        seen.add(row["id"])
        row["zrodlo"] = zrodlo
        if not row.get("cena_za_m2"):
            row["cena_za_m2"] = price_per_m2(row.get("cena_pln"), row.get("powierzchnia_m2"))
        unique.append(annotate(row))

    if not unique:
        return pd.DataFrame(columns=COLUMNS)
    df = pd.DataFrame(unique)
    extra = [c for c in df.columns if c not in COLUMNS]
    return df.reindex(columns=COLUMNS + extra)   # missing optional fields → NaN
