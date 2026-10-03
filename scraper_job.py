"""
Standalone scraper job for GitHub Actions daily cron.

Runs all portal scrapers, detects new listings vs data/seen_ids.json,
sends email digest, and updates the seen_ids file and the listing history
(data/listings.json) that the static site is built from.

Usage:
    python scraper_job.py

Required env vars:
    GMAIL_USER, GMAIL_APP_PASSWORD, NOTIFY_EMAIL
"""
import json
from pathlib import Path

from liwiec import store
from liwiec.notifier import email_configured, send_new_listings
from liwiec.pipeline import scrape_portals

SEEN_IDS_FILE = Path(__file__).parent / "data" / "seen_ids.json"


def _load_seen() -> set:
    try:
        return set(json.loads(SEEN_IDS_FILE.read_text()))
    except (FileNotFoundError, json.JSONDecodeError):
        return set()


def _save_seen(ids: set) -> None:
    SEEN_IDS_FILE.parent.mkdir(exist_ok=True)
    SEEN_IDS_FILE.write_text(json.dumps(sorted(ids), ensure_ascii=False, indent=2))


def main():
    df = scrape_portals(log=print)
    if df.empty:
        print("✗ Brak ogłoszeń – przerywam.")
        return

    # Portals that returned nothing (blocked, down) keep their listings as they were
    scraped_sources = set(df["zrodlo"])
    df = df[df["na_liwcu"] == True]
    print(f"▶ Łącznie nad Liwcem: {len(df)} ogłoszeń")

    seen = _load_seen()
    current_ids = set(df["id"].astype(str))
    new_df = df[df["id"].astype(str).isin(current_ids - seen)]
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

    history = store.update(store.load(), df, scraped_sources, known_ids=seen)
    store.save(history)
    active = sum(r["active"] for r in history.values())
    print(f"✓ listings.json zaktualizowany ({active} aktywnych, {len(history) - active} zniknęło).")


if __name__ == "__main__":
    main()
