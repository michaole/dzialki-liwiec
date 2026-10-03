import pandas as pd

from liwiec import history, pipeline
from liwiec.listings import COLUMNS, to_dataframe, to_float
from liwiec.places import match_place


def test_match_place_ignores_case_and_polish_letters():
    assert match_place("Kamieńczyk").odcinek == "Ujście"
    assert match_place("KAMIENCZYK").nazwa == "Kamieńczyk"
    assert match_place("Branszczyk-Nakiel").nazwa == "Brańszczyk-Nakieł"
    assert match_place("Wyszków") is None
    assert match_place("") is None


def test_to_float():
    assert to_float("1\xa0598 454") == 1598454.0
    assert to_float("2,5") == 2.5
    assert to_float(None) is None
    assert to_float("cena do negocjacji") is None


def test_to_dataframe_dedupes_annotates_and_computes_price_per_m2():
    rows = [
        {"id": "a", "tytul": "x", "miejscowosc": "Loretto", "cena_pln": 100000.0,
         "powierzchnia_m2": 1000.0, "url": "u1"},
        {"id": "a", "tytul": "dup", "miejscowosc": "Loretto", "cena_pln": 1.0,
         "powierzchnia_m2": 1.0, "url": "u1"},
        {"id": "b", "tytul": "y", "miejscowosc": "Gdańsk", "cena_pln": None,
         "powierzchnia_m2": 500.0, "url": "u2", "lat": 54.3, "lon": 18.6},
    ]

    df = to_dataframe(rows, "Test").set_index("id")

    assert list(df.reset_index().columns[:len(COLUMNS)]) == COLUMNS
    assert len(df) == 2
    assert df.loc["a", "zrodlo"] == "Test"
    assert df.loc["a", "cena_za_m2"] == 100
    assert df.loc["a", "na_liwcu"] and df.loc["a", "odcinek"] == "Dolny bieg"
    assert df.loc["a", "lat"] == match_place("Loretto").lat       # place coords as fallback
    assert not df.loc["b", "na_liwcu"] and df.loc["b", "odcinek"] == "—"
    assert df.loc["b", "lat"] == 54.3                               # listing GPS is kept
    assert pd.isna(df.loc["b", "cena_za_m2"])


def test_to_dataframe_empty_has_schema():
    assert list(to_dataframe([], "Test").columns) == COLUMNS


def test_pipeline_merges_and_dedupes_cross_posted_listings(monkeypatch):
    def fake(name, rows):
        return lambda progress_callback=None: to_dataframe(rows, name)

    monkeypatch.setattr(pipeline, "SCRAPERS", {
        "A": fake("A", [{"id": "a1", "tytul": "Działka", "miejscowosc": "Loretto", "url": ""}]),
        "B": fake("B", [{"id": "b1", "tytul": "Działka", "miejscowosc": "Loretto", "url": ""},
                        {"id": "b2", "tytul": "Inna", "miejscowosc": "Loretto", "url": ""}]),
        "C": fake("C", []),
    })

    df = pipeline.scrape_portals()

    assert sorted(df["id"]) == ["a1", "b2"]
    assert pipeline.scrape_portals(["C"]).empty


def test_update_and_mark_only_deactivates_scraped_portals(tmp_path, monkeypatch):
    monkeypatch.setattr(history, "_DB_PATH", tmp_path / "test.db")

    def listing(id_, zrodlo, cena):
        return {"id": id_, "zrodlo": zrodlo, "tytul": id_, "miejscowosc": "Loretto",
                "odcinek": "Dolny bieg", "na_liwcu": True, "url": "", "cena_pln": cena,
                "powierzchnia_m2": 1000.0}

    history.update_and_mark(pd.DataFrame([listing("o1", "Otodom", 100.0),
                                          listing("x1", "OLX", 100.0)]),
                            scraped_sources={"Otodom", "OLX"})

    # Re-scrape only OLX, with a price drop: the Otodom listing must stay active
    out = history.update_and_mark(pd.DataFrame([listing("x1", "OLX", 90.0)]),
                                  scraped_sources={"OLX"})

    assert out.loc[0, "zmiana_ceny"] == -10.0
    assert history.get_inactive_listings().empty

    # Re-scrape OLX without x1: now it is gone
    history.update_and_mark(pd.DataFrame([listing("x2", "OLX", 50.0)]), scraped_sources={"OLX"})
    assert history.get_inactive_listings()["id"].tolist() == ["x1"]


def test_store_tracks_first_seen_price_history_and_gone():
    from liwiec import store

    def df(*rows):
        return pd.DataFrame([{"id": i, "zrodlo": z, "tytul": i, "miejscowosc": "Loretto",
                              "odcinek": "Dolny bieg", "url": "", "cena_pln": c,
                              "powierzchnia_m2": 1000.0, "cena_za_m2": None,
                              "data_dodania": "2026-09-01"} for i, z, c in rows])

    h = store.update({}, df(("a", "OLX", 100.0), ("k", "Otodom", 50.0)),
                     {"OLX", "Otodom"}, today="2026-10-01", known_ids={"k"})
    assert h["a"]["first_seen"] == "2026-10-01"
    assert h["k"]["first_seen"] == "2026-09-01"          # known to the email job already

    # Next day: OLX blocked (no rows), Otodom price drop
    store.update(h, df(("k", "Otodom", 45.0)), {"Otodom"}, today="2026-10-02")
    assert h["a"]["active"]                              # not scraped → untouched
    assert h["k"]["prices"] == [["2026-10-01", 50.0], ["2026-10-02", 45.0]]

    # OLX back without "a": now it is gone
    store.update(h, df(("b", "OLX", 70.0), ("k", "Otodom", 45.0)), {"OLX", "Otodom"}, today="2026-10-03")
    assert not h["a"]["active"] and h["b"]["active"]
    assert h["k"]["prices"][-1] == ["2026-10-02", 45.0]  # unchanged price not repeated
