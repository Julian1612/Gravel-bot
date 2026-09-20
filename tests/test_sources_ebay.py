from __future__ import annotations

import json

import pytest

from gravelbot.config import Settings
from gravelbot.http import Http
from gravelbot.sources.ebay import EbayQuelle


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch):
    # Verhindert, dass zufaellig gesetzte echte Credentials aus der Umgebung
    # des Entwicklers die Tests beeinflussen.
    monkeypatch.delenv("EBAY_CLIENT_ID", raising=False)
    monkeypatch.delenv("EBAY_CLIENT_SECRET", raising=False)


def test_ebay_inaktiv_ohne_credentials(monkeypatch):
    monkeypatch.delenv("EBAY_CLIENT_ID", raising=False)
    monkeypatch.delenv("EBAY_CLIENT_SECRET", raising=False)
    settings = Settings()
    quelle = EbayQuelle(Http(settings), settings)

    assert quelle.aktiv() is False
    assert "EBAY_CLIENT_ID" in (quelle.inaktiv_grund() or "")


def test_ebay_suchen_ohne_credentials_liefert_leere_liste_ohne_netzwerk(monkeypatch):
    monkeypatch.delenv("EBAY_CLIENT_ID", raising=False)
    monkeypatch.delenv("EBAY_CLIENT_SECRET", raising=False)
    settings = Settings()
    quelle = EbayQuelle(Http(settings), settings)

    from gravelbot.models import Profil

    # aktiv() ist False -> die Registrierung wuerde suchen() gar nicht erst
    # aufrufen; hier direkt geprueft, dass es trotzdem sicher ausfaellt.
    assert quelle.suchen(Profil()) == []


def test_ebay_map_item_from_real_response_shape(fixture_path):
    settings = Settings()
    quelle = EbayQuelle(Http(settings), settings)
    data = json.loads(fixture_path("ebay_search_response.json").read_text(encoding="utf-8"))

    items = [quelle._map_item(raw, radtyp="gravel") for raw in data["itemSummaries"]]
    assert all(items)

    shop_item, private_item = items
    assert shop_item.source == "ebay"
    assert shop_item.price_eur == 1850.0
    assert shop_item.zip_code == "70173"
    assert shop_item.shipping is True
    assert shop_item.seller_type == "shop"
    assert shop_item.seller_name == "radhaus_stuttgart"
    assert shop_item.radtyp == "gravel"

    assert private_item.seller_type == "private"
    assert private_item.seller_name == "privat_verkauf_99"
    assert private_item.shipping is False
    assert private_item.price_eur == 999.0


def test_ebay_map_item_returns_none_for_incomplete_item():
    settings = Settings()
    quelle = EbayQuelle(Http(settings), settings)
    assert quelle._map_item({"itemId": "1"}, radtyp=None) is None


def test_ebay_search_raw_url_encodes_multi_word_query(monkeypatch):
    settings = Settings()
    quelle = EbayQuelle(Http(settings), settings)
    monkeypatch.setattr(quelle, "_token", lambda: "fake-token")

    aufgerufene_urls = []

    def fake_get(url, headers=None):
        aufgerufene_urls.append(url)
        return None

    monkeypatch.setattr(quelle.http, "get", fake_get)

    # Regression: ein unencodetes Leerzeichen/Sonderzeichen in der Freitext-
    # Query (z.B. aus /suche) wuerde die Query-String-Struktur der URL
    # kaputt machen (Leerzeichen sind in URLs nicht erlaubt, "&" wuerde
    # zusaetzliche, falsche Parameter injizieren).
    quelle._search_raw("Canyon Grizl & Grail", "priceCurrency:EUR", limit=10)

    assert len(aufgerufene_urls) == 1
    assert " " not in aufgerufene_urls[0]
    assert "q=Canyon%20Grizl%20%26%20Grail" in aufgerufene_urls[0]
