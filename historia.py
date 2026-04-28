"""
Persistent listing history backed by SQLite.

DB file: historia_ogloszen.db  (excluded from git via .gitignore)

Tables
------
ogloszenia          — one row per unique listing, upserted on every scrape
historia_cen        — one row per (id, date) whenever price changes

New features vs CSV:
  • Detects price drops / increases
  • Flags listings that disappeared from search (possibly sold)
  • Tracks first & last seen dates per listing
"""
import os
import sqlite3
from contextlib import contextmanager
from datetime import date

import pandas as pd

_DB_PATH = os.path.join(os.path.dirname(__file__), "historia_ogloszen.db")

_DDL = """
CREATE TABLE IF NOT EXISTS ogloszenia (
    id                       TEXT PRIMARY KEY,
    zrodlo                   TEXT,
    tytul                    TEXT,
    miejscowosc              TEXT,
    odcinek                  TEXT,
    na_liwcu                 INTEGER,
    url                      TEXT,
    cena_pln                 REAL,
    powierzchnia_m2          REAL,
    data_pierwszego_widzenia TEXT NOT NULL,
    data_ostatniego_widzenia TEXT NOT NULL,
    aktywne                  INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS historia_cen (
    id          TEXT    NOT NULL,
    data        TEXT    NOT NULL,
    cena_pln    REAL,
    PRIMARY KEY (id, data)
);

CREATE TABLE IF NOT EXISTS ulubione (
    id           TEXT PRIMARY KEY,
    data_dodania TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ai_analiza (
    id            TEXT PRIMARY KEY,
    score         INTEGER,
    pozytywne     TEXT,
    flagi         TEXT,
    podsumowanie  TEXT,
    data_analizy  TEXT NOT NULL
);
"""


@contextmanager
def _db():
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _ensure_schema():
    with _db() as conn:
        conn.executescript(_DDL)


# ── Public API ────────────────────────────────────────────────────────────────

def update_and_mark(df: pd.DataFrame) -> pd.DataFrame:
    """
    Upsert all scraped listings into the DB, then annotate df with:
      - nowe          (bool)  : first seen today
      - zmiana_ceny   (float) : price delta vs previous scrape (None = no change)
      - data_pierwszego_widzenia (str)

    Also marks listings absent from this scrape as inactive (aktywne=0).
    Returns annotated copy of df.
    """
    _ensure_schema()
    df = df.copy()
    today = date.today().isoformat()
    current_ids = set(df["id"].astype(str))

    with _db() as conn:
        # ── Load existing records ────────────────────────────────────────
        existing = {
            row["id"]: dict(row)
            for row in conn.execute("SELECT * FROM ogloszenia").fetchall()
        }

        nowe_col          = []
        zmiana_ceny_col   = []
        first_seen_col    = []

        rows_to_upsert    = []
        prices_to_log     = []

        for _, row in df.iterrows():
            lid       = str(row["id"])
            cena      = row.get("cena_pln")
            cena_val  = float(cena) if pd.notna(cena) else None
            area_val  = float(row["powierzchnia_m2"]) if pd.notna(row.get("powierzchnia_m2")) else None

            if lid in existing:
                rec           = existing[lid]
                first_seen    = rec["data_pierwszego_widzenia"]
                is_new        = (first_seen == today)

                # Detect price change
                old_price     = rec["cena_pln"]
                if (old_price is not None
                        and cena_val is not None
                        and abs(old_price - cena_val) > 0.5):
                    delta = cena_val - old_price
                    prices_to_log.append((lid, today, cena_val))
                else:
                    delta = None

                zmiana_ceny_col.append(delta)
            else:
                first_seen = today
                is_new     = True
                delta      = None
                zmiana_ceny_col.append(None)
                prices_to_log.append((lid, today, cena_val))

            nowe_col.append(is_new)
            first_seen_col.append(first_seen)

            rows_to_upsert.append((
                lid,
                str(row.get("zrodlo", "")),
                str(row.get("tytul", ""))[:200],
                str(row.get("miejscowosc", "")),
                str(row.get("odcinek", "")),
                1 if row.get("na_liwcu") else 0,
                str(row.get("url", "")),
                cena_val,
                area_val,
                first_seen,
                today,
                1,   # aktywne
            ))

        # ── Upsert current listings ──────────────────────────────────────
        conn.executemany("""
            INSERT INTO ogloszenia
                (id, zrodlo, tytul, miejscowosc, odcinek, na_liwcu, url,
                 cena_pln, powierzchnia_m2,
                 data_pierwszego_widzenia, data_ostatniego_widzenia, aktywne)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(id) DO UPDATE SET
                tytul                    = excluded.tytul,
                url                      = excluded.url,
                cena_pln                 = excluded.cena_pln,
                powierzchnia_m2          = excluded.powierzchnia_m2,
                data_ostatniego_widzenia = excluded.data_ostatniego_widzenia,
                aktywne                  = 1
        """, rows_to_upsert)

        # ── Log price history ────────────────────────────────────────────
        if prices_to_log:
            conn.executemany(
                "INSERT OR IGNORE INTO historia_cen (id, data, cena_pln) VALUES (?,?,?)",
                prices_to_log,
            )

        # ── Mark absent listings as inactive ────────────────────────────
        absent_ids = [
            (eid,) for eid in existing if eid not in current_ids
        ]
        if absent_ids:
            conn.executemany(
                "UPDATE ogloszenia SET aktywne=0 WHERE id=?",
                absent_ids,
            )

    df["nowe"]                      = nowe_col
    df["zmiana_ceny"]               = zmiana_ceny_col
    df["data_pierwszego_widzenia"]  = first_seen_col
    return df


