from __future__ import annotations

from gravelbot.models import Listing, Profil
from gravelbot.scoring.evaluate import evaluate
from gravelbot.scoring.filters import passes_filters


def _profil(**overrides) -> Profil:
    p = Profil()
    for k, v in overrides.items():
        setattr(p, k, v)
    return p


def _listing(**overrides) -> Listing:
    base = dict(
        source="bikemarkt",
        source_id="1",
        title="Canyon Grizl CF SL 8",
        price_eur=2000,
        url="https://example.test/1",
        shipping=False,
    )
    base.update(overrides)
    return Listing(**base)


def test_passes_filters_rejects_out_of_price_range():
    listing = _listing(price_eur=100)
    assert not passes_filters(listing, _profil())


def test_passes_filters_rejects_hard_exclude_keyword():
    listing = _listing(title="Canyon Grizl Rahmenset 58cm")
    assert not passes_filters(listing, _profil())


def test_passes_filters_rejects_profile_exclude_keyword():
    listing = _listing(title="Canyon Grizl defekt")
    assert not passes_filters(listing, _profil(exclude_keywords=["defekt"]))


def test_passes_filters_include_keywords_must_match():
    listing = _listing(title="Canyon Grizl")
    assert not passes_filters(listing, _profil(include_keywords=["Rose"]))
    assert passes_filters(listing, _profil(include_keywords=["Grizl"]))


def test_passes_filters_distance_within_radius_passes():
    listing = _listing(distance_km=50)
    assert passes_filters(listing, _profil(max_distance_km=100))


def test_passes_filters_distance_too_far_without_shipping_fails():
    listing = _listing(distance_km=500, shipping=False)
    assert not passes_filters(listing, _profil(max_distance_km=100))


def test_passes_filters_distance_too_far_with_shipping_passes():
    listing = _listing(distance_km=500, shipping=True)
    assert passes_filters(listing, _profil(max_distance_km=100, include_shipping_offers=True))


def test_passes_filters_unknown_location_respects_profile_flag():
    listing = _listing(distance_km=None, shipping=False)
    assert passes_filters(listing, _profil(include_unknown_location=True))
    assert not passes_filters(listing, _profil(include_unknown_location=False))


def test_evaluate_price_drop_detected():
    listing = _listing(price_eur=900)
    deal = evaluate(listing, _profil(min_price_drop_pct=7), previous_price=1000, market_samples=[])
    assert deal is not None
    assert deal.reason == "price_drop"


def test_evaluate_price_drop_below_threshold_is_not_a_deal():
    listing = _listing(price_eur=980)
    deal = evaluate(listing, _profil(min_price_drop_pct=7), previous_price=1000, market_samples=[])
    assert deal is None


def test_evaluate_under_market_detected_with_enough_samples():
    listing = _listing(price_eur=1500)
    samples = [2000, 2100, 1950, 2050]
    deal = evaluate(
        listing,
        _profil(min_discount_pct=15, min_samples_for_median=4),
        previous_price=None,
        market_samples=samples,
    )
    assert deal is not None
    assert deal.reason == "under_market"


def test_evaluate_under_market_requires_minimum_samples():
    listing = _listing(price_eur=1500)
    samples = [2000, 2100]
    deal = evaluate(
        listing,
        _profil(min_discount_pct=15, min_samples_for_median=4),
        previous_price=None,
        market_samples=samples,
    )
    assert deal is None


def test_evaluate_returns_none_when_no_deal():
    listing = _listing(price_eur=2000)
    deal = evaluate(listing, _profil(), previous_price=2000, market_samples=[2000, 2000, 2000, 2000])
    assert deal is None
