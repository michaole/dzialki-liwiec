"""Shared HTTP fetching for all portal scrapers."""
import time

import requests

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


def fetch(url: str, *, referer: str, params: dict | None = None,
          retries: int = 3, timeout: int = 20) -> str | None:
    """GET a page as text, retrying with exponential backoff. None on failure."""
    headers = {
        "User-Agent": USER_AGENT,
        "Accept-Language": "pl-PL,pl;q=0.9,en;q=0.8",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Referer": referer,
    }
    for attempt in range(retries):
        try:
            r = requests.get(url, headers=headers, params=params or {}, timeout=timeout)
            if r.status_code == 200:
                return r.text
        except requests.RequestException:
            pass
        time.sleep(2 ** attempt)
    return None
