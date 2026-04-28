"""
AI analysis of listing descriptions using Claude.

Reads ANTHROPIC_API_KEY from environment or Streamlit secrets.
Results are cached in SQLite (ai_analiza table) to avoid re-analysing.
"""
import json
import os

import pandas as pd

from historia import save_ai_result, get_ai_results

_MODEL = "claude-haiku-4-5"

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


def _get_api_key():
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        try:
            import streamlit as st
            key = st.secrets.get("ANTHROPIC_API_KEY", "")
        except Exception:
            pass
    return key


def _get_client():
    """Return (client, error_str). client is None on failure."""
    key = _get_api_key()
    if not key:
        return None, "Brak klucza ANTHROPIC_API_KEY w Streamlit Secrets"
    try:
        import anthropic
    except ImportError:
        return None, "Brak biblioteki anthropic — dodaj do requirements.txt"
    try:
        client = anthropic.Anthropic(api_key=key)
        return client, None
    except Exception as e:
        return None, f"Błąd inicjalizacji klienta Anthropic: {e}"


def _analyze_one(client, tytul, miejscowosc, cena, powierzchnia, opis):
    """Call Claude for one listing. Returns (dict, error_str)."""
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
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw), None
    except Exception as e:
        return None, str(e)


def analyze_new_listings(df, progress_callback=None):
    """
    Analyse listings not yet in AI cache.
    Returns (results_dict, error_str).
    results_dict: {id: {score, pozytywne, flagi, podsumowanie}}
    error_str: None on success, message on failure
    """
    client, err = _get_client()
    if client is None:
        return get_ai_results(), err

    cached = get_ai_results()
    to_do = df[~df["id"].astype(str).isin(cached)].copy()

    if to_do.empty:
        return cached, None

    n = len(to_do)
    errors = []

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

        result, err = _analyze_one(
            client,
            tytul=str(row.get("tytul", "")),
            miejscowosc=str(row.get("miejscowosc", "")),
            cena=cena_str,
            powierzchnia=pow_str,
            opis=str(row.get("opis", "")),
        )

        if result:
            lid = str(row["id"])
            save_ai_result(
                listing_id=lid,
                score=int(result.get("score", 3)),
                pozytywne=result.get("pozytywne", []),
                flagi=result.get("flagi", []),
                podsumowanie=result.get("podsumowanie", ""),
            )
            cached[lid] = result
        else:
            errors.append(f"[{row.get('tytul','?')[:30]}]: {err}")
            # Stop after first error — no point burning quota on repeated failures
            break

    if errors:
        return cached, "\n".join(errors)
    return cached, None


def score_emoji(score) -> str:
    if score is None:
        return ""
    try:
        return {1: "🔴", 2: "🟠", 3: "🟡", 4: "🟢", 5: "⭐"}.get(int(score), "")
    except Exception:
        return ""
