import os
import json
import urllib.parse
import requests
from shapely.geometry import LineString, Point
from shapely.ops import transform, unary_union
import pyproj
import streamlit as st

OVERPASS_URL = "https://overpass.kumi.systems/api/interpreter"
OVERPASS_HEADERS = {"User-Agent": "LiwiecDzialkaApp/1.0 (educational)"}

# Simplified query — only confirmed river ways, shorter timeout to avoid 504
OVERPASS_QUERY = (
    '[out:json][timeout:30];'
    'way["name"="Liwiec"]["waterway"="river"];'
    'out geom;'
)

# Local cache file — populated on first successful fetch so subsequent runs
# never need to hit the Overpass API.
_CACHE_FILE = os.path.join(os.path.dirname(__file__), "liwiec_geometry.json")


def _build_geometry_from_osm(data):
    lines = []
    for el in data.get("elements", []):
        if el.get("type") == "way" and "geometry" in el:
            coords = [(pt["lon"], pt["lat"]) for pt in el["geometry"]]
            if len(coords) >= 2:
                lines.append(LineString(coords))
    if not lines:
        return None
    return unary_union(lines)


@st.cache_data(show_spinner="Wczytywanie geometrii rzeki Liwiec…", ttl=86400)
def get_liwiec_geometry():
    """Returns Liwiec river as a Shapely geometry (WGS84 lon/lat).

    Tries in order:
    1. Local cache file (liwiec_geometry.json) — fast, no network
    2. Overpass API — saves result to cache file for next run
    """
    # 1. Local cache
    if os.path.exists(_CACHE_FILE):
        try:
            with open(_CACHE_FILE) as f:
                data = json.load(f)
            geom = _build_geometry_from_osm(data)
            if geom is not None:
                return geom
        except Exception:
            pass  # fall through to network

    # 2. Overpass API
    try:
        url = OVERPASS_URL + "?data=" + urllib.parse.quote(OVERPASS_QUERY)
        resp = requests.get(url, headers=OVERPASS_HEADERS, timeout=45)
        resp.raise_for_status()
        data = resp.json()
        # Save for next run
        try:
            with open(_CACHE_FILE, "w") as f:
                json.dump(data, f)
        except Exception:
            pass
        geom = _build_geometry_from_osm(data)
        if geom is not None:
            return geom
    except Exception as e:
        st.warning(f"⚠️ Nie udało się pobrać geometrii rzeki z API: {e}")

    st.warning("⚠️ Brak danych o rzece Liwiec — obliczenia odległości niedostępne.")
    return None


# ── Distance calculation ──────────────────────────────────────────────────────

_TRANSFORMER = None


def _get_transformer():
    global _TRANSFORMER
    if _TRANSFORMER is None:
        wgs84 = pyproj.CRS("EPSG:4326")
        pl1992 = pyproj.CRS("EPSG:2180")
        _TRANSFORMER = pyproj.Transformer.from_crs(wgs84, pl1992, always_xy=True).transform
    return _TRANSFORMER


def distance_to_liwiec_m(lat, lon, liwiec_geom):
    """Distance in meters from (lat, lon) to the Liwiec river geometry."""
    if liwiec_geom is None or lat is None or lon is None:
        return None
    try:
        t = _get_transformer()
        pt = transform(t, Point(lon, lat))
        river = transform(t, liwiec_geom)
        return pt.distance(river)
    except Exception:
        return None


# ── Map helpers ───────────────────────────────────────────────────────────────

def liwiec_coords_for_map(liwiec_geom):
    """Return list-of-lists of [lat, lon] pairs for Folium PolyLine."""
    if liwiec_geom is None:
        return []

    def _extract(geom):
        if geom.geom_type == "LineString":
            return [list(geom.coords)]
        elif geom.geom_type in ("MultiLineString", "GeometryCollection"):
            result = []
            for g in geom.geoms:
                result.extend(_extract(g))
            return result
        return []

    segments = _extract(liwiec_geom)
    # OSM stores (lon, lat) → flip to [lat, lon] for Folium
    return [[[lat, lon] for lon, lat in seg] for seg in segments]
