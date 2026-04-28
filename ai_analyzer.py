"""
AI analysis of listing descriptions using Claude.

Reads ANTHROPIC_API_KEY from environment or Streamlit secrets.
Results are cached in SQLite (ai_analiza table) to avoid re-analysing.
"""
import json
import os

import pandas as pd

from historia import save_ai_result, get_ai_results

_MODEL = "claude-haiku-4-5-20251001"

_SYSTEM = """\
Jesteś ekspertem od rynku nieruchomości w Polsce. Analizujesz ogłoszenia \
działek rekreacyjnych i budowlanych nad rzeką Liwiec. \
Odpowiadasz WYŁĄCZNIE JSON-em, bez żadnego dodatkowego tekstu."""

_PROMPT = """\
Przeanalizuj to ogłoszenie działki:

Tytuł: {tytul}
Miejscowość: {miejscowosc}
Cena: {cena}
Powierzchnia: {powierzchnia}
Opis: {opis}

Zwróć JSON w tej strukturze (bez Markdown):
{{
  "score": <liczba 1-5, gdzie 5=świetna okazja, 1=liczne problemy>,
  "pozytywne": ["max 3 krótkie zalety"],
  "flagi": ["max 3 krótkie czerwone flagi lub puste [] jeśli brak"],
  "podsumowanie": "1 zdanie po polsku"
}}

Czerwone flagi to np.: podmokły teren, brak dostępu do drogi, udziały w \
działce, brak mediów, las/bagna, służebności, niejasny status prawny, \
rażąco zawyżona cena."""


def _get_client():
    """Return Anthropic client or None if no API key."""
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        try:
            import streamlit as st
            key = st.secrets.get("ANTHROPIC_API_KEY", "")
        except Exception:
            pass
    if not key:
        return None
    try:
        import anthropic
        return anthropic.Anthropic(api_key=key)
    except ImportError:
        return None


def _analyze_one(client, listing_id: str, tytul: str, miejscowosc: str,
                 cena: str, powierzchnia: str, opis: str) -> dict | None:
    """Call Claude for one listing. Returns parsed dict or None on error."""
    prompt = _PROMPT.format(
        tytul=tytul or "—",
        miejscowosc=miejscowosc or "—",
        cena=cena or "—",
        powierzchnia=powierzchnia or "—",
        opis=(opis or "brak opisu")[:600],
    )
    try:
        resp = client.messages.create(
            model=_MODEL,
            max_tokens=300,
            system=_SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = resp.content[0].text.strip()
        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw)
    except Exception:
        return None


def analyze_new_listings(df: pd.DataFrame,
                         progress_callback=None) -> dict:
    """
    Analyse listings not yet in AI cache.
    Returns updated full results dict {id: {score, pozytywne, flagi, podsumowanie}}.
    """
    client = _get_client()
    if client is None:
        return get_ai_results()

    cached = get_ai_results()
    to_do = df[~df["id"].astype(str).isin(cached)].copy()

    if to_do.empty:
        return cached

    n = len(to_do)
    for i, (_, row) in enumerate(to_do.iterrows()):
        if progress_callback:
            progress_callback(
                f"🤖 AI analizuje {i+1}/{n}: {str(row.get('miejscowosc',''))[:20]}…",
                i / n,
            )

        cena_str = (
            f"{int(row['cena_pln']):,} PLN".replace(",", " ")
            if pd.notna(row.get("cena_pln")) else "—"
        )
        pow_str = (
            f"{int(row['powierzchnia_m2'])} m²"
            if pd.notna(row.get("powierzchnia_m2")) else "—"
        )
        result = _analyze_one(
            client,
            listing_id=str(row["id"]),
            tytul=str(row.get("tytul", "")),
            miejscowosc=str(row.get("miejscowosc", "")),
            cena=cena_str,
            powierzchnia=pow_str,
            opis=str(row.get("opis", "")),
        )
        if result:
            save_ai_result(
                listing_id=str(row["id"]),
                score=int(result.get("score", 3)),
                pozytywne=result.get("pozytywne", []),
                flagi=result.get("flagi", []),
                podsumowanie=result.get("podsumowanie", ""),
            )
            cached[str(row["id"])] = result

    return cached


def score_emoji(score: int | None) -> str:
    if score is None:
        return ""
    return {1: "🔴", 2: "🟠", 3: "🟡", 4: "🟢", 5: "⭐"}.get(int(score), "")
