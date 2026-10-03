"""
Listing history kept in data/listings.json, committed by the nightly job and
published with the static site.

Per listing: current fields, first/last seen dates, whether it is still on
the market, and its price history as [[date, price], ...].
"""
import json
import math
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd

LISTINGS_FILE = Path(__file__).resolve().parent.parent / "data" / "listings.json"

_FIELDS = ["zrodlo", "tytul", "miejscowosc", "odcinek", "url",
           "cena_pln", "powierzchnia_m2", "cena_za_m2", "data_dodania"]


def load(path: Path = LISTINGS_FILE) -> dict[str, dict]:
    try:
        return {r["id"]: r for r in json.loads(path.read_text())["listings"]}
    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        return {}


def save(listings: dict[str, dict], path: Path = LISTINGS_FILE) -> None:
    path.parent.mkdir(exist_ok=True)
    payload = {
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "listings": sorted(listings.values(), key=lambda r: (r["first_seen"], r["id"]), reverse=True),
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=1))


def _clean(v):
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return None
    return v


def _first_seen(row: dict, today: str, known: bool) -> str:
    """For listings first recorded here: today, unless the email job already
    knew them (seen_ids.json), then the portal's own date or yesterday."""
    if not known:
        return today
    listed = row.get("data_dodania")
    if isinstance(listed, str) and len(listed) == 10 and listed < today:
        return listed
    return date.fromordinal(date.fromisoformat(today).toordinal() - 1).isoformat()


def update(listings: dict[str, dict], df: pd.DataFrame, scraped_sources: set[str],
           today: str | None = None, known_ids: set[str] = frozenset()) -> dict[str, dict]:
    """
    Merge one scrape into the history (in place) and return it.
    Listings of `scraped_sources` missing from `df` become inactive; listings
    of portals that returned nothing this run are left as they were.
    """
    today = today or date.today().isoformat()
    current = set()
    for row in df.to_dict("records"):
        lid = str(row["id"])
        current.add(lid)
        fields = {k: _clean(row.get(k)) for k in _FIELDS}
        rec = listings.get(lid)
        if rec is None:
            rec = listings[lid] = {
                "id": lid, "first_seen": _first_seen(fields, today, lid in known_ids), "prices": [],
            }
        rec.update(fields, last_seen=today, active=True)
        price = fields["cena_pln"]
        if price is not None and (not rec["prices"] or abs(rec["prices"][-1][1] - price) > 0.5):
            rec["prices"].append([today, price])

    for lid, rec in listings.items():
        if lid not in current and rec["zrodlo"] in scraped_sources:
            rec["active"] = False
    return listings
