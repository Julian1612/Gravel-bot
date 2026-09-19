from __future__ import annotations

from gravelbot.models import Listing, Profil


def test_model_key_strips_brand_and_noise_words():
    listing = Listing(
        source="bikemarkt",
        source_id="1",
        title="Canyon Grizl CF SL 8 AXS",
        price_eur=2500,
        url="https://example.test/1",
        brand="Canyon",
    )
    assert listing.model_key == "canyon grizl"


def test_model_key_guesses_brand_from_title_when_missing():
    listing = Listing(
        source="bikemarkt",
        source_id="2",
        title="Rondo Ruut CF 1 Gravel Plus",
        price_eur=1800,
        url="https://example.test/2",
    )
    assert listing.model_key == "rondo ruut"


def test_discount_vs_list_pct_none_without_list_price():
    listing = Listing("shop", "1", "Bike", 1000, "https://example.test")
    assert listing.discount_vs_list_pct is None


def test_discount_vs_list_pct_computed():
    listing = Listing("shop", "1", "Bike", 800, "https://example.test", list_price_eur=1000)
    assert listing.discount_vs_list_pct == 20.0


def test_guess_zip_from_location_extracts_five_digits():
    listing = Listing("s", "1", "t", 1, "u", location="70173 Stuttgart")
    listing.guess_zip_from_location()
    assert listing.zip_code == "70173"


def test_guess_zip_does_not_override_existing():
    listing = Listing("s", "1", "t", 1, "u", location="70173 Stuttgart", zip_code="99999")
    listing.guess_zip_from_location()
    assert listing.zip_code == "99999"


def test_profil_validate_radtypen_drops_unknown_and_defaults_to_gravel():
    profil = Profil(radtypen=["unbekannt"])
    profil.validate_radtypen()
    assert profil.radtypen == ["gravel"]


def test_profil_validate_radtypen_keeps_known_values():
    profil = Profil(radtypen=["cyclocross", "rennrad"])
    profil.validate_radtypen()
    assert profil.radtypen == ["cyclocross", "rennrad"]
