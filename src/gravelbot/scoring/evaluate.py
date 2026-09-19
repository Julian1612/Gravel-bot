"""Bewertung: entscheidet, ob ein Listing ein Deal ist.

Reine Funktion — Vergleichspreise (Median-Stichprobe, letzter Preis)
werden als Parameter uebergeben statt hier aus dem Store gelesen. Der
Rabatt gegenueber der Neupreis-Referenz (Listing.discount_vs_list_pct)
fliesst hier bewusst noch NICHT ein — das ist Phase 2, siehe
docs/adr/0005-neupreis-referenz-ohne-bewertung.md. Aktuell sammeln wir die
Daten nur.
"""

from __future__ import annotations

import statistics

from gravelbot.models import Deal, Listing, Profil


def evaluate(
    listing: Listing, profil: Profil, previous_price: float | None, market_samples: list[float]
) -> Deal | None:
    if previous_price and previous_price > listing.price_eur:
        drop = (previous_price - listing.price_eur) / previous_price * 100
        if drop >= profil.min_price_drop_pct:
            return Deal(
                listing,
                "price_drop",
                f"Preis gesenkt −{drop:.0f}%",
                score=drop + 10,
                discount_pct=drop,
                previous_price=previous_price,
            )

    if len(market_samples) >= profil.min_samples_for_median:
        ref = statistics.median(market_samples)
        if ref and listing.price_eur < ref:
            discount = (ref - listing.price_eur) / ref * 100
            if discount >= profil.min_discount_pct:
                return Deal(
                    listing,
                    "under_market",
                    f"{discount:.0f}% unter Marktwert",
                    score=discount,
                    discount_pct=discount,
                    reference_price=ref,
                )
    return None
