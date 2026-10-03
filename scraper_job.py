"""
Standalone scraper job for GitHub Actions daily cron.

Runs all portal scrapers, detects new listings vs data/seen_ids.json,
sends email digest, and updates the seen_ids file.

Usage:
    python scraper_job.py

Required env vars:
    GMAIL_USER, GMAIL_APP_PASSWORD, NOTIFY_EMAIL
"""
import json
from pathlib import Path

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


if __name__ == "__main__":
    main()
