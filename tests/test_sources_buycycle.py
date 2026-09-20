from __future__ import annotations

from gravelbot.sources.buycycle import BuycycleQuelle, parse_buycycle_page


class _FakeHttp:
    def __init__(self):
        self.aufgerufene_urls: list[str] = []

    def get(self, url, headers=None):
        self.aufgerufene_urls.append(url)
        return None


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


def test_volltext_url_encodes_multi_word_query():
    http = _FakeHttp()
    quelle = BuycycleQuelle(http, settings=None)

    quelle.volltext("Canyon Grizl & Grail", max_seiten=1)

    assert len(http.aufgerufene_urls) == 1
    url = http.aufgerufene_urls[0]
    assert " " not in url
    assert "query=Canyon%20Grizl%20%26%20Grail" in url