def count_new_today(df: pd.DataFrame) -> int:
    """Count listings flagged as new in df."""
    if "nowe" not in df.columns:
        return 0
    return int((df["nowe"] == True).sum())


def get_stats() -> dict:
    """
    Return summary stats from the DB for display in the sidebar / info panel.
    """
    _ensure_schema()
    with _db() as conn:
        total = conn.execute(
            "SELECT COUNT(*) FROM ogloszenia"
        ).fetchone()[0]
        active = conn.execute(
            "SELECT COUNT(*) FROM ogloszenia WHERE aktywne=1"
        ).fetchone()[0]
        inactive = total - active
        price_drops = conn.execute("""
            SELECT COUNT(DISTINCT h.id)
            FROM historia_cen h
            JOIN (
                SELECT id, MIN(data) AS first_date, MAX(data) AS last_date
                FROM historia_cen GROUP BY id HAVING COUNT(*) > 1
            ) multi ON h.id = multi.id
            JOIN historia_cen h2
                ON h.id = h2.id AND h2.data = multi.last_date
            JOIN historia_cen h1
                ON h.id = h1.id AND h1.data = multi.first_date
            WHERE h2.cena_pln < h1.cena_pln
        """).fetchone()[0]

    return {
        "total":       total,
        "active":      active,
        "inactive":    inactive,
        "price_drops": price_drops,
    }


def get_price_history(listing_id: str) -> pd.DataFrame:
    """Return price history for a single listing (for charting)."""
    _ensure_schema()
    with _db() as conn:
        rows = conn.execute(
            "SELECT data, cena_pln FROM historia_cen WHERE id=? ORDER BY data",
            (listing_id,),
        ).fetchall()
    if not rows:
        return pd.DataFrame(columns=["data", "cena_pln"])
    return pd.DataFrame([dict(r) for r in rows])


def clear_inactive_listings() -> int:
    """Delete all inactive listings from the DB. Returns number of deleted rows."""
    _ensure_schema()
    with _db() as conn:
        n = conn.execute(
            "SELECT COUNT(*) FROM ogloszenia WHERE aktywne=0"
        ).fetchone()[0]
        conn.execute("DELETE FROM ogloszenia WHERE aktywne=0")
    return n


def get_inactive_listings() -> pd.DataFrame:
    """Return listings that disappeared from search results (possibly sold)."""
    _ensure_schema()
    with _db() as conn:
        rows = conn.execute("""
            SELECT id, zrodlo, tytul, miejscowosc, odcinek,
                   cena_pln, url,
                   data_pierwszego_widzenia, data_ostatniego_widzenia
            FROM   ogloszenia
            WHERE  aktywne = 0
            ORDER  BY data_ostatniego_widzenia DESC
        """).fetchall()
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame([dict(r) for r in rows])


# ── Favourites ────────────────────────────────────────────────────────────────

def get_favorites() -> set:
    """Return set of favourite listing IDs."""
    _ensure_schema()
    with _db() as conn:
        rows = conn.execute("SELECT id FROM ulubione").fetchall()
    return {r["id"] for r in rows}


def set_favorites(ids: set) -> None:
    """Replace the entire favourites set with the given IDs."""
    _ensure_schema()
    with _db() as conn:
        conn.execute("DELETE FROM ulubione")
        today = date.today().isoformat()
        conn.executemany(
            "INSERT OR IGNORE INTO ulubione (id, data_dodania) VALUES (?,?)",
            [(lid, today) for lid in ids],
        )


# ── AI analysis ───────────────────────────────────────────────────────────────

def save_ai_result(listing_id: str, score: int,
                   pozytywne: list, flagi: list, podsumowanie: str) -> None:
    """Persist AI analysis result for one listing."""
    import json
    _ensure_schema()
    today = date.today().isoformat()
    with _db() as conn:
        conn.execute("""
            INSERT OR REPLACE INTO ai_analiza
                (id, score, pozytywne, flagi, podsumowanie, data_analizy)
            VALUES (?,?,?,?,?,?)
        """, (
            listing_id, score,
            json.dumps(pozytywne, ensure_ascii=False),
            json.dumps(flagi,     ensure_ascii=False),
            podsumowanie, today,
        ))


def get_ai_results() -> dict:
    """Return {id: {score, pozytywne, flagi, podsumowanie}} from cache."""
    import json
    _ensure_schema()
    with _db() as conn:
        rows = conn.execute(
            "SELECT id, score, pozytywne, flagi, podsumowanie FROM ai_analiza"
        ).fetchall()
    out = {}
    for r in rows:
        out[r["id"]] = {
            "score":        r["score"],
            "pozytywne":    json.loads(r["pozytywne"] or "[]"),
            "flagi":        json.loads(r["flagi"]     or "[]"),
            "podsumowanie": r["podsumowanie"] or "",
        }
    return out
