"""Run portal scrapers and merge their results — shared by the app and the daily job."""
from collections.abc import Callable, Iterable

import pandas as pd

from liwiec.sources import SCRAPERS

ProgressCallback = Callable[[str, float], None]


def scrape_portals(portals: Iterable[str] | None = None,
                   progress_callback: ProgressCallback | None = None,
                   log: Callable[[str], None] | None = None) -> pd.DataFrame:
    """
    Scrape the given portals (default: all) and return one DataFrame,
    deduplicated across portals by (tytul, miejscowosc) — the same plot is
    often cross-posted. Empty DataFrame if nothing was found.
    """
    frames = []
    for name in portals or SCRAPERS:
        if log:
            log(f"▶ Scraping {name}…")
        df = SCRAPERS[name](progress_callback=progress_callback)
        if log:
            log(f"  {name}: {len(df)} ogłoszeń")
        if not df.empty:
            frames.append(df)

    if not frames:
        return pd.DataFrame()
    df = pd.concat(frames, ignore_index=True)
    return df.drop_duplicates(subset=["tytul", "miejscowosc"], keep="first")
