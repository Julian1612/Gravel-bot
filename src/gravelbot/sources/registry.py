"""Registrierung aller Quellen und fehlertolerante Ausfuehrung.

Neue Quellen kommen hier in ``alle_quellen()`` dazu — sonst muss am
Hauptablauf (app.py) nichts geaendert werden.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from gravelbot.config import Settings
from gravelbot.http import Http
from gravelbot.models import Listing, Profil
from gravelbot.sources.base import Quelle

log = logging.getLogger("gravel.sources")


def alle_quellen(http: Http, settings: Settings) -> list[Quelle]:
    # Lazy importiert, damit ein Fehler in einem Quellenmodul nicht den
    # kompletten Import von gravelbot.sources.registry verhindert.
    from gravelbot.sources.bikemarkt import BikemarktQuelle
    from gravelbot.sources.buycycle import BuycycleQuelle
    from gravelbot.sources.ebay import EbayQuelle
    from gravelbot.sources.shops.bike24 import Bike24Quelle
    from gravelbot.sources.shops.bike_components import BikeComponentsQuelle
    from gravelbot.sources.shops.bike_discount import BikeDiscountQuelle
    from gravelbot.sources.shops.canyon_outlet import CanyonOutletQuelle
    from gravelbot.sources.shops.rose_sale import RoseSaleQuelle

    return [
        BikemarktQuelle(http, settings),
        BuycycleQuelle(http, settings),
        EbayQuelle(http, settings),
        CanyonOutletQuelle(http, settings),
        RoseSaleQuelle(http, settings),
        BikeComponentsQuelle(http, settings),
        BikeDiscountQuelle(http, settings),
        Bike24Quelle(http, settings),
    ]


@dataclass
class QuellenLauf:
    """Ergebnis eines Quellendurchlaufs — Basis fuer die Laufzusammenfassung."""

    name: str
    aktiv: bool
    grund: str | None
    treffer: int
    fehler: str | None


def durchsuche_alle(quellen: list[Quelle], profil: Profil) -> tuple[list[Listing], list[QuellenLauf]]:
    """Jede Quelle einzeln in try/except — eine kaputte Quelle bricht den Lauf nicht ab."""
    listings: list[Listing] = []
    berichte: list[QuellenLauf] = []
    for quelle in quellen:
        if not quelle.aktiv():
            grund = quelle.inaktiv_grund() or "unbekannt"
            log.info("Quelle %s uebersprungen: %s", quelle.name, grund)
            berichte.append(QuellenLauf(quelle.name, False, grund, 0, None))
            continue
        try:
            treffer = quelle.suchen(profil)
        except Exception as exc:  # erwartete UND unerwartete Fehler der Quelle isolieren
            log.exception("Quelle %s fehlgeschlagen", quelle.name)
            berichte.append(QuellenLauf(quelle.name, True, None, 0, str(exc)))
            continue
        listings.extend(treffer)
        berichte.append(QuellenLauf(quelle.name, True, None, len(treffer), None))
        log.info("%s -> %s Treffer", quelle.name, len(treffer))
    return listings, berichte


def volltextsuche_alle(quellen: list[Quelle], query: str, max_seiten: int, gesamtlimit: int) -> list[Listing]:
    """Fragt alle Quellen mit volltext() ab und fuehrt die Ergebnisse zusammen.

    Deckel ueber max_seiten je Quelle und ein Gesamtlimit, damit eine
    interaktive Suche nicht in den Action-Timeout laeuft.
    """
    out: dict[str, Listing] = {}
    for quelle in quellen:
        if not quelle.aktiv():
            continue
        if len(out) >= gesamtlimit:
            break
        try:
            treffer = quelle.volltext(query, max_seiten=max_seiten)
        except Exception:
            log.exception("Freitextsuche bei %s fehlgeschlagen", quelle.name)
            continue
        for item in treffer:
            if len(out) >= gesamtlimit:
                break
            out.setdefault(item.key, item)
    return list(out.values())
