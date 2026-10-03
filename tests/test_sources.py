"""Parser tests for each portal, using minimal offline copies of the real page structure."""
import json

from liwiec.sources import adresowo, gratka, olx, otodom


def test_otodom_parses_next_data():
    data = {"props": {"pageProps": {"data": {"searchAds": {
        "pagination": {"totalPages": 3},
        "items": [{
            "id": 123, "title": " Działka nad Liwcem ", "slug": "dzialka-ID4abc",
            "totalPrice": {"value": 150000}, "pricePerSquareMeter": {"value": 150},
            "areaInSquareMeters": 1000, "estate": "TERRAIN", "dateCreated": "2026-09-30 10:00:00",
            "location": {
                "address": {"city": {"name": "Kamieńczyk"}},
                "reverseGeocoding": {"locations": [{"locationLevel": "county", "name": "wyszkowski"}]},
            },
        }],
    }}}}}
    html = f'<script id="__NEXT_DATA__" type="application/json">{json.dumps(data)}</script>'

    rows, pages = otodom.parse_page(html)

    assert pages == 3
    assert rows == [{
        "id": "123", "tytul": "Działka nad Liwcem", "opis": "",
        "cena_pln": 150000.0, "cena_za_m2": 150.0, "powierzchnia_m2": 1000.0,
        "miejscowosc": "Kamieńczyk", "powiat": "wyszkowski",
        "url": "https://www.otodom.pl/pl/oferta/dzialka-ID4abc",
        "typ": "TERRAIN", "data_dodania": "2026-09-30",
    }]


def test_otodom_handles_missing_or_broken_page():
    assert otodom.parse_page(None) == ([], 0)
    assert otodom.parse_page("<html>captcha</html>") == ([], 0)


def test_olx_parses_double_encoded_state():
    state = {"listing": {"listing": {"totalPages": 2, "ads": [{
        "id": 987, "title": "Działka rekreacyjna", "url": "https://www.olx.pl/d/oferta/x.html",
        "price": {"regularPrice": {"value": 99000, "negotiable": True}},
        "params": [{"key": "m", "value": "1 200"}, {"key": "type", "value": "rekreacyjna"}],
        "location": {"cityName": "Brańszczyk"},
        "map": {"lat": 52.62, "lon": 21.58, "radius": 0},
        "createdTime": "2026-09-01T12:00:00+02:00",
    }]}}}
    html = f"<script>window.__PRERENDERED_STATE__= {json.dumps(json.dumps(state))};</script>"

    rows, pages = olx.parse_page(html)

    assert pages == 2
    assert rows[0]["id"] == "olx_987"
    assert rows[0]["powierzchnia_m2"] == 1200.0
    assert rows[0]["cena_negocjowalna"] is True
    assert (rows[0]["lat"], rows[0]["lon"]) == (52.62, 21.58)
    assert rows[0]["gps_dokladny"] is True


def test_olx_city_slug_and_bbox():
    assert olx.city_slug("Brańszczyk-Nakieł") == "branszczyk-nakiel"
    assert olx.city_slug("Świniotop") == "swiniotop"
    assert olx.in_liwiec_bbox(52.6, 21.6)
    assert not olx.in_liwiec_bbox(54.0, 18.6)    # same name, Pomerania
    assert olx.in_liwiec_bbox(None, None)


def test_gratka_resolves_nuxt_references():
    # Flat Nuxt array: integers are indexes into the same array
    data = [
        {"header": 11, "count": 12},
        {"idOnFrontend": 2, "advertisementText": 3, "price": 4, "area": 6,
         "location": 7, "url": 9, "addedAt": 10},
        "41026295",
        "Działka budowlana",
        {"amount": 5},
        "175 000",
        "1\xa0172",           # area with a non-breaking space
        {"location": 8},
        ["mazowieckie", "wyszkowski", "Brańszczyk", "Pogorzelec"],
        "/nieruchomosci/dzialka/ob/41026295",
        "2026-09-20T08:00:00",
        "Działki i grunty na sprzedaż",
        "80 ogłoszeń",
    ]
    html = f'<script type="application/json" id="__NUXT_DATA__">{json.dumps(data)}</script>'

    rows, pages = gratka.parse_page(html)

    assert pages == 3     # 80 results / 35 per page
    assert rows == [{
        "id": "gratka_41026295", "tytul": "Działka budowlana",
        "cena_pln": 175000.0, "powierzchnia_m2": 1172.0, "miejscowosc": "Pogorzelec",
        "url": "https://gratka.pl/nieruchomosci/dzialka/ob/41026295",
        "data_dodania": "2026-09-20",
    }]


ADRESOWO_CARD = """
<html><head><link rel="next" href="/dzialki/powiat-wyszkowski/_l2"></head><body>
<div class="relative flex" data-id="4282652" data-offer-card="">
  <p class="flex-auto text-base text-neutral-900">
    <span class="font-bold">199 000</span><span class="text-xs text-neutral-700">zł</span>
  </p>
  <p class="flex-auto text-base text-neutral-900">
    <span class="font-bold">0,5</span><span class="text-xs text-neutral-700">ha</span>
  </p>
  <p class="flex-auto text-sm"><span data-badge=""></span><span>Obejrzane</span></p>
  <h2><a data-track="offer-link" href="/o/dzialka-kamienczyk-n1h8w6">
    <span aria-hidden="true" class="absolute inset-0"></span>
    <span class="line-clamp-1 font-medium">Kamieńczyk</span>
    <span class="line-clamp-1 text-neutral-600"></span>
    <span class="flex"><span>Działka na sprzedaż</span></span>
  </a></h2>
</div>
</body></html>
"""


def test_adresowo_parses_current_card_markup():
    rows, has_next = adresowo.parse_page(ADRESOWO_CARD)

    assert has_next
    assert rows == [{
        "id": "adresowo_4282652",
        "tytul": "Kamieńczyk Działka na sprzedaż",
        "miejscowosc": "Kamieńczyk",
        "cena_pln": 199000.0,
        "powierzchnia_m2": 5000.0,
        "url": "https://adresowo.pl/o/dzialka-kamienczyk-n1h8w6",
    }]


def test_adresowo_page_urls():
    assert adresowo._page_url("/dzialki/powiat-wyszkowski/", 1) == \
        "https://adresowo.pl/dzialki/powiat-wyszkowski/"
    assert adresowo._page_url("/dzialki/powiat-wyszkowski/", 3) == \
        "https://adresowo.pl/dzialki/powiat-wyszkowski/_l3"


def test_gratka_page_count_from_header_text():
    data = [{"header": 1, "count": 2}, "Działki i grunty na sprzedaż", "1 204 ogłoszenia"]
    html = f'<script type="application/json" id="__NUXT_DATA__">{json.dumps(data)}</script>'

    _, pages = gratka.parse_page(html)

    assert pages == 35    # ceil(1204 / 35)
