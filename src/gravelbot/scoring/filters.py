"""Filter: entscheidet, ob ein Listing ueberhaupt zum Profil passt."""

from __future__ import annotations

import re

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
    if profil.frame_sizes:
        # Bevorzugt gegen die praezise per Regex extrahierte Groesse pruefen
        # (listing.frame_size, siehe enrich/attributes.py — exakter
        # Vergleich). Fallback auf ein Wortgrenzen-Suchmuster im Titel, falls
        # die Extraktion nichts fand (z.B. untypische Schreibweise) — sonst
        # wuerden Treffer mit erkennbarer, aber nicht exakt geparster
        # Groessenangabe faelschlich rausgefiltert. Wortgrenzen statt einem
        # rohen Substring-Check, weil z.B. Groesse "S" sonst in fast jedem
        # Titel als Teilstring eines anderen Worts (z.B. "SL", "Rahmenset")
        # faelschlich "matchen" wuerde.
        exakt_passend = listing.frame_size is not None and any(
            listing.frame_size.lower() == str(s).lower() for s in profil.frame_sizes
        )
        titel_passend = any(
            re.search(rf"\b{re.escape(str(s))}\b", listing.title, re.I) for s in profil.frame_sizes
        )
        if not (exakt_passend or titel_passend):
            return False
    if listing.distance_km is not None:
        if listing.distance_km > profil.max_distance_km:
            return listing.shipping and profil.include_shipping_offers
        return True
    if listing.shipping and profil.include_shipping_offers:
        return True
    return profil.include_unknown_location
