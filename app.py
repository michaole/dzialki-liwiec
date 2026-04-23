import streamlit as st
import pandas as pd
import folium
from folium.plugins import MarkerCluster
from streamlit_folium import st_folium

from geo_utils import get_liwiec_geometry, distance_to_liwiec_m, liwiec_coords_for_map
from scraper import scrape_all
from olx_scraper import scrape_olx_all
from liwiec_places import load_places, odcinek_options

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(page_title="Działki nad Liwcem", page_icon="🌊", layout="wide")

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* Overall page */
.block-container { padding-top: 1.2rem; padding-bottom: 1rem; max-width: 1300px; }

/* Filter pill bar */
div[data-testid="stHorizontalBlock"] .stSelectbox label,
div[data-testid="stHorizontalBlock"] .stMultiSelect label,
div[data-testid="stHorizontalBlock"] .stNumberInput label {
    font-size: 0.78rem;
    font-weight: 600;
    color: #5e6e82;
    text-transform: uppercase;
    letter-spacing: 0.04em;
}

/* Metric cards */
div[data-testid="metric-container"] {
    background: #f8fafd;
    border: 1px solid #dce6f0;
    border-radius: 12px;
    padding: 14px 18px;
    box-shadow: 0 1px 4px rgba(0,0,0,0.05);
}
div[data-testid="metric-container"] [data-testid="stMetricValue"] {
    font-size: 1.6rem;
    font-weight: 700;
    color: #1565C0;
}
div[data-testid="metric-container"] [data-testid="stMetricLabel"] {
    font-size: 0.78rem;
    color: #5e6e82;
}

