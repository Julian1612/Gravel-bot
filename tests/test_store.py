from __future__ import annotations

from gravelbot.models import Listing, Profil
from gravelbot.storage.store import Store


def _store(tmp_path):
    return Store(str(tmp_path / "state.json"))


def test_new_store_is_first_run(tmp_path):
    store = _store(tmp_path)
    assert store.is_first_run is True
    assert store.profil == Profil()


def test_record_and_previous_price(tmp_path):
    store = _store(tmp_path)
    listing = Listing("bikemarkt", "1", "Canyon Grizl", 2000, "https://example.test/1")
    store.record(listing)
    assert store.previous_price(listing.key) is None

    listing.price_eur = 1800
    store.record(listing)
    assert store.previous_price(listing.key) == 2000


def test_market_and_neupreis_samples_are_capped(tmp_path):
    store = _store(tmp_path)
    for price in range(100):
        store.add_market_sample("canyon grizl", float(price))
    assert len(store.market_samples("canyon grizl")) == store.MAX_MARKET_SAMPLES

    store.add_neupreis_sample("canyon grizl", 2999.0)
    assert store.neupreis_samples("canyon grizl") == [2999.0]


def test_already_alerted_respects_price_tolerance(tmp_path):
    store = _store(tmp_path)
    listing = Listing("bikemarkt", "1", "Canyon Grizl", 1000, "https://example.test/1")
    store.record(listing)
    store.mark_alerted(listing.key, "under_market", 1000)

    assert store.already_alerted(listing.key, "under_market", 1000) is True
    assert store.already_alerted(listing.key, "under_market", 970) is True  # innerhalb 3%
    assert store.already_alerted(listing.key, "under_market", 900) is False  # deutlich billiger


def test_merkliste_add_remove(tmp_path):
    store = _store(tmp_path)
    listing = Listing("bikemarkt", "1", "Canyon Grizl", 1000, "https://example.test/1")
    store.merkliste_add(listing)
    assert listing.key in store.merkliste_items()
    assert store.merkliste_remove(listing.key) is True
    assert listing.key not in store.merkliste_items()
    assert store.merkliste_remove(listing.key) is False


def test_blockliste_seller_and_listing(tmp_path):
    store = _store(tmp_path)
    store.block_seller("boeser_verkaeufer")
    assert store.is_seller_blocked("boeser_verkaeufer") is True
    assert store.unblock_seller("boeser_verkaeufer") is True
    assert store.is_seller_blocked("boeser_verkaeufer") is False

    store.block_listing("bikemarkt:1", "Titel", "https://example.test/1", reason="test")
    assert store.is_listing_blocked("bikemarkt:1") is True
    assert store.unblock_listing("bikemarkt:1") is True
    assert store.is_listing_blocked("bikemarkt:1") is False


def test_reset_profil_restores_defaults(tmp_path):
    store = _store(tmp_path)
    profil = store.profil
    profil.max_distance_km = 999
    store.set_profil(profil)
    assert store.profil.max_distance_km == 999

    store.reset_profil()
    assert store.profil.max_distance_km == Profil().max_distance_km


def test_dialog_state_roundtrip(tmp_path):
    store = _store(tmp_path)
    assert store.get_dialog("123") is None
    store.set_dialog("123", {"flow": "setup", "schritt": "radtyp", "daten": {}})
    assert store.get_dialog("123")["schritt"] == "radtyp"
    store.clear_dialog("123")
    assert store.get_dialog("123") is None


def test_prune_removes_stale_listings(tmp_path):
    store = _store(tmp_path)
    listing = Listing("bikemarkt", "1", "Canyon Grizl", 1000, "https://example.test/1")
    store.record(listing)
    store.data["listings"][listing.key]["last_seen"] = "2000-01-01T00:00:00+00:00"
    removed = store.prune()
    assert removed == 1
    assert store.get(listing.key) is None
