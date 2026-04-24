"""
Persists listing IDs across scraping sessions so the app can flag
listings that are new since the last run.

Storage: historia_ogloszen.csv  (id, data_pierwszego_widzenia)
The file lives next to the other app files and is excluded from git
via .gitignore so it never gets wiped on redeploy.
"""
import os
from datetime import date

import pandas as pd

_HISTORY_FILE = os.path.join(os.path.dirname(__file__), "historia_ogloszen.csv")


def _load_raw() -> dict:
    """Return {id: first_seen_str} from the CSV, or {} if missing."""
    if not os.path.exists(_HISTORY_FILE):
        return {}
    try:
        df = pd.read_csv(_HISTORY_FILE, dtype=str)
        return dict(zip(df["id"], df["data_pierwszego_widzenia"]))
    except Exception:
        return {}


def _save_raw(history: dict) -> None:
    df = pd.DataFrame(
        [{"id": k, "data_pierwszego_widzenia": v} for k, v in history.items()]
    )
    df.to_csv(_HISTORY_FILE, index=False, encoding="utf-8")


def update_and_mark(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compare df against stored history.

    Adds two columns to df (in-place copy):
      - nowe (bool)  : True if this listing was never seen before today
      - data_pierwszego_widzenia (str): date string when first encountered

    Saves updated history to disk.
    Returns the annotated DataFrame.
    """
    df = df.copy()
    today = date.today().isoformat()

    history = _load_raw()
    new_entries = {}

    first_seen_col = []
    nowe_col = []

    for listing_id in df["id"].astype(str):
        if listing_id in history:
            first_seen_col.append(history[listing_id])
            nowe_col.append(False)
        else:
            first_seen_col.append(today)
            nowe_col.append(True)
            new_entries[listing_id] = today

    df["nowe"] = nowe_col
    df["data_pierwszego_widzenia"] = first_seen_col

    if new_entries:
        history.update(new_entries)
        _save_raw(history)

    return df


def count_new_today(df: pd.DataFrame) -> int:
    """How many listings in df are flagged as new today."""
    if "nowe" not in df.columns:
        return 0
    return int(df["nowe"].sum())