/* Primary fetch buttons */
div[data-testid="stHorizontalBlock"] .stButton > button[kind="primary"] {
    background: linear-gradient(135deg, #1565C0, #1976D2);
    border: none;
    border-radius: 10px;
    font-weight: 700;
    letter-spacing: 0.02em;
    box-shadow: 0 2px 6px rgba(21,101,192,0.35);
    transition: transform 0.1s, box-shadow 0.1s;
}
div[data-testid="stHorizontalBlock"] .stButton > button[kind="primary"]:hover {
    transform: translateY(-1px);
    box-shadow: 0 4px 10px rgba(21,101,192,0.45);
}
div[data-testid="stHorizontalBlock"] .stButton > button[kind="secondary"] {
    border-radius: 10px;
    font-weight: 600;
}

/* Section headings */
h3 { color: #1a2c42; margin-top: 0.5rem !important; }

/* Dataframe */
div[data-testid="stDataFrame"] { border-radius: 10px; overflow: hidden; }

/* Divider styling */
hr { border-color: #e0eaf4 !important; margin: 0.6rem 0 !important; }
</style>
""", unsafe_allow_html=True)

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

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("## 🌊 Działki nad rzeką Liwiec")
st.caption(
    "Ogłoszenia z Otodom i OLX filtrowane według miejscowości nad Liwcem. "
    f"Baza zawiera **{len(places_df)}** miejscowości."
)

st.divider()

# ── Top filter bar ────────────────────────────────────────────────────────────
c_src, c_odc, c_liwiec, c_price, c_area, c_gap, c_btn1, c_btn2 = st.columns(
    [1.6, 1.6, 1.2, 1.5, 1.5, 0.4, 1.2, 1.2]
)

with c_src:
    zrodlo_filter = st.multiselect(
        "Źródło", options=["Otodom", "OLX"], default=["Otodom", "OLX"],
        label_visibility="visible",
    )
with c_odc:
    odcinek = st.selectbox("Odcinek rzeki", options=odcinek_options())
with c_liwiec:
    only_liwiec = st.checkbox(
        "Tylko nad Liwcem",
        value=True,
        help="Odznacz, żeby zobaczyć też ogłoszenia spoza listy CSV.",
    )
with c_price:
    max_price = st.number_input("Maks. cena (PLN)", min_value=0, value=0, step=10_000,
                                help="0 = bez limitu")
with c_area:
    min_area = st.number_input("Min. pow. (m²)", min_value=0, value=0, step=100,
                               help="0 = bez limitu")
with c_btn1:
    st.markdown("<div style='margin-top:22px'></div>", unsafe_allow_html=True)
    fetch_otodom = st.button("🔄 Otodom", use_container_width=True, type="primary")
with c_btn2:
    st.markdown("<div style='margin-top:22px'></div>", unsafe_allow_html=True)
    fetch_olx = st.button("🔄 OLX", use_container_width=True, type="secondary")

fetch_btn = fetch_otodom or fetch_olx

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

    bar.progress(1.0, text="Gotowe!")

    if not frames:
        st.error("Nie pobrano żadnych ogłoszeń. Spróbuj za chwilę.")
    else:
        df_raw = pd.concat(frames, ignore_index=True)
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
        st.success(
            f"Pobrano **{total}** ogłoszeń ({sources}) — "
            f"**{on_river}** z miejscowości nad Liwcem."
        )

# ── Display ───────────────────────────────────────────────────────────────────
df_raw = st.session_state.raw_df

if df_raw is None:
    st.info("👆 Kliknij **🔄 Otodom** lub **🔄 OLX** powyżej, aby pobrać ogłoszenia.")
    # Show empty map
    m0 = folium.Map(location=[52.46, 21.85], zoom_start=10,
                    tiles="CartoDB positron")
    for segment in liwiec_coords_for_map(liwiec_geom):
        folium.PolyLine(segment, color="#1565C0", weight=5, opacity=0.8,
                        tooltip="Rzeka Liwiec").add_to(m0)
    for _, p in places_df.iterrows():
        folium.CircleMarker(
            location=[p["lat"], p["lon"]], radius=5,
            color="#43A047", fill=True, fill_color="#43A047", fill_opacity=0.6,
            tooltip=f"{p['Nazwa']} ({p['Odcinek']})",
        ).add_to(m0)
    st_folium(m0, use_container_width=True, height=520, returned_objects=[])
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
        f"Wszystkich: {len(df_raw)} — nad Liwcem: {int(df_raw['na_liwcu'].sum())}."
    )

# ── Metrics ───────────────────────────────────────────────────────────────────
m1, m2, m3, m4 = st.columns(4)
m1.metric("Ogłoszenia (po filtrach)", len(df))
m2.metric("Nad Liwcem", int(df_raw["na_liwcu"].sum()))
m3.metric("Wszystkich pobranych", len(df_raw))
if len(df) > 0 and df["cena_pln"].notna().any():
    m4.metric(
        "Mediana ceny",
        f"{int(df['cena_pln'].median()):,} PLN".replace(",", " ")
    )

st.divider()

# ── Map ───────────────────────────────────────────────────────────────────────
st.markdown("### 🗺️ Mapa ogłoszeń")

ODCINEK_COLOR = {
    "Górny bieg":    "#F4511E",
    "Środkowy bieg": "#2E7D32",
    "Dolny bieg":    "#1565C0",
    "Ujście":        "#6A1B9A",
}

m = folium.Map(
    location=[52.46, 21.85],
    zoom_start=10,
    tiles="CartoDB positron",
    prefer_canvas=True,
)

# River line — double-layer for glow effect
for segment in liwiec_coords_for_map(liwiec_geom):
    folium.PolyLine(
        segment, color="#90CAF9", weight=10, opacity=0.35,
    ).add_to(m)
    folium.PolyLine(
        segment, color="#1565C0", weight=4, opacity=0.9,
        tooltip="Rzeka Liwiec",
    ).add_to(m)

# Markers with clustering
cluster = MarkerCluster(
    options={
        "maxClusterRadius": 45,
        "disableClusteringAtZoom": 13,
    }
).add_to(m)

df_map = df[df["lat"].notna() & df["lon"].notna()].copy()

for _, row in df_map.iterrows():
    color = ODCINEK_COLOR.get(row.get("odcinek", ""), "#757575")
    cena_str = f"{int(row['cena_pln']):,} PLN".replace(",", " ") \
        if pd.notna(row.get("cena_pln")) else "cena nieznana"
    area_str = f"{int(row['powierzchnia_m2'])} m²" \
        if pd.notna(row.get("powierzchnia_m2")) else "—"
    dist_str = f"~{int(row['odleglosc_m'])} m" \
        if pd.notna(row.get("odleglosc_m")) else "—"
    zrodlo_badge = (
        f'<span style="background:#E3F2FD;color:#1565C0;border-radius:4px;'
        f'padding:1px 6px;font-size:10px;font-weight:700">'
        f'{row.get("zrodlo","")}</span>'
        if row.get("zrodlo") else ""
    )

    popup_html = f"""
    <div style="font-family:sans-serif;font-size:13px;min-width:240px;max-width:280px">
      <div style="margin-bottom:6px">{zrodlo_badge}
        <span style="color:#546e7a;font-size:11px;margin-left:4px">
          {row.get("odcinek","")}
        </span>
      </div>
      <b style="font-size:14px;color:#1a2c42;line-height:1.3">
        {str(row["tytul"])[:70]}
      </b>
      <div style="margin:7px 0 4px;font-size:12px;color:#37474f">
        📍 <b>{row["miejscowosc"]}</b>
      </div>
      <div style="display:flex;gap:10px;margin-bottom:6px">
        <span style="background:#e8f5e9;color:#2e7d32;border-radius:6px;
                     padding:3px 8px;font-weight:700;font-size:12px">
          💰 {cena_str}
        </span>
        <span style="background:#f3e5f5;color:#6a1b9a;border-radius:6px;
                     padding:3px 8px;font-weight:600;font-size:12px">
          📐 {area_str}
        </span>
      </div>
      <div style="color:#78909c;font-size:11px;margin-bottom:8px">
        🌊 od rzeki: {dist_str}
      </div>
      <a href="{row["url"]}" target="_blank"
         style="display:block;text-align:center;background:#1565C0;color:white;
                padding:6px;border-radius:6px;text-decoration:none;
                font-weight:600;font-size:12px">
        Zobacz ogłoszenie →
      </a>
    </div>
    """

    folium.CircleMarker(
        location=[row["lat"], row["lon"]],
        radius=9,
        color="white",
        weight=2,
        fill=True,
        fill_color=color,
        fill_opacity=0.92,
        popup=folium.Popup(popup_html, max_width=290),
        tooltip=f"<b>{row['miejscowosc']}</b> | {cena_str}",
    ).add_to(cluster)

# Legend
legend_html = """
<div style="position:fixed;bottom:28px;left:28px;z-index:9999;
            background:rgba(255,255,255,0.96);
            padding:12px 16px;border-radius:10px;
            box-shadow:0 2px 10px rgba(0,0,0,0.15);
            font-family:sans-serif;font-size:12px;line-height:2">
  <div style="font-weight:700;color:#1a2c42;margin-bottom:2px">Odcinek Liwca</div>
  <span style="color:#F4511E;font-size:16px">●</span>&nbsp;Górny bieg<br>
  <span style="color:#2E7D32;font-size:16px">●</span>&nbsp;Środkowy bieg<br>
  <span style="color:#1565C0;font-size:16px">●</span>&nbsp;Dolny bieg<br>
  <span style="color:#6A1B9A;font-size:16px">●</span>&nbsp;Ujście
</div>
"""
m.get_root().html.add_child(folium.Element(legend_html))

st_folium(m, use_container_width=True, height=560, returned_objects=[])

st.divider()

# ── Table ─────────────────────────────────────────────────────────────────────
st.markdown("### 📋 Lista ogłoszeń")

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
    column_config={
        "Link": st.column_config.LinkColumn("Link", display_text="Otwórz →"),
    },
    hide_index=True,
    height=500,
)
st.caption("*) Odległość liczona od centrum miejscowości do rzeki Liwiec (przybliżona).")

# ── Export ────────────────────────────────────────────────────────────────────
csv_out = df.drop(columns=["id"], errors="ignore").to_csv(index=False, encoding="utf-8-sig")
st.download_button(
    "⬇️ Eksportuj CSV",
    data=csv_out,
    file_name="dzialki_liwiec.csv",
    mime="text/csv",
)
