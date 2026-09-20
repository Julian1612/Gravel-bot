from __future__ import annotations

from html import escape as html_escape

from gravelbot.sources.shops.bike_components import parse_bike_components_page
from gravelbot.sources.shops.canyon_outlet import parse_canyon_outlet_page
from gravelbot.sources.shops.fahrrad_de import parse_fahrrad_de_collection
from gravelbot.sources.shops.focus_outlet import FocusOutletQuelle
from gravelbot.sources.shops.radon_outlet import RadonOutletQuelle
from gravelbot.sources.shops.rose_sale import parse_rose_sale_page


def test_canyon_outlet_parses_real_fixture(fixture_text):
    items = parse_canyon_outlet_page(fixture_text("canyon_outlet.html"))
    assert len(items) >= 5
    assert all(item.source == "canyon_outlet" for item in items)
    assert all(item.is_new for item in items)
    # jeder Sale-Artikel hat einen Streichpreis ueber dem Aktionspreis
    assert all(item.list_price_eur and item.list_price_eur > item.price_eur for item in items)


def test_canyon_outlet_filters_by_kategorie(fixture_text):
    text = fixture_text("canyon_outlet.html")
    alle = parse_canyon_outlet_page(text)
    gravel = parse_canyon_outlet_page(text, kategorie="Gravel Outlet")
    assert 0 < len(gravel) < len(alle)
    assert all(i.title for i in gravel)


def test_canyon_outlet_excludes_hard_excluded_titles():
    impression = (
        '[{"ecommerce":{"items":['
        '{"item_name":"Grizl E-Bike Outlet","item_id":"1",'
        '"item_category2":"Gravel Outlet","price":2000,"gross_price":2500}'
        "]}}]"
    )
    html = f"""
    <div data-pid="1" data-gtm-impression='{html_escape(impression)}'>
        <a href="https://example.test/1">x</a>
    </div>
    """
    assert parse_canyon_outlet_page(html) == []


def test_rose_sale_parses_real_fixture(fixture_text):
    items = parse_rose_sale_page(fixture_text("rose_sale.html"))
    assert len(items) >= 5
    assert all(item.source == "rose_sale" for item in items)
    assert all(item.brand == "Rose" for item in items)
    assert all(item.is_new for item in items)
    assert all(item.list_price_eur and item.list_price_eur >= item.price_eur for item in items)


def test_bike_components_only_keeps_sale_items(fixture_text):
    items = parse_bike_components_page(fixture_text("bike_components_gravelbike.html"))
    assert len(items) >= 5
    assert all(item.source == "bike_components" for item in items)
    assert all(item.list_price_eur and item.list_price_eur > item.price_eur for item in items)
    assert all(
        "gravelbike" in item.url.lower() or "gravel" in item.title.lower() or item.list_price_eur
        for item in items
    )


def test_fahrrad_de_one_listing_per_available_variant(fixture_text):
    seite = parse_fahrrad_de_collection(fixture_text("fahrrad_de_gravel_bikes.json"))
    titel = [i.title for i in seite.listings]
    # Kona Rove AL hat 3 Groessen, eine davon (56) ist sold out -> nur 2 Listings.
    assert titel.count("Kona Rove AL blue (2026)") == 2
    groessen = {i.frame_size for i in seite.listings if i.title == "Kona Rove AL blue (2026)"}
    assert groessen == {"48", "50"}


def test_fahrrad_de_skips_sold_out_variants(fixture_text):
    seite = parse_fahrrad_de_collection(fixture_text("fahrrad_de_gravel_bikes.json"))
    assert all(i.frame_size != "56" or i.title != "Kona Rove AL blue (2026)" for i in seite.listings)


def test_fahrrad_de_filters_out_non_whitelisted_product_type(fixture_text):
    # "Jugend-/Kinder-Gravelbike" ist trotz Kollektionsname kein Komplettbike
    # im gesuchten Sinn und steht nicht auf der product_type-Whitelist.
    seite = parse_fahrrad_de_collection(fixture_text("fahrrad_de_gravel_bikes.json"))
    assert all("gravel 5" not in i.title.lower() for i in seite.listings)


def test_fahrrad_de_excludes_hard_excluded_titles(fixture_text):
    seite = parse_fahrrad_de_collection(fixture_text("fahrrad_de_gravel_bikes.json"))
    assert all("e-bike" not in i.title.lower() for i in seite.listings)


def test_fahrrad_de_normalizes_variant_size_labels(fixture_text):
    seite = parse_fahrrad_de_collection(fixture_text("fahrrad_de_gravel_bikes.json"))
    cube = next(i for i in seite.listings if i.title.startswith("Cube Nuroad"))
    assert cube.frame_size == "XS"


def test_fahrrad_de_sets_list_price_and_new_flag(fixture_text):
    seite = parse_fahrrad_de_collection(fixture_text("fahrrad_de_gravel_bikes.json"))
    kona = next(i for i in seite.listings if i.frame_size == "48")
    assert kona.price_eur == 629.0
    assert kona.list_price_eur == 899.0
    assert kona.is_new is True
    assert kona.source == "fahrrad_de"


def test_fahrrad_de_reports_last_page_when_fewer_than_page_size(fixture_text):
    seite = parse_fahrrad_de_collection(fixture_text("fahrrad_de_gravel_bikes.json"))
    assert seite.ist_letzte_seite is True


def test_fahrrad_de_handles_invalid_json_gracefully():
    seite = parse_fahrrad_de_collection("not json")
    assert seite.listings == []
    assert seite.ist_letzte_seite is True


def test_radon_outlet_is_disabled_with_a_reason():
    quelle = RadonOutletQuelle(http=None, settings=None)
    assert quelle.aktiv() is False
    assert quelle.inaktiv_grund()
    assert quelle.suchen(profil=None) == []


def test_focus_outlet_is_disabled_with_a_reason():
    quelle = FocusOutletQuelle(http=None, settings=None)
    assert quelle.aktiv() is False
    assert quelle.inaktiv_grund()
    assert quelle.suchen(profil=None) == []
