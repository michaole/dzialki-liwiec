import streamlit as st
import pandas as pd
from datetime import date

from scraper import scrape_all
from olx_scraper import scrape_olx_all
from gratka_scraper import scrape_gratka_all
from liwiec_places import load_places, odcinek_options
from historia import (update_and_mark, count_new_today, get_stats,
                      get_inactive_listings, clear_inactive_listings,
                      get_favorites, set_favorites)
from notifier import send_new_listings, email_configured

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(page_title="Działki nad Liwcem", page_icon="🌊", layout="wide")

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
.block-container { padding-top: 1.2rem; padding-bottom: 1rem; max-width: 1300px; }

div[data-testid="stHorizontalBlock"] .stSelectbox label,
div[data-testid="stHorizontalBlock"] .stMultiSelect label,
div[data-testid="stHorizontalBlock"] .stNumberInput label {
    font-size: 0.78rem; font-weight: 600; color: #5e6e82;
    text-transform: uppercase; letter-spacing: 0.04em;
}
div[data-testid="metric-container"] {
    background: #f8fafd; border: 1px solid #dce6f0;
    border-radius: 12px; padding: 14px 18px;
    box-shadow: 0 1px 4px rgba(0,0,0,0.05);
}
div[data-testid="metric-container"] [data-testid="stMetricValue"] {
    font-size: 1.6rem; font-weight: 700; color: #1565C0;
}
div[data-testid="metric-container"] [data-testid="stMetricLabel"] {
    font-size: 0.78rem; color: #5e6e82;
}
div[data-testid="stHorizontalBlock"] .stButton > button[kind="primary"] {
    background: linear-gradient(135deg, #1565C0, #1976D2);
    border: none; border-radius: 10px; font-weight: 700;
    box-shadow: 0 2px 6px rgba(21,101,192,0.35);
}
div[data-testid="stHorizontalBlock"] .stButton > button[kind="secondary"] {
    border-radius: 10px; font-weight: 600;
}
h3 { color: #1a2c42; margin-top: 0.5rem !important; }
div[data-testid="stDataFrame"] { border-radius: 10px; overflow: hidden; }
hr { border-color: #e0eaf4 !important; margin: 0.6rem 0 !important; }
</style>
""", unsafe_allow_html=True)

# ── Load static data ──────────────────────────────────────────────────────────
places_df = load_places()

if "raw_df" not in st.session_state:
    st.session_state.raw_df = None

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("## 🌊 Działki nad rzeką Liwiec")
st.caption(
    "Ogłoszenia z Otodom, OLX i Gratka filtrowane według miejscowości nad Liwcem. "
    f"Baza zawiera **{len(places_df)}** miejscowości."
)

st.divider()

# ── Filter bar — row 1 ────────────────────────────────────────────────────────
c_src, c_odc, c_price, c_area, c_liwiec, c_new = st.columns([2, 2, 1.6, 1.6, 1.4, 1.4])

with c_src:
    zrodlo_filter = st.multiselect(
        "Źródło", options=["Otodom", "OLX", "Gratka"], default=["Otodom", "OLX", "Gratka"],
    )
with c_odc:
    odcinek = st.selectbox("Odcinek rzeki", options=odcinek_options())
with c_price:
    max_price = st.number_input("Maks. cena (PLN)", min_value=0, value=0, step=10_000,
                                help="0 = bez limitu")
with c_area:
    min_area = st.number_input("Min. pow. (m²)", min_value=0, value=0, step=100,
                               help="0 = bez limitu")
with c_liwiec:
    st.markdown("<div style='margin-top:28px'></div>", unsafe_allow_html=True)
    only_liwiec = st.checkbox("Tylko nad Liwcem", value=True)
with c_new:
    st.markdown("<div style='margin-top:28px'></div>", unsafe_allow_html=True)
    only_new = st.checkbox("🆕 Tylko nowe", value=False)

# ── Filter bar — row 2: buttons ───────────────────────────────────────────────
_, c_btn_all, c_btn1, c_btn2, c_btn3 = st.columns([4, 2.5, 1.3, 1.3, 1.3])

with c_btn_all:
    fetch_all = st.button("⚡ Wszystkie portale", use_container_width=True, type="primary")
with c_btn1:
    fetch_otodom = st.button("Otodom", use_container_width=True, type="secondary")
with c_btn2:
    fetch_olx = st.button("OLX", use_container_width=True, type="secondary")
with c_btn3:
    fetch_gratka = st.button("Gratka", use_container_width=True, type="secondary")

fetch_otodom = fetch_otodom or fetch_all
fetch_olx    = fetch_olx    or fetch_all
fetch_gratka = fetch_gratka or fetch_all
fetch_btn    = fetch_otodom or fetch_olx or fetch_gratka

st.divider()

# ── Scraping ──────────────────────────────────────────────────────────────────
if fetch_btn:
    bar = st.progress(0.0, text="Inicjalizacja…")

    def _cb(msg, frac):
        bar.progress(min(frac, 1.0), text=msg)

    frames = []
    if fetch_otodom:
        df_oto = scrape_all(progress_callback=_cb)
        if not df_oto.empty:
            df_oto["zrodlo"] = "Otodom"
            frames.append(df_oto)
    if fetch_olx:
        df_olx = scrape_olx_all(progress_callback=_cb)
        if not df_olx.empty:
            frames.append(df_olx)
    if fetch_gratka:
        df_gratka = scrape_gratka_all(progress_callback=_cb)
        if not df_gratka.empty:
            frames.append(df_gratka)

    bar.progress(1.0, text="Gotowe!")

    if not frames:
        st.error("Nie pobrano żadnych ogłoszeń. Spróbuj za chwilę.")
    else:
        df_raw = pd.concat(frames, ignore_index=True)
        df_raw = df_raw.drop_duplicates(subset=["tytul", "miejscowosc"], keep="first")
        df_raw = update_and_mark(df_raw)
        st.session_state.raw_df = df_raw
        total     = len(df_raw)
        on_river  = int(df_raw["na_liwcu"].sum())
        new_today = count_new_today(df_raw)
        sources   = ", ".join(df_raw["zrodlo"].unique()) if "zrodlo" in df_raw.columns else ""
        st.success(
            f"Pobrano **{total}** ogłoszeń ({sources}) — "
            f"**{on_river}** z miejscowości nad Liwcem — "
            f"🆕 **{new_today}** nowych od ostatniego scrapowania."
        )

# ── Display ───────────────────────────────────────────────────────────────────
df_raw = st.session_state.raw_df

if df_raw is None:
    st.info("👆 Kliknij **⚡ Wszystkie portale** aby pobrać z Otodom, OLX i Gratka naraz — albo wybierz konkretny portal po prawej.")
    st.stop()

# ── Apply filters ─────────────────────────────────────────────────────────────
df = df_raw.copy()
if zrodlo_filter and "zrodlo" in df.columns:
    df = df[df["zrodlo"].isin(zrodlo_filter)]
if only_liwiec:
    df = df[df["na_liwcu"] == True]
if odcinek != "Wszystkie":
    df = df[df["odcinek"] == odcinek]
if max_price > 0:
    df = df[df["cena_pln"].isna() | (df["cena_pln"] <= max_price)]
if min_area > 0:
    df = df[df["powierzchnia_m2"].isna() | (df["powierzchnia_m2"] >= min_area)]
if only_new and "nowe" in df.columns:
    df = df[df["nowe"] == True]

if len(df) == 0 and len(df_raw) > 0:
    st.warning(
        f"Brak ogłoszeń spełniających kryteria. "
        f"Wszystkich: {len(df_raw)} — nad Liwcem: {int(df_raw['na_liwcu'].sum())}."
    )

# ── Metrics ───────────────────────────────────────────────────────────────────
m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Ogłoszenia (po filtrach)", len(df))
m2.metric("Nad Liwcem", int(df_raw["na_liwcu"].sum()))
m3.metric("Wszystkich pobranych", len(df_raw))
if "nowe" in df.columns:
    m4.metric("🆕 Nowych od ostatniego razu", count_new_today(df))
if len(df) > 0 and df["cena_pln"].notna().any():
    m5.metric("Mediana ceny",
              f"{int(df['cena_pln'].median()):,} PLN".replace(",", " "))

db_stats = get_stats()
if db_stats["total"] > 0:
    st.markdown(
        f"<div style='font-size:12px;color:#78909c;margin:4px 0 0'>"
        f"🗄️ Baza: <b>{db_stats['total']}</b> łącznie &nbsp;·&nbsp; "
        f"<b>{db_stats['active']}</b> aktywnych &nbsp;·&nbsp; "
        f"<b>{db_stats['inactive']}</b> znikniętych &nbsp;·&nbsp; "
        f"<b>{db_stats['price_drops']}</b> z obniżką ceny"
        f"</div>",
        unsafe_allow_html=True,
    )

st.divider()

# ── Action buttons row ────────────────────────────────────────────────────────
_a1, _a2 = st.columns([2, 8])

with _a1:
    send_email_btn = st.button(
        "📧 Wyślij digest",
        use_container_width=True,
        disabled=not email_configured(),
        help="Wysyła email z nowymi ogłoszeniami" if email_configured()
             else "Skonfiguruj GMAIL_USER, GMAIL_APP_PASSWORD i NOTIFY_EMAIL w Secrets",
    )

# ── Email digest trigger ──────────────────────────────────────────────────────
if send_email_btn:
    new_df = df[df.get("nowe", pd.Series(False, index=df.index)) == True] \
             if "nowe" in df.columns else df
    ok = send_new_listings(new_df if not new_df.empty else df)
    if ok:
        st.success("📧 Email wysłany!")
    else:
        st.error("Błąd wysyłki. Sprawdź konfigurację SMTP w Secrets.")

st.divider()

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab_lista, tab_znikniete = st.tabs(["📋 Lista ogłoszeń", "👻 Zniknęły (możliwie sprzedane)"])

with tab_lista:
    today = date.today()
    favorites = get_favorites()

    # Enrich df with computed columns
    df_show = df.copy()

    # Days on market
    if "data_pierwszego_widzenia" in df_show.columns:
        def _days(v):
            try:
                return (today - date.fromisoformat(str(v))).days
            except Exception:
                return None
        df_show["dni_na_rynku"] = df_show["data_pierwszego_widzenia"].apply(_days)
    elif "data_dodania" in df_show.columns:
        def _days(v):
            try:
                return (today - date.fromisoformat(str(v)[:10])).days
            except Exception:
                return None
        df_show["dni_na_rynku"] = df_show["data_dodania"].apply(_days)

    # Favourites
    df_show["⭐"] = df_show["id"].astype(str).apply(lambda i: i in favorites)

    col_map = {
        "⭐":                   "⭐",
        "nowe":                 "🆕",
        "zmiana_ceny":          "Zmiana ceny",
        "zrodlo":               "Źródło",
        "odcinek":              "Odcinek",
        "miejscowosc":          "Miejscowość",
        "tytul":                "Tytuł",
        "cena_pln":             "Cena (PLN)",
        "url":                  "Link",
        "powierzchnia_m2":      "Pow. (m²)",
        "cena_za_m2":           "PLN/m²",
        "dni_na_rynku":         "Dni na rynku",
        "data_pierwszego_widzenia": "Pierwsze widzenie",
    }
    keep = ["id"] + [c for c in col_map if c != "id" and c in df_show.columns]
    df_edit = df_show[keep].copy()
    df_edit = df_edit.rename(columns={k: v for k, v in col_map.items() if k in df_edit.columns})

    # Sort: new first → odcinek → price (numeric, before string formatting)
    sort_keys, sort_asc = [], []
    if "🆕" in df_edit.columns:
        df_edit["🆕"] = df_edit["🆕"].apply(lambda v: "🆕" if bool(v) else "")
        sort_keys.append("🆕"); sort_asc.append(False)
    if "Odcinek" in df_edit.columns:
        sort_keys.append("Odcinek"); sort_asc.append(True)
    if "Cena (PLN)" in df_edit.columns:
        sort_keys.append("Cena (PLN)"); sort_asc.append(True)
    if sort_keys:
        df_edit = df_edit.sort_values(sort_keys, ascending=sort_asc, na_position="last")

    # Format price change
    if "Zmiana ceny" in df_edit.columns:
        def _fmt_delta(v):
            try:
                v = float(v)
            except (TypeError, ValueError):
                return ""
            if pd.isna(v) or abs(v) < 1:
                return ""
            return f"{'🔻' if v < 0 else '🔺'} {int(abs(v)):,}".replace(",", " ")
        df_edit["Zmiana ceny"] = df_edit["Zmiana ceny"].apply(_fmt_delta)

    # Format numbers
    for col in ["Cena (PLN)", "Pow. (m²)", "PLN/m²"]:
        if col in df_edit.columns:
            df_edit[col] = df_edit[col].apply(
                lambda v: f"{int(v):,}".replace(",", " ") if pd.notna(v) else "—")

    # data_editor — ⭐ is the only editable column; id is hidden
    _new_count = count_new_today(df)
    edited = st.data_editor(
        df_edit,
        use_container_width=True,
        hide_index=True,
        height=560,
        column_config={
            "id":    None,
            "⭐":    st.column_config.CheckboxColumn("⭐", help="Oznacz jako ulubione"),
            "🆕":    st.column_config.TextColumn("🆕", width="small"),
            "Link":  st.column_config.LinkColumn("Link", display_text="Otwórz →"),
            "Dni na rynku": st.column_config.NumberColumn("Dni na rynku", help="Ile dni widzimy to ogłoszenie"),
        },
        disabled=[c for c in df_edit.columns if c not in ("⭐", "id")],
        key=f"tbl_{len(df_edit)}_{_new_count}",
    )

    # Save favourite changes
    new_favs = set(edited.loc[edited["⭐"] == True, "id"].astype(str))
    if new_favs != favorites:
        set_favorites(new_favs)
        st.toast("⭐ Ulubione zapisane!")

with tab_znikniete:
    df_inactive = get_inactive_listings()
    if df_inactive.empty:
        st.info(
            "Żadne ogłoszenie nie zniknęło jeszcze z wyników. "
            "Po kolejnym scrapowaniu tutaj pojawią się działki, "
            "które zniknęły z portali — prawdopodobnie sprzedane."
        )
    else:
        _col_info, _col_btn = st.columns([6, 1])
        with _col_btn:
            if st.button("🗑️ Wyczyść listę", type="secondary", use_container_width=True):
                n = clear_inactive_listings()
                st.success(f"Usunięto {n} wpisów.")
                st.rerun()
        st.caption(
            f"Ogłoszenia, które **przestały pojawiać się** w wynikach — "
            f"możliwe, że sprzedane lub wycofane. Łącznie: **{len(df_inactive)}**"
        )
        df_i = df_inactive.copy()
        df_i["cena_pln"] = df_i["cena_pln"].apply(
            lambda v: f"{int(v):,} PLN".replace(",", " ") if pd.notna(v) else "—"
        )
        df_i = df_i.rename(columns={
            "zrodlo": "Źródło", "tytul": "Tytuł", "miejscowosc": "Miejscowość",
            "odcinek": "Odcinek", "cena_pln": "Ostatnia cena", "url": "Link",
            "data_pierwszego_widzenia": "Pierwsze widzenie",
            "data_ostatniego_widzenia": "Ostatnio widziane",
        })
        st.dataframe(
            df_i[[c for c in ["Źródło","Odcinek","Miejscowość","Tytuł","Ostatnia cena",
                               "Link","Pierwsze widzenie","Ostatnio widziane"]
                  if c in df_i.columns]],
            use_container_width=True,
            column_config={"Link": st.column_config.LinkColumn("Link", display_text="Otwórz →")},
            hide_index=True,
            height=400,
        )

# ── Export ────────────────────────────────────────────────────────────────────
csv_out = df.drop(columns=["id"], errors="ignore").to_csv(index=False, encoding="utf-8-sig")
st.download_button("⬇️ Eksportuj CSV", data=csv_out,
                   file_name="dzialki_liwiec.csv", mime="text/csv")
