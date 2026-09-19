from __future__ import annotations

from gravelbot.sources.buycycle import parse_buycycle_page


def test_parse_buycycle_jsonld_fixture(fixture_text):
    items = parse_buycycle_page(fixture_text("buycycle_jsonld.html"), radtyp="gravel")
    assert len(items) == 1
    item = items[0]
    assert item.source == "buycycle"
    assert item.title == "Canyon Grizl CF SL 8 AXS"
    assert item.price_eur == 2450.0
    assert item.brand == "Canyon"
    assert item.shipping is True
    assert item.radtyp == "gravel"
    assert item.url.startswith("https://buycycle.com/")


def test_parse_buycycle_empty_page_returns_empty_list():
    assert parse_buycycle_page("<html><body>keine Treffer</body></html>") == []
