"""Filter: entscheidet, ob ein Listing ueberhaupt zum Profil passt."""

from __future__ import annotations

from gravelbot.config import HARD_EXCLUDE
from gravelbot.models import Listing, Profil


def passes_filters(listing: Listing, profil: Profil) -> bool:
    title = listing.title.lower()
    if any(w in title for w in HARD_EXCLUDE):
        return False
    if not (profil.min_price_eur <= listing.price_eur <= profil.max_price_eur):
        return False
    if any(w.lower() in title for w in profil.exclude_keywords):
        return False
    if profil.include_keywords and not any(w.lower() in title for w in profil.include_keywords):
        return False
    if profil.frame_sizes and not any(str(s).lower() in title for s in profil.frame_sizes):
        return False
    if listing.distance_km is not None:
        if listing.distance_km > profil.max_distance_km:
            return listing.shipping and profil.include_shipping_offers
        return True
    if listing.shipping and profil.include_shipping_offers:
        return True
    return profil.include_unknown_location
