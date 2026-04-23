import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium

from geo_utils import get_liwiec_geometry, distance_to_liwiec_m, liwiec_coords_for_map
from scraper import scrape_all
from olx_scraper import scrape_olx_all
from liwiec_places import load_places, odcinek_options


def _render_empty_map(liwiec_geom, places_df):
    m = folium.Map(location=[52.46, 21.85], zoom_start=10, tiles="OpenStreetMap")
    for segment in liwiec_coords_for_map(liwiec_geom):
        folium.PolyLine(segment, color="#1565C0", weight=4, opacity=0.85,
                        tooltip="Rzeka Liwiec").add_to(m)
    # Pin known places
    for _, p in places_df.iterrows():
        folium.CircleMarker(
            location=[p["lat"], p["lon"]], radius=5,
            color="#43A047", fill=True, fill_color="#43A047", fill_opacity=0.7,
            tooltip=f"{p['Nazwa']} ({p['Odcinek']})",
        ).add_to(m)
    st_folium(m, use_container_width=True, height=500, returned_objects=[])


st.set_page_config(page_title="Działki nad Liwcem", page_icon="🌊", layout="wide")
st.title("🌊 Działki nad rzeką Liwiec")
st.caption("Ogłoszenia z Otodom filtrowane według Twojej listy miejscowości nad Liwcem.")

# ── Load static data ──────────────────────────────────────────────────────────
places_df = load_places()

# ── Session state ─────────────────────────────────────────────────────────────
if "raw_df" not in st.session_state:
    st.session_state.raw_df = None
if "liwiec_geom" not in st.session_state:
    st.session_state.liwiec_geom = None

if st.session_state.liwiec_geom is None:
    st.session_state.liwiec_geom = get_liwiec_geometry()
liwiec_geom = st.session_state.liwiec_geom

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Filtry")

    zrodlo_filter = st.multiselect(
        "Źródło", options=["Otodom", "OLX"], default=["Otodom", "OLX"]
    )

    only_liwiec = st.checkbox(
        "Tylko miejscowości z listy (nad Liwcem)",
        value=True,
        help="Odznacz, żeby zobaczyć też ogłoszenia z okolic (spoza listy CSV).",
    )

    odcinek = st.selectbox("Odcinek rzeki", options=odcinek_options())

    max_price = st.number_input("Maks. cena (PLN, 0 = bez limitu)",
                                min_value=0, value=0, step=10000)
    min_area  = st.number_input("Min. powierzchnia (m²)",
                                min_value=0, value=0, step=100)

    st.divider()
    col_oto, col_olx = st.columns(2)
    fetch_otodom = col_oto.button("🔄 Otodom", use_container_width=True, type="primary")
    fetch_olx    = col_olx.button("🔄 OLX",    use_container_width=True)
    fetch_btn    = fetch_otodom or fetch_olx   # backwards compat
    st.caption("Pobieranie zajmuje ~1–2 minuty.")

    st.divider()
    st.caption(f"📍 Miejscowości w bazie: **{len(places_df)}**")
    with st.expander("Pokaż listę"):
        for _, p in places_df.iterrows():
            st.markdown(f"**{p['Nazwa']}** — {p['Odcinek']}")

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

    bar.progress(1.0, text="Gotowe!")

    if not frames:
        st.error("Nie pobrano żadnych ogłoszeń. Spróbuj za chwilę.")
    else:
        df_raw = pd.concat(frames, ignore_index=True)
        # Remove cross-source duplicates by title+city
        df_raw = df_raw.drop_duplicates(subset=["tytul", "miejscowosc"], keep="first")

        with st.spinner("Obliczam odległości od rzeki…"):
            df_raw["odleglosc_m"] = df_raw.apply(
                lambda r: distance_to_liwiec_m(r["lat"], r["lon"], liwiec_geom),
                axis=1,
            )
        st.session_state.raw_df = df_raw
        total    = len(df_raw)
        on_river = int(df_raw["na_liwcu"].sum())
        sources  = ", ".join(df_raw["zrodlo"].unique()) if "zrodlo" in df_raw.columns else ""
        st.success(f"Pobrano **{total}** ogłoszeń ({sources}) — **{on_river}** z miejscowości nad Liwcem.")

# ── Display ───────────────────────────────────────────────────────────────────
df_raw = st.session_state.raw_df

if df_raw is None:
    st.info("Kliknij **Pobierz ogłoszenia z Otodom** aby rozpocząć.")
    _render_empty_map(liwiec_geom, places_df)
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

if len(df) == 0 and len(df_raw) > 0:
    st.warning(
        f"Brak ogłoszeń spełniających kryteria. "
        f"Wszystkich pobranych: {len(df_raw)} — "
        f"w tym z Liwca: {int(df_raw['na_liwcu'].sum())}."
    )

# ── Metrics ───────────────────────────────────────────────────────────────────
c1, c2, c3, c4 = st.columns(4)
c1.metric("Ogłoszeń (po filtrach)", len(df))
c2.metric("Z miejscowości nad Liwcem", int(df_raw["na_liwcu"].sum()))
c3.metric("Wszystkich pobranych", len(df_raw))
if len(df) > 0 and df["cena_pln"].notna().any():
    c4.metric("Mediana ceny",
              f"{int(df['cena_pln'].median()):,} PLN".replace(",", " "))

