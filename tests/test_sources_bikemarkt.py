from __future__ import annotations

from gravelbot.sources.bikemarkt import BikemarktQuelle, guess_brand, guess_condition, parse_bikemarkt_page


class _FakeResponse:
    def __init__(self, text: str, url: str):
        self.text = text
        self.url = url


class _FakeHttp:
    """Simuliert, dass /search?q_ft=X auf eine kanonische URL umleitet und
    Pagination nur auf dieser kanonischen URL funktioniert — genau das
    Verhalten, das gegen die echte Bikemarkt-Seite verifiziert wurde."""

    def __init__(self, seiten: dict[str, str]):
        self.seiten = seiten
        self.angefragte_urls: list[str] = []

    def get(self, url, headers=None):
        self.angefragte_urls.append(url)
        if url.startswith("https://bikemarkt.mtb-news.de/search?q_ft="):
            return _FakeResponse(self.seiten["seite1"], "https://bikemarkt.mtb-news.de/search/Canyon")
        if url == "https://bikemarkt.mtb-news.de/search/Canyon?page=2":
            return _FakeResponse(self.seiten["seite2"], url)
        return _FakeResponse("<html></html>", url)


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


def test_volltext_encodes_query_and_paginates_via_canonical_redirect_url(fixture_text):
    http = _FakeHttp(
        {"seite1": fixture_text("bikemarkt_search.html"), "seite2": fixture_text("bikemarkt_category.html")}
    )
    quelle = BikemarktQuelle(http, settings=None)

    items = quelle.volltext("canyon grizl", max_seiten=2)

    assert http.angefragte_urls[0] == "https://bikemarkt.mtb-news.de/search?q_ft=canyon%20grizl"
    assert http.angefragte_urls[1] == "https://bikemarkt.mtb-news.de/search/Canyon?page=2"
    # Ergebnisse von beiden Seiten wurden zusammengefuehrt
    seite1_only_ids = {i.source_id for i in parse_bikemarkt_page(fixture_text("bikemarkt_search.html"))}
    seite2_only_ids = {i.source_id for i in parse_bikemarkt_page(fixture_text("bikemarkt_category.html"))}
    result_ids = {i.source_id for i in items}
    assert seite1_only_ids <= result_ids
    assert seite2_only_ids <= result_ids


def test_volltext_stops_after_one_page_when_max_seiten_is_1(fixture_text):
    http = _FakeHttp(
        {"seite1": fixture_text("bikemarkt_search.html"), "seite2": fixture_text("bikemarkt_category.html")}
    )
    quelle = BikemarktQuelle(http, settings=None)

    quelle.volltext("canyon", max_seiten=1)

    assert len(http.angefragte_urls) == 1


def test_guess_brand_matches_known_prefix():
    assert guess_brand("Canyon Grizl CF SL 8") == "Canyon"
    assert guess_brand("Unbekannte Marke XY") is None


def test_guess_condition_recognizes_common_phrases():
    assert guess_condition("Zustand: gebraucht, wie neu") == "gebraucht, wie neu"
    assert guess_condition("gebrauchtes Rad") == "gebraucht"
    assert guess_condition("xyz") is None
