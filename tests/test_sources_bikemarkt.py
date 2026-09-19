from __future__ import annotations

from gravelbot.sources.bikemarkt import guess_brand, guess_condition, parse_bikemarkt_page


def test_parse_bikemarkt_category_fixture_finds_listings(fixture_text):
    items = parse_bikemarkt_page(fixture_text("bikemarkt_category.html"), radtyp="gravel")
    assert len(items) >= 5
    assert all(item.source == "bikemarkt" for item in items)
    assert all(item.price_eur > 0 for item in items)
    assert all(item.radtyp == "gravel" for item in items)
    assert all(item.url.startswith("https://bikemarkt.mtb-news.de/article/") for item in items)


def test_parse_bikemarkt_search_fixture_finds_listings(fixture_text):
    items = parse_bikemarkt_page(fixture_text("bikemarkt_search.html"))
    assert len(items) >= 2
    titles = " ".join(item.title for item in items).lower()
    assert "grizl" in titles


def test_parse_bikemarkt_deduplicates_by_article_id(fixture_text):
    items = parse_bikemarkt_page(fixture_text("bikemarkt_category.html"))
    ids = [item.source_id for item in items]
    assert len(ids) == len(set(ids))


def test_guess_brand_matches_known_prefix():
    assert guess_brand("Canyon Grizl CF SL 8") == "Canyon"
    assert guess_brand("Unbekannte Marke XY") is None


def test_guess_condition_recognizes_common_phrases():
    assert guess_condition("Zustand: gebraucht, wie neu") == "gebraucht, wie neu"
    assert guess_condition("gebrauchtes Rad") == "gebraucht"
    assert guess_condition("xyz") is None