st.divider()

# ── Map ───────────────────────────────────────────────────────────────────────
st.subheader("Mapa")

ODCINEK_COLOR = {
    "Górny bieg":    "#EF6C00",
    "Środkowy bieg": "#1B5E20",
    "Dolny bieg":    "#1565C0",
    "Ujście":        "#6A1B9A",
}

m = folium.Map(location=[52.46, 21.85], zoom_start=10, tiles="OpenStreetMap")

for segment in liwiec_coords_for_map(liwiec_geom):
    folium.PolyLine(segment, color="#1565C0", weight=4, opacity=0.85,
                    tooltip="Rzeka Liwiec").add_to(m)

df_map = df[df["lat"].notna() & df["lon"].notna()].copy()

for _, row in df_map.iterrows():
    color = ODCINEK_COLOR.get(row.get("odcinek", ""), "#757575")
    cena_str = f"{int(row['cena_pln']):,} PLN".replace(",", " ") \
        if pd.notna(row.get("cena_pln")) else "cena nieznana"
    area_str = f"{int(row['powierzchnia_m2'])} m²" \
        if pd.notna(row.get("powierzchnia_m2")) else "pow. nieznana"
    dist_str = f"~{int(row['odleglosc_m'])} m od rzeki" \
        if pd.notna(row.get("odleglosc_m")) else ""
    uwagi = row.get("uwagi", "")

    popup_html = f"""
    <b style="font-size:13px">{row['tytul'][:65]}</b><br>
    📍 <b>{row['miejscowosc']}</b> — {row.get('odcinek','')}<br>
    💰 {cena_str} &nbsp;|&nbsp; 📐 {area_str}<br>
    {"🌊 " + dist_str + "<br>" if dist_str else ""}
    {"💬 <i>" + uwagi + "</i><br>" if uwagi else ""}
    <a href="{row['url']}" target="_blank">Zobacz ogłoszenie →</a>
    """

    folium.CircleMarker(
        location=[row["lat"], row["lon"]],
        radius=8,
        color=color, fill=True, fill_color=color, fill_opacity=0.85,
        popup=folium.Popup(popup_html, max_width=280),
        tooltip=f"{row['miejscowosc']} | {cena_str}",
    ).add_to(m)

legend_html = """
<div style="position:fixed;bottom:30px;left:30px;z-index:9999;background:#222;color:#eee;
            padding:10px 14px;border-radius:8px;border:1px solid #555;font-size:12px;
            line-height:1.9">
  <b>Odcinek Liwca</b><br>
  <span style="color:#EF6C00">●</span> Górny bieg<br>
  <span style="color:#4CAF50">●</span> Środkowy bieg<br>
  <span style="color:#64B5F6">●</span> Dolny bieg<br>
  <span style="color:#CE93D8">●</span> Ujście
</div>
"""
m.get_root().html.add_child(folium.Element(legend_html))
st_folium(m, use_container_width=True, height=540, returned_objects=[])

# ── Table ─────────────────────────────────────────────────────────────────────
st.subheader("Lista ogłoszeń")

show_cols = {
    "zrodlo":          "Źródło",
    "odcinek":         "Odcinek",
    "miejscowosc":     "Miejscowość",
    "tytul":           "Tytuł",
    "cena_pln":        "Cena (PLN)",
    "url":             "Link",
    "powierzchnia_m2": "Pow. (m²)",
    "cena_za_m2":      "PLN/m²",
    "odleglosc_m":     "Odl. od rzeki (m)*",
}

df_show = df[[c for c in show_cols if c in df.columns]].copy()
df_show = df_show.rename(columns=show_cols)

if "Odcinek" in df_show.columns:
    df_show = df_show.sort_values(["Odcinek", "Cena (PLN)"], na_position="last")

for col in ["Cena (PLN)", "Pow. (m²)", "PLN/m²"]:
    if col in df_show.columns:
        df_show[col] = df_show[col].apply(
            lambda v: f"{int(v):,}".replace(",", " ") if pd.notna(v) else "—")

if "Odl. od rzeki (m)*" in df_show.columns:
    df_show["Odl. od rzeki (m)*"] = df_show["Odl. od rzeki (m)*"].apply(
        lambda v: f"~{int(v):,}".replace(",", " ") if pd.notna(v) else "—")

st.dataframe(
    df_show,
    use_container_width=True,
    column_config={"Link": st.column_config.LinkColumn("Link", display_text="Otwórz →")},
    hide_index=True,
    height=520,
)
st.caption("*) Odległość liczona od centrum miejscowości do rzeki Liwiec (przybliżona).")

# ── Export ────────────────────────────────────────────────────────────────────
csv_out = df.drop(columns=["id"], errors="ignore").to_csv(index=False, encoding="utf-8-sig")
st.download_button("⬇️ Eksportuj CSV", data=csv_out,
                   file_name="dzialki_liwiec.csv", mime="text/csv")
