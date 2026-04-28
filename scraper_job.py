"""
Standalone scraper job for GitHub Actions daily cron.

Runs all three scrapers, detects new listings vs data/seen_ids.json,
sends email digest, and updates the seen_ids file.

Usage:
    python scraper_job.py

Required env vars:
    GMAIL_USER, GMAIL_APP_PASSWORD, NOTIFY_EMAIL
"""
import json
import os
import sys
from pathlib import Path

import pandas as pd

# ── Make sure project root is in path ────────────────────────────────────────
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from scraper import scrape_all
from olx_scraper import scrape_olx_all
from gratka_scraper import scrape_gratka_all
from notifier import send_new_listings, email_configured

SEEN_IDS_FILE = ROOT / "data" / "seen_ids.json"


def _load_seen() -> set:
    if SEEN_IDS_FILE.exists():
        try:
            return set(json.loads(SEEN_IDS_FILE.read_text()))
        except Exception:
            pass
    return set()


def _save_seen(ids: set) -> None:
    SEEN_IDS_FILE.parent.mkdir(exist_ok=True)
    SEEN_IDS_FILE.write_text(json.dumps(sorted(ids), ensure_ascii=False, indent=2))


def main():
    print("▶ Scraping Otodom…")
    frames = []

    df_oto = scrape_all()
    if not df_oto.empty:
        df_oto["zrodlo"] = "Otodom"
        frames.append(df_oto)
        print(f"  Otodom: {len(df_oto)} ogłoszeń")

    print("▶ Scraping OLX…")
    df_olx = scrape_olx_all()
    if not df_olx.empty:
        frames.append(df_olx)
        print(f"  OLX: {len(df_olx)} ogłoszeń")

    print("▶ Scraping Gratka…")
    df_gratka = scrape_gratka_all()
    if not df_gratka.empty:
        frames.append(df_gratka)
        print(f"  Gratka: {len(df_gratka)} ogłoszeń")

    if not frames:
        print("✗ Brak ogłoszeń – przerywam.")
        return

    df = pd.concat(frames, ignore_index=True)
    df = df.drop_duplicates(subset=["tytul", "miejscowosc"], keep="first")
    df = df[df["na_liwcu"] == True]       # only Liwiec towns
    print(f"▶ Łącznie nad Liwcem: {len(df)} ogłoszeń")

    seen = _load_seen()
    current_ids = set(df["id"].astype(str))
    new_ids = current_ids - seen
    new_df = df[df["id"].astype(str).isin(new_ids)]
    print(f"▶ Nowych: {len(new_df)}")

    if new_df.empty:
        print("✓ Brak nowych ogłoszeń – email nie wysłany.")
    elif not email_configured():
        print("⚠ Email nie skonfigurowany (brak GMAIL_USER/GMAIL_APP_PASSWORD/NOTIFY_EMAIL).")
    else:
        ok = send_new_listings(new_df)
        print("✓ Email wysłany." if ok else "✗ Błąd wysyłki emaila.")

    _save_seen(seen | current_ids)
    print("✓ seen_ids.json zaktualizowany.")


if __name__ == "__main__":
    main()
