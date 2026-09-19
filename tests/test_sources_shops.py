from __future__ import annotations

from html import escape as html_escape

from gravelbot.sources.shops.bike_components import parse_bike_components_page
from gravelbot.sources.shops.canyon_outlet import parse_canyon_outlet_page
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
